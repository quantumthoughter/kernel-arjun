from __future__ import annotations

import hashlib
import json
import re
import signal
import subprocess
from datetime import datetime, timezone

from rich.console import Console

from .context import build_executor_messages, build_planner_messages, build_writer_messages
from .deliberate import Council
from .models import ModelError, ModelResponse
from .tools import TOOL_NAMES
from .verifier import parse_json_block

ALLOWED_KINDS = {"tool", "finish", "think", "escalate"}


class Orchestrator:
    def __init__(self, cfg, db, router, memory, tools, verifier):
        self.cfg = cfg
        self.db = db
        self.router = router
        self.memory = memory
        self.tools = tools
        self.verifier = verifier
        self.council = Council(router, cfg)
        self.writer_mode = False
        self.canon_text = ""
        self._last_deliberation = ""
        self.console = Console()
        self.stop_requested = False
        self.shifts = 0
        self.no_progress = 0
        self.consecutive_errors = 0
        self._last_progress_key = None
        self._last_verdict: dict[int, dict] = {}
        self._last_task_id = None

    def _sigint(self, *_):
        self.stop_requested = True
        self.console.print("\n[yellow]Ctrl-C — pausing after current step...[/yellow]")

    def run(self, goal_id: int) -> str:
        goal = self.db.get_goal(goal_id)
        if not goal:
            raise SystemExit(f"goal {goal_id} not found")
        if goal["status"] == "done":
            self.console.print(f"goal {goal_id} is already done")
            return "done"
        if not self.db.try_lock(goal_id):
            self.console.print("[red]another Kernel-Arjun process holds this goal[/red]")
            return "locked"
        try:
            signal.signal(signal.SIGINT, self._sigint)
        except ValueError:
            # not the main thread (e.g. SDK watch()); skip the Ctrl-C handler
            pass
        self._configure_mode(goal)
        self.db.set_goal_status(goal_id, "active")
        self.db.reset_running_tasks(goal_id)
        self.db.add_event(goal_id, None, "run_start", {})
        self.console.print(f"[bold]🏹 Kernel-Arjun — goal {goal_id}: {goal['title']}[/bold]")
        try:
            self._ensure_plan(goal_id)
            self._loop(goal_id)
        finally:
            self.db.unlock(goal_id)
        return self.db.get_goal(goal_id)["status"]

    def _run_verifier(self, method: str, goal, *args) -> dict:
        """Adapt to either the legacy Verifier or a pluggable SDK verifier."""
        if method == "verify":
            fn = getattr(self.verifier, "verify", None)
            if fn is None:
                fn = getattr(self.verifier, "verify_task")
            return fn(goal, *args)
        # verify_goal
        fn = getattr(self.verifier, "verify_goal", None)
        if fn is not None:
            return fn(goal, *args)
        # a pluggable verifier may only expose .verify; approximate with empty task
        task = {"seq": 0, "title": goal.get("title", ""), "detail": goal.get("dod", "")}
        return self.verifier.verify(goal, task, [], args[1] if len(args) > 1 else [])

    def _plan_text(self, goal_id: int) -> str:
        from .context import format_plan

        return format_plan(self.db.get_tasks(goal_id))

    def _steps_text(self, goal_id: int, limit: int = 5) -> str:
        from .context import format_steps

        return format_steps(self.db.recent_steps(goal_id, limit))

    def _configure_mode(self, goal: dict) -> None:
        meta = goal.get("meta") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        self.writer_mode = bool(meta.get("writer_mode"))
        canon_path = meta.get("canon")
        if canon_path:
            p = self.tools.workspace / canon_path
            if p.exists():
                self.canon_text = p.read_text()[:6000]

    def _canon_continuity(self, goal_id: int, limit: int = 12) -> str:
        """Concatenate short openings of already-written chapters for continuity."""
        chapters = sorted(
            (a["path"] for a in self.db.list_artifacts(goal_id, 200) if "book/" in a["path"])
        )
        if not chapters:
            return ""
        p = self.tools.workspace / chapters[-1]
        if not p.exists():
            return ""
        tail = p.read_text()[-1200:]
        return f"(end of {chapters[-1]})\n{tail}"

    # ---- planning ----

    def _ensure_plan(self, goal_id: int) -> None:
        if self.db.get_tasks(goal_id):
            return
        goal = self.db.get_goal(goal_id)
        self.console.print("[cyan]planning...[/cyan]")
        try:
            resp = self.router.complete("planner", build_planner_messages(goal))
        except ModelError as e:
            self._escalate(goal_id, f"planner model failed: {e}", "model error")
            return
        self.db.bump_tokens(goal_id, resp.tokens_in, resp.tokens_out)
        plan = parse_json_block(resp.content)
        items = plan.get("tasks", []) if isinstance(plan, dict) else []
        items = [t for t in items if isinstance(t, dict) and t.get("title")][:8]
        if not items:
            items = [{"title": goal["title"], "detail": goal["dod"]}]
        self.db.add_tasks(goal_id, items)
        self.db.add_event(goal_id, None, "plan", {"tasks": items})
        self.console.print(f"[green]plan: {len(items)} tasks[/green]")

    # ---- main loop ----

    def _loop(self, goal_id: int) -> None:
        while True:
            if self.stop_requested:
                self._pause(goal_id, "interrupted")
                return
            goal = self.db.get_goal(goal_id)
            if goal["status"] != "active":
                return
            if self._over_budget(goal_id):
                return
            task = self.db.next_open_task(goal_id)
            if task is None:
                if self._finish_goal(goal):
                    return
                continue
            self._step(goal, task)

    def _over_budget(self, goal_id: int) -> bool:
        b = self.db.get_budget(goal_id)
        elapsed = (datetime.now(timezone.utc) - b["started_at"]).total_seconds()
        if b["steps_used"] >= b["steps_limit"]:
            self._escalate(goal_id, "step budget exhausted", "budget")
            return True
        if b["tokens_used"] >= b["tokens_limit"]:
            self._escalate(goal_id, "token budget exhausted", "budget")
            return True
        if elapsed >= b["wallclock_limit_sec"]:
            self._escalate(goal_id, "wallclock budget exhausted", "budget")
            return True
        return False

    def _finish_goal(self, goal: dict) -> bool:
        goal_id = goal["id"]
        counts = self.db.task_counts(goal_id)
        artifacts = self.db.list_artifacts(goal_id)
        if self.writer_mode:
            # Disk is the authority. Reconcile task statuses from the filesystem,
            # then judge the book itself — phantom tasks must not block completion.
            self._reconcile_writer(goal_id)
            self.console.print("[cyan]goal verification (writer: disk truth)...[/cyan]")
            verdict = self._writer_goal_verify(goal_id, artifacts)
            self.db.add_step(goal_id, None, "goal_verify", {}, verdict, "ok" if verdict["pass"] else "error")
            self.db.add_event(goal_id, None, "goal_verify", verdict)
            if verdict["pass"]:
                self.db.set_goal_status(goal_id, "done")
                self._notify(f"Goal done: {goal['title']}")
                self.console.print(f"[bold green]✅ BOOK COMPLETE: {goal['title']}[/bold green]")
                self.console.print(f"[green]{verdict['reason']}[/green]")
                return True
            self.console.print(f"[yellow]book not accepted: {verdict.get('reason','')[:160]}[/yellow]")
            self._strategy_shift(goal_id, verdict.get("reason", ""), hint=verdict.get("missing"))
            return False
        try:
            verdict = self._run_verifier("verify_goal", goal, counts, artifacts)
        except ModelError as e:
            self._escalate(goal_id, f"goal verifier failed: {e}", "model error")
            return True
        self.db.add_step(
            goal_id, None, "goal_verify", {}, verdict, "ok" if verdict["pass"] else "error"
        )
        self.db.add_event(goal_id, None, "goal_verify", verdict)
        if verdict["pass"]:
            self.db.set_goal_status(goal_id, "done")
            self._notify(f"Goal done: {goal['title']}")
            self.console.print(f"[bold green]✅ GOAL DONE: {goal['title']}[/bold green]")
            return True
        self.console.print(f"[yellow]goal not accepted: {verdict.get('reason', '')[:140]}[/yellow]")
        self._strategy_shift(goal_id, f"goal verification failed: {verdict.get('reason', '')}", hint=verdict.get("missing"))
        return False

    # ---- one step ----

    def _step(self, goal: dict, task: dict) -> None:
        goal_id = goal["id"]
        if task["status"] == "pending":
            self.db.set_task_status(task["id"], "running")
        if self._last_task_id != task["id"]:
            self._last_task_id = task["id"]
            self.console.print(f"[blue]▶ task #{task['seq']}: {task['title']}[/blue]")
        tasks = self.db.get_tasks(goal_id)
        steps = self.db.recent_steps(goal_id, 6)
        budget = self.db.get_budget(goal_id)
        memories = self.memory.recall(f"{task['title']}. {task['detail']}", k=self.cfg.memory_top_k)
        last_verdict = self._last_verdict.get(task["id"])
        spin, ok_steps = self._detect_spin(steps, task)
        if spin:
            self.console.print("  [magenta]spin detected — auto-finishing task for verification[/magenta]")
            self._do_finish(
                goal_id,
                task,
                {
                    "kind": "finish",
                    "note": "auto-finish: repeated identical-target steps",
                    "evidence": [f"{ok_steps} successful steps on this task"],
                },
                ModelResponse(content="", model="auto"),
            )
            return
        hint = None
        if ok_steps >= 3:
            hint = (
                "You already have successful steps on this task. If it is verifiably complete, "
                "reply finish now instead of repeating work."
            )
        deliberation = None
        if self.cfg.reasoning_depth > 0:
            brief = (
                f"GOAL: {goal['title']}\nDEFINITION OF DONE: {goal['dod']}\n"
                f"CURRENT TASK (#{task['seq']}): {task['title']}\nTASK DETAIL: {task['detail']}\n\n"
                f"PLAN:\n{self._plan_text(goal_id)}\n\nRECENT STEPS:\n{self._steps_text(goal_id)}"
            )
            if self.writer_mode and self.canon_text:
                brief += f"\n\nCANON:\n{self.canon_text}"
            try:
                council = self.council.deliberate(
                    brief, boundary="BOUNDARY" in (task.get("detail") or "")
                )
                self.db.bump_tokens(goal_id, council.tokens_in, council.tokens_out)
                deliberation = council.transcript_text()
                self.console.print(
                    f"  [dim]council: {len(council.transcript)} passes · "
                    f"{council.tokens_in + council.tokens_out} tok "
                    f"({council.reasoning_tokens} reasoning)[/dim]"
                )
            except Exception as e:  # never let deliberation kill a run
                self.console.print(f"  [yellow]council skipped: {e}[/yellow]")
            self._last_deliberation = (deliberation or "")[:2000]
        build = build_writer_messages if self.writer_mode else build_executor_messages
        if self.writer_mode:
            messages = build(
                goal, task, steps, memories, budget,
                canon_text=self.canon_text,
                continuity=self._canon_continuity(goal_id),
                last_verdict=last_verdict,
                deliberation=deliberation,
            )
        else:
            messages = build(
                goal, task, tasks, steps, memories, budget, last_verdict, hint, deliberation
            )
        try:
            resp = self.router.complete(
                "executor", messages, max_tokens=self.cfg.max_output_tokens
            )
        except (ModelError, TypeError) as e:
            try:
                resp = self.router.complete("executor", messages)
            except ModelError as e2:
                self._error_step(goal_id, task, {"error": str(e2)}, "executor model error")
                return
        self.db.bump_tokens(goal_id, resp.tokens_in, resp.tokens_out)
        action = self._validate_action(parse_json_block(resp.content))
        if action is None:
            self._error_step(goal_id, task, {"raw": resp.content[:400]}, "unparseable action")
            return
        kind = action["kind"]
        if kind == "tool":
            self._do_tool(goal_id, task, action, resp)
        elif kind == "finish":
            self._do_finish(goal_id, task, action, resp)
        elif kind == "think":
            self._persist(
                goal_id, task, "think", action,
                {"ok": True, "summary": action.get("note", "")}, "ok", resp,
            )
        elif kind == "escalate":
            self._persist(goal_id, task, "escalate", action, {"ok": True}, "ok", resp)
            self._escalate(goal_id, action.get("question", "blocked"), "model escalated")

    KIND_ALIASES = {"complete": "finish", "done": "finish", "task_complete": "finish",
                    "ask": "escalate", "question": "escalate", "wait": "think", "reasoning": "think",
                    "verify": "finish", "validate": "finish", "check": "finish"}

    def _validate_action(self, raw: dict | None) -> dict | None:
        if not isinstance(raw, dict):
            return None
        if "kind" not in raw and "action" in raw:
            raw = {"kind": raw.pop("action"), **raw}
        if "kind" not in raw and "tool" in raw:
            raw = {"kind": "tool", **raw}
        kind = raw.get("kind")
        if isinstance(kind, str):
            kind = kind.strip().lower()
        kind = self.KIND_ALIASES.get(kind, kind)
        if kind in TOOL_NAMES:
            args = {k: v for k, v in raw.items() if k not in ("kind", "tool", "note", "args")}
            if isinstance(raw.get("args"), dict):
                args = {**args, **raw["args"]}
            raw = {"kind": "tool", "tool": kind, "args": args, "note": raw.get("note", "")}
            kind = "tool"
        if kind == "tool":
            tool = raw.get("tool") or raw.get("name")
            if tool not in TOOL_NAMES:
                return None
            if not isinstance(raw.get("args", {}), dict):
                return None
            raw["tool"] = tool
            raw.setdefault("args", {})
        if kind not in ALLOWED_KINDS:
            return None
        raw["kind"] = kind
        if kind == "escalate" and not raw.get("question"):
            raw["question"] = "blocked without a question"
        return raw

    # ---- actions ----

    def _do_tool(self, goal_id: int, task: dict, action: dict, resp) -> None:
        tool = action["tool"]
        args = action.get("args", {})
        fingerprint = hashlib.sha1(
            json.dumps([tool, args], sort_keys=True).encode()
        ).hexdigest()[:16]
        failed = self.db.failed_fingerprints(goal_id)
        if failed.get(fingerprint, 0) >= 3:
            self._persist(
                goal_id, task, "blocked_action", action,
                {"ok": False, "error": "identical action failed 3+ times"},
                "error", resp, fingerprint,
            )
            self._strategy_shift(goal_id, f"repeated failing action: {tool}")
            return
        result = self.tools.run(tool, args)
        status = "ok" if result.get("ok") else "error"
        step_id = self._persist(goal_id, task, "tool", action, result, status, resp, fingerprint)
        if status == "ok":
            self.consecutive_errors = 0
            artifact = result.get("artifact")
            if artifact:
                self.db.add_artifact(
                    goal_id, step_id, artifact["path"], artifact.get("sha256", ""), artifact.get("kind", "file")
                )
            # only a real artifact (a write) counts as a progress event
            if artifact:
                self._note_progress(goal_id)
            if self.writer_mode and tool == "write_file":
                self._writer_gate(goal_id, task, str(result.get("path", "")))
        else:
            self.consecutive_errors += 1
            if self.consecutive_errors >= 4:
                self._strategy_shift(
                    goal_id,
                    f"{self.consecutive_errors} consecutive tool errors; last: {str(result.get('error', ''))[:120]}",
                )

    def _reconcile_writer(self, goal_id: int) -> None:
        """Ground truth is the filesystem: mark chapters on disk done/short.

        Never creates tasks. Prevents duplicate rewrite tasks after a false
        no-progress signal.
        """
        for t in self.db.get_tasks(goal_id):
            if t["status"] == "done":
                continue
            detail = t.get("detail") or ""
            paths = re.findall(r"book/[0-9A-Za-z_]+\.md", detail)
            if not paths:
                # non-writer task (e.g. reconcile/canon) — leave it
                continue
            # a task is only "done" if ALL its referenced chapters are on disk
            ok = True
            for target in paths:
                p = self.tools.workspace / target
                if not p.exists():
                    ok = False
                    break
            if ok and paths:
                self.db.set_task_status(t["id"], "done", f"reconciled: {len(paths)} file(s) on disk")
                self.db.add_event(goal_id, None, "chapter_done",
                                  {"files": paths, "reconciled": True})
                self.console.print(f"  [green]✓ reconciled (on disk): {', '.join(paths)}[/green]")

    def _writer_goal_verify(self, goal_id: int, artifacts: list[dict]) -> dict:
        import re as _re

        tasks = self.db.get_tasks(goal_id)
        missing = []
        total_words = 0
        for t in tasks:
            m = _re.search(r"INTO\s+(\S+\.md).*?minimum\s+(\d+)\s+words", t.get("detail") or "", _re.S)
            if not m:
                continue
            target = m.group(1).rstrip(".,;")
            minimum = int(m.group(2))
            p = self.tools.workspace / target
            if not p.exists():
                missing.append(f"{target} missing")
                continue
            words = len(p.read_text().split())
            total_words += words
            if words < minimum:
                missing.append(f"{target}: {words}/{minimum}")
        if missing:
            return {"pass": False, "reason": f"{len(missing)} chapters incomplete", "missing": missing[:8]}
        return {"pass": True, "reason": f"all {len(tasks)} chapters meet target; {total_words} words total", "missing": []}

    def _writer_gate(self, goal_id: int, task: dict, written_path: str) -> bool:
        """Deterministic completion for a written chapter: count words on disk.

        If the target file meets the seed's minimum, the task is done — no LLM
        verifier needed. Non-.md writes (e.g. canon) are always accepted.
        """
        detail = task.get("detail") or ""
        m = re.search(r"INTO\s+(\S+\.md).*?minimum\s+(\d+)\s+words", detail, re.S)
        if not m:
            self.db.set_task_status(task["id"], "done", "write accepted (no word target)")
            return True
        target = m.group(1).rstrip(".,;")
        minimum = int(m.group(2))
        p = self.tools.workspace / target
        if not p.exists():
            self._persist(
                goal_id, task, "verify", {"kind": "deterministic"},
                {"pass": False, "reason": f"expected {target} on disk"}, "error",
            )
            return False
        words = len(p.read_text().split())
        if words >= minimum:
            self.db.add_step(
                goal_id, task["id"], "verify", {"kind": "deterministic", "file": target},
                {"pass": True, "reason": f"{words} words ≥ {minimum}", "words": words},
                "ok", "", getattr(self, "_resp_model", ""),
            )
            self.db.bump_steps(goal_id)
            self.db.set_task_status(task["id"], "done", f"deterministic: {words}/{minimum} words")
            self.db.add_event(goal_id, None, "chapter_done", {"file": target, "words": words})
            self.console.print(f"  [green]✓ chapter accepted deterministically: {target} ({words}/{minimum} words)[/green]")
            self.consecutive_errors = 0
            self._last_verdict.pop(task["id"], None)
            self._note_progress(goal_id)
            return True
        self._persist(
            goal_id, task, "verify", {"kind": "deterministic", "file": target},
            {"pass": False, "reason": f"{words} words < {minimum} required — continue writing",
             "missing": [f"{minimum - words} more words"]},
            "error",
        )
        self.console.print(f"  [yellow]chapter short: {words}/{minimum} words[/yellow]")
        return False

    def _do_finish(self, goal_id: int, task: dict, action: dict, resp) -> None:
        if self.writer_mode:
            # deterministic judge decides; no LLM verifier for prose chapters
            if not self._writer_gate(goal_id, task, ""):
                self.console.print("  [yellow]finish requested but chapter not yet at target[/yellow]")
            return
        goal = self.db.get_goal(goal_id)
        steps = self.db.recent_steps(goal_id, 10)
        artifacts = self.db.list_artifacts(goal_id, 10)
        self.console.print(f"  [cyan]verifying task #{task['seq']}...[/cyan]")
        try:
            verdict = self._run_verifier("verify", goal, task, steps, artifacts)
        except ModelError as e:
            self._error_step(goal_id, task, {"error": str(e)}, "verifier model error")
            return
        self.db.add_step(
            goal_id, task["id"], "verify", action, verdict,
            "ok" if verdict["pass"] else "error", "", resp.model,
        )
        self.db.bump_steps(goal_id)
        if verdict["pass"]:
            self.db.set_task_status(task["id"], "done", verdict.get("reason", ""))
            self.db.add_event(goal_id, None, "task_done", {"task": task["title"], "reason": verdict.get("reason", "")})
            self.memory.store(
                f"Completed task: {task['title']}. {verdict.get('reason', '')}",
                importance=0.4, tags=["task"],
            )
            self.console.print(f"  [green]✓ task done: {task['title']}[/green]")
            self.consecutive_errors = 0
            self._last_verdict.pop(task["id"], None)
            self._note_progress(goal_id)
        else:
            self._last_verdict[task["id"]] = verdict
            prior_fails = sum(
                1 for s in steps
                if s["kind"] == "verify"
                and s.get("task_id") == task["id"]
                and (s.get("result") or {}).get("pass") is False
            )
            self.console.print(f"  [yellow]verifier rejected: {str(verdict.get('reason', ''))[:110]}[/yellow]")
            if prior_fails + 1 >= 3:
                self.db.set_task_status(
                    task["id"], "blocked", f"verifier rejected 3x: {verdict.get('reason', '')}"
                )
                self._strategy_shift(goal_id, f"task #{task['seq']} rejected 3x by verifier")

    # ---- guards ----

    def _detect_spin(self, steps: list[dict], task: dict) -> tuple[bool, int]:
        recent = [
            s for s in steps
            if s["kind"] == "tool" and s["status"] == "ok" and s.get("task_id") == task["id"]
        ][-6:]
        counts: dict[str, int] = {}
        for s in recent:
            args = (s.get("action") or {}).get("args") or {}
            target = str(args.get("path", ""))
            if target:
                counts[target] = counts.get(target, 0) + 1
        return any(c >= 3 for c in counts.values()), len(recent)

    def _note_progress(self, goal_id: int) -> None:
        """Called only on a genuinely productive event (a file written/accepted).

        The key must reflect real output — chapters done AND artifact paths — so a
        long, productive struggle on one chapter never looks like 'no progress'.
        """
        counts = self.db.task_counts(goal_id)
        artifacts = self.db.list_artifacts(goal_id, 200)
        distinct_paths = len({a["path"] for a in artifacts})
        key = (counts.get("done", 0), distinct_paths)
        if key == self._last_progress_key:
            self.no_progress += 1
            if self.no_progress >= 8:
                self._strategy_shift(goal_id, "no growth in done tasks or artifacts for 8 productive events")
                self.no_progress = 0
        else:
            self._last_progress_key = key
            self.no_progress = 0

    def _strategy_shift(self, goal_id: int, reason: str, hint: list | None = None) -> bool:
        self.shifts += 1
        self.db.add_event(goal_id, None, "strategy_shift", {"reason": reason, "shift": self.shifts})
        self.console.print(f"  [magenta]strategy shift #{self.shifts}: {reason}[/magenta]")
        if self.writer_mode:
            # Never re-plan prose. Reconcile: mark any chapter already on disk (>= target) done,
            # re-open any that is short, and return. Re-planning duplicates work.
            self._reconcile_writer(goal_id)
            self._last_progress_key = None
            self.no_progress = 0
            return True
        if self.shifts > 2:
            self._escalate(goal_id, f"Repeated strategy shifts without progress. Last: {reason}", reason)
            return False
        goal = self.db.get_goal(goal_id)
        try:
            resp = self.router.complete(
                "planner", build_planner_messages(goal, self.db.get_tasks(goal_id), hint)
            )
        except ModelError:
            self._escalate(goal_id, f"planner failed during strategy shift: {reason}", reason)
            return False
        self.db.bump_tokens(goal_id, resp.tokens_in, resp.tokens_out)
        plan = parse_json_block(resp.content) or {}
        items = [t for t in plan.get("tasks", []) if isinstance(t, dict) and t.get("title")][:8]
        if not items:
            self._escalate(goal_id, f"re-plan produced nothing after: {reason}", reason)
            return False
        max_seq = max((t["seq"] for t in self.db.get_tasks(goal_id)), default=0)
        self.db.add_tasks(goal_id, items, start_seq=max_seq)
        self.db.add_event(goal_id, None, "replan", {"tasks": items})
        self._last_progress_key = None
        return True

    # ---- helpers ----

    def _persist(self, goal_id, task, kind, action, result, status, resp=None, fingerprint=""):
        if self._last_deliberation and isinstance(result, dict):
            result = {**result, "deliberation": self._last_deliberation}
            self._last_deliberation = ""
        step_id = self.db.add_step(
            goal_id,
            task["id"] if task else None,
            kind,
            action,
            result,
            status,
            fingerprint,
            resp.model if resp else "",
            resp.tokens_in if resp else 0,
            resp.tokens_out if resp else 0,
        )
        self.db.bump_steps(goal_id)
        self.db.add_checkpoint(
            goal_id,
            task["id"] if task else None,
            step_id,
            {
                "task": task["title"] if task else None,
                "last_kind": kind,
                "last_status": status,
            },
        )
        icon = "✓" if status == "ok" else "✗"
        summary = str(
            result.get("summary")
            or result.get("error")
            or result.get("note")
            or result.get("raw")
            or ""
        )[:110]
        self.console.print(f"    {icon} [{kind}] {summary}")
        return step_id

    def _error_step(self, goal_id, task, result, note):
        self.consecutive_errors += 1
        self._persist(goal_id, task, "error", {"note": note}, result, "error")
        if self.consecutive_errors >= 4:
            self._strategy_shift(goal_id, f"{self.consecutive_errors} consecutive errors: {note}")

    def _escalate(self, goal_id: int, question: str, reason: str = "") -> None:
        self.db.add_event(goal_id, None, "escalate", {"question": question, "reason": reason})
        self.db.set_goal_status(goal_id, "paused")
        self._notify(f"paused: {question}")
        self.console.print(f"[bold yellow]⚠ ESCALATION: {question}[/bold yellow]")
        self.console.print(f"[yellow]goal {goal_id} paused — resume with: arjun resume {goal_id}[/yellow]")

    def _pause(self, goal_id: int, reason: str) -> None:
        self.db.add_event(goal_id, None, "pause", {"reason": reason})
        self.db.set_goal_status(goal_id, "paused")
        self.console.print(f"[yellow]paused ({reason}) — resume with: arjun resume {goal_id}[/yellow]")

    def _notify(self, message: str) -> None:
        if not self.cfg.notify_enabled:
            return
        safe = message.replace('"', "'").replace("\\", "")[:200]
        try:
            subprocess.run(
                ["osascript", "-e", f'display notification "{safe}" with title "Kernel-Arjun" sound name "Glass"'],
                check=False,
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass

"""The Arjun SDK client — embed the long-horizon kernel in any Python program."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import Config, load_config
from ..db import DB, ensure_database
from ..memory import EngramMemory
from ..models import Router
from ..orchestrator import Orchestrator
from ..tools import ToolRuntime
from .backends import Backend
from .verifiers import ModelVerifier


@dataclass
class Meter:
    words: int = 0
    steps: int = 0
    tokens_used: int = 0
    tokens_limit: int = 0
    escalations: int = 0
    replans: int = 0
    first_pass: int = 0
    tasks_total: int = 0
    tasks_done: int = 0

    @property
    def tokens_pct(self) -> float:
        return 100 * self.tokens_used / self.tokens_limit if self.tokens_limit else 0.0


@dataclass
class RunResult:
    goal_id: int
    status: str
    meter: Meter
    workspace: str
    dod: str


@dataclass
class GoalHandle:
    id: int
    title: str
    dod: str
    workspace: str


class Arjun:
    """A long-horizon agent kernel you can embed.

    One instance = one engine bound to a database and a workspace. Create many
    goals, run them, watch them, score them — all from Python.
    """

    def __init__(
        self,
        workspace: str = ".",
        backend: Backend | str = "openai",
        dsn: str | None = None,
        config_path: str | None = None,
        verifier=None,
        reasoning_depth: int | None = None,
        max_output_tokens: int | None = None,
        max_minutes: int | None = None,
        memory: bool = True,
        verbose: bool = True,
    ):
        self.cfg: Config = load_config(config_path) if config_path else Config()
        if dsn:
            self.cfg.dsn = dsn
        if isinstance(backend, str):
            backend = Backend(kind=backend)
        self.backend = backend
        backend.apply(self.cfg)
        if reasoning_depth is not None:
            self.cfg.reasoning_depth = reasoning_depth
        if max_output_tokens is not None:
            self.cfg.max_output_tokens = max_output_tokens
        if max_minutes is not None:
            self.cfg.max_minutes = max_minutes
        self.workspace = str(Path(workspace).expanduser().resolve())
        self.verbose = verbose

        ensure_database(self.cfg.dsn)
        self.db = DB(self.cfg.dsn)
        self.db.init_schema()
        self.router: Router = backend.build_router(self.cfg)
        client = backend.build_client()
        embedder = lambda text: client.embed(self.cfg.embed_model, text)  # noqa: E731
        self.memory = EngramMemory(
            self.cfg.memory_path, embedder,
            enabled=memory and self.cfg.memory_enabled,
            top_k=self.cfg.memory_top_k,
        )
        self._custom_verifier = verifier

    # ---- goal lifecycle -----------------------------------------------------

    def goal(
        self,
        title: str,
        dod: str = "",
        workspace: str | None = None,
        max_steps: int | None = None,
        max_tokens: int | None = None,
        meta: dict | None = None,
    ) -> GoalHandle:
        ws = str(Path(workspace or self.workspace).expanduser().resolve())
        gid = self.db.create_goal(title, dod, ws, meta or {})
        self.db.ensure_budget(
            gid,
            max_steps or self.cfg.max_steps,
            max_tokens or self.cfg.max_tokens,
            self.cfg.max_minutes * 60,
        )
        return GoalHandle(id=gid, title=title, dod=dod, workspace=ws)

    def plan_tasks(self, goal: GoalHandle, tasks: list[dict]) -> None:
        """Pre-seed the plan (each item: {title, detail}). Bypasses the planner model."""
        self.db.add_tasks(goal.id, tasks)

    def run(self, goal: GoalHandle | int, depth: int | None = None) -> RunResult:
        gid = goal.id if isinstance(goal, GoalHandle) else goal
        if depth is not None:
            self.cfg.reasoning_depth = depth
        verifier = self._custom_verifier or ModelVerifier(self.router)
        tools = ToolRuntime(self.db.get_goal(gid)["workspace"], self.memory, self.cfg)
        orch = Orchestrator(self.cfg, self.db, self.router, self.memory, tools, verifier)
        if not self.verbose:
            from rich.console import Console
            orch.console = Console(quiet=True)
        status = orch.run(gid)
        return self.result(gid)

    def resume(self, goal_id: int) -> RunResult:
        return self.run(goal_id)

    def watch(self, goal_id: int):
        """Run the goal and yield live events as they are written to the ledger.

        A generator: iterate it to stream progress, then read k.result(id).

            for ev in k.watch(goal.id):
                print(ev["kind"], ev["detail"])
        """
        import threading
        import time

        seen = {e["id"] for e in self.db.recent_events(goal_id, 100000)}
        result_box: dict = {}

        def _run():
            result_box["r"] = self.run(goal_id)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        while t.is_alive():
            for e in reversed(self.db.recent_events(goal_id, 50)):
                if e["id"] not in seen:
                    seen.add(e["id"])
                    payload = e.get("payload") or {}
                    detail = (
                        payload.get("file")
                        or payload.get("reason")
                        or payload.get("question")
                        or payload.get("source")
                        or ""
                    )
                    yield {"kind": e["type"], "detail": detail, "payload": payload}
            time.sleep(0.5)
        # drain any final events
        for e in reversed(self.db.recent_events(goal_id, 50)):
            if e["id"] not in seen:
                seen.add(e["id"])
                payload = e.get("payload") or {}
                detail = payload.get("file") or payload.get("reason") or ""
                yield {"kind": e["type"], "detail": detail, "payload": payload}

    # ---- inspection ---------------------------------------------------------

    def result(self, goal_id: int) -> RunResult:
        goal = self.db.get_goal(goal_id) or {}
        b = self.db.get_budget(goal_id) or {}
        counts = self.db.task_counts(goal_id)
        events = self.db.recent_events(goal_id, 100000)
        verifies = [s for s in self.db.recent_steps(goal_id, 100000) if s["kind"] == "verify"]
        first_pass = sum(1 for v in verifies if (v.get("result") or {}).get("pass") is True)
        words = 0
        seen = set()
        for a in self.db.list_artifacts(goal_id, 500):
            if a["path"] in seen:
                continue
            seen.add(a["path"])
            p = Path(a["path"])
            if p.exists() and p.suffix == ".md":
                words += len(p.read_text().split())
        meter = Meter(
            words=words,
            steps=b.get("steps_used", 0),
            tokens_used=b.get("tokens_used", 0),
            tokens_limit=b.get("tokens_limit", 0),
            escalations=sum(1 for e in events if e["type"] == "escalate"),
            replans=sum(1 for e in events if e["type"] == "replan"),
            first_pass=first_pass,
            tasks_total=sum(counts.values()),
            tasks_done=counts.get("done", 0),
        )
        return RunResult(
            goal_id=goal_id,
            status=goal.get("status", "unknown"),
            meter=meter,
            workspace=goal.get("workspace", ""),
            dod=goal.get("dod", ""),
        )

    def meter(self, goal_id: int) -> Meter:
        return self.result(goal_id).meter

    def list_goals(self, limit: int = 20) -> list[dict]:
        return self.db.list_goals(limit)

    def pause(self, goal_id: int) -> None:
        self.db.set_goal_status(goal_id, "paused")

    def context_anatomy(self, goal_id: int) -> dict:
        """Return the token-size breakdown of the next assembled context."""
        from ..context import build_executor_messages, build_writer_messages

        goal = self.db.get_goal(goal_id)
        task = self.db.next_open_task(goal_id)
        if not task:
            return {"error": "no open task"}
        tasks = self.db.get_tasks(goal_id)
        steps = self.db.recent_steps(goal_id, 6)
        budget = self.db.get_budget(goal_id)
        meta = goal.get("meta") or {}
        writer = bool(meta.get("writer_mode"))
        canon = ""
        if writer and meta.get("canon"):
            p = Path(goal["workspace"]) / meta["canon"]
            if p.exists():
                canon = p.read_text()[:6000]
        if writer:
            msgs = build_writer_messages(goal, task, steps, [], budget, canon_text=canon)
        else:
            msgs = build_executor_messages(goal, task, tasks, steps, [], budget)
        est = lambda t: int(len(t.split()) * 1.33)  # noqa: E731
        return {
            "task": task["title"],
            "messages": [{"role": m["role"], "tokens": est(m["content"])} for m in msgs],
            "total_tokens": sum(est(m["content"]) for m in msgs),
            "window_pct": 100 * sum(est(m["content"]) for m in msgs) / 1_000_000,
        }

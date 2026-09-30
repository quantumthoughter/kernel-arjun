from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import CONFIG_PATH, load_config
from .db import DB, ensure_database
from .memory import EngramMemory
from .models import FakeModel, ModelError, OllamaClient, OpenAIClient, Router
from .orchestrator import Orchestrator
from .tools import TOOL_NAMES, ToolRuntime
from .verifier import Verifier

console = Console()

DRY_RUN_SCRIPT = [
    json.dumps(
        {
            "tasks": [
                {"title": "Write greeting file", "detail": "Create hello.txt containing 'Jai Arjun'"},
                {"title": "Confirm greeting file", "detail": "Read hello.txt and confirm its content"},
            ]
        }
    ),
    json.dumps(
        {
            "kind": "tool",
            "tool": "write_file",
            "args": {"path": "hello.txt", "content": "Jai Arjun\n"},
            "note": "create the greeting file",
        }
    ),
    json.dumps(
        {"kind": "finish", "note": "hello.txt was written", "evidence": ["write_file reported success"]}
    ),
    json.dumps({"pass": True, "reason": "hello.txt was created with the requested content", "missing": []}),
    json.dumps(
        {"kind": "tool", "tool": "read_file", "args": {"path": "hello.txt"}, "note": "confirm content"}
    ),
    json.dumps(
        {"kind": "finish", "note": "content confirmed", "evidence": ["read_file output: Jai Arjun"]}
    ),
    json.dumps({"pass": True, "reason": "file content confirmed by read", "missing": []}),
    json.dumps({"pass": True, "reason": "all tasks done, definition of done met", "missing": []}),
]


def setup(cfg, dry_run: bool = False, workspace: str | None = None):
    ensure_database(cfg.dsn)
    db = DB(cfg.dsn)
    db.init_schema()
    if dry_run:
        client = FakeModel(DRY_RUN_SCRIPT)
        cfg.reasoning_depth = 0
    elif cfg.backend == "openai":
        key = os.environ.get("HIVE_API_KEY", cfg.hive_api_key)
        client = OpenAIClient(cfg.hive_base_url, key, timeout=cfg.model_timeout_sec)
    else:
        client = OllamaClient(cfg.ollama_url, timeout=cfg.model_timeout_sec)
    router = Router(cfg, client)
    embedder = lambda text: client.embed(cfg.embed_model, text)
    memory = EngramMemory(
        cfg.memory_path, embedder, enabled=cfg.memory_enabled, top_k=cfg.memory_top_k
    )
    return db, client, router, memory


def build_orchestrator(cfg, db, router, memory, workspace: str) -> Orchestrator:
    tools = ToolRuntime(workspace, memory, cfg)
    verifier = Verifier(router)
    return Orchestrator(cfg, db, router, memory, tools, verifier)


def cmd_init(args) -> int:
    cfg = load_config(args.config)
    ensure_database(cfg.dsn)
    db = DB(cfg.dsn)
    db.init_schema()
    Path(cfg.memory_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        example = Path(__file__).parent.parent / "config.example.yaml"
        if example.exists():
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(example.read_text())
            console.print(f"[green]config created:[/green] {CONFIG_PATH}")
    console.print("[green]Kernel-Arjun initialized[/green]")
    console.print(f"  database: {cfg.dsn}")
    console.print(f"  memory:   {cfg.memory_path}")
    console.print("next: arjun start \"your goal\" --dod \"definition of done\"")
    return 0


def cmd_start(args) -> int:
    cfg = load_config(args.config)
    if args.max_steps:
        cfg.max_steps = args.max_steps
    db, client, router, memory = setup(cfg, dry_run=args.dry_run)
    workspace = str(Path(args.workspace or ".").expanduser().resolve())
    meta = {}
    if args.canon:
        meta["writer_mode"] = True
        meta["canon"] = args.canon
    goal_id = db.create_goal(args.title, args.dod or "", workspace, meta)
    db.ensure_budget(goal_id, cfg.max_steps, cfg.max_tokens, cfg.max_minutes * 60)
    console.print(f"[green]goal {goal_id} created[/green] — workspace: {workspace}")
    orch = build_orchestrator(cfg, db, router, memory, workspace)
    status = orch.run(goal_id)
    console.print(f"final status: [bold]{status}[/bold]")
    return 0


def cmd_book(args) -> int:
    """Run a seed-driven book mission: seeds.yml defines goal + one task per chapter."""
    cfg = load_config(args.config)
    seeds_path = Path(args.seeds).expanduser().resolve()
    spec = yaml.safe_load(seeds_path.read_text())
    goal_spec = spec["goal"]
    seeds = spec["seeds"]
    cfg.reasoning_depth = args.depth if args.depth is not None else cfg.reasoning_depth
    cfg.max_output_tokens = args.max_tokens or cfg.max_output_tokens
    cfg.backend = cfg.backend if not args.local else "ollama"
    workspace = str(Path(args.workspace).expanduser().resolve())
    Path(workspace, "book").mkdir(parents=True, exist_ok=True)
    for name in ("canon.md", "check_canon.py"):
        src = seeds_path.parent / name
        if src.exists():
            shutil.copy(src, Path(workspace) / name)
    db, client, router, memory = setup(cfg, dry_run=False)
    db.init_schema()
    meta = {"writer_mode": True, "canon": "canon.md"}
    goal_id = db.create_goal(goal_spec["title"], goal_spec.get("dod", ""), workspace, meta)
    db.ensure_budget(
        goal_id,
        goal_spec.get("steps_limit", cfg.max_steps),
        goal_spec.get("tokens_limit", cfg.max_tokens),
        cfg.max_minutes * 60,
    )
    tasks = [
        {"title": f"Ch {s['id']}: {s['title']}", "detail": render_seed(s)}
        for s in seeds
    ]
    db.add_tasks(goal_id, tasks)
    db.add_event(goal_id, None, "plan", {"source": "seeds.yml", "tasks": len(tasks)})
    console.print(f"[green]book goal {goal_id} created[/green] — {len(tasks)} chapters, workspace {workspace}")
    console.print(f"[dim]backend={cfg.backend} depth={cfg.reasoning_depth} tokens_limit={goal_spec.get('tokens_limit'):,}[/dim]")
    orch = build_orchestrator(cfg, db, router, memory, workspace)
    status = orch.run(goal_id)
    console.print(f"final status: [bold]{status}[/bold]  —  meter: arjun meter {goal_id}")
    return 0


def render_seed(s: dict) -> str:
    bound = "BOUNDARY " if s["id"] in {"02", "08", "14", "17", "20", "21"} else ""
    return (
        f"{bound}WRITE CHAPTER INTO {s['file']} (minimum {s['words']} words).\n"
        f"GROUND (outer — what is true): {s['ground']}\n"
        f"PATH (inner — how to render): {s['path']}\n"
        f"FRUIT (other — done when): {s['fruit']}\n"
        f"QUERY (the one instruction): {s['query']}\n"
        f"When the file exists at {s['file']} with ≥{s['words']} words and satisfies FRUIT, reply finish."
    )


def cmd_resume(args) -> int:
    cfg = load_config(args.config)
    db, client, router, memory = setup(cfg)
    goal = db.get_goal(args.goal_id)
    if not goal:
        console.print(f"[red]goal {args.goal_id} not found[/red]")
        return 1
    orch = build_orchestrator(cfg, db, router, memory, goal["workspace"])
    status = orch.run(args.goal_id)
    console.print(f"final status: [bold]{status}[/bold]")
    return 0


def cmd_status(args) -> int:
    cfg = load_config(args.config)
    db = DB(cfg.dsn)
    if args.goal_id:
        goal = db.get_goal(args.goal_id)
        if not goal:
            console.print(f"[red]goal {args.goal_id} not found[/red]")
            return 1
        console.print(f"[bold]goal {goal['id']}: {goal['title']}[/bold]")
        console.print(f"status: {goal['status']}  workspace: {goal['workspace']}")
        console.print(f"dod: {goal['dod']}")
        counts = db.task_counts(goal["id"])
        budget = db.get_budget(goal["id"])
        console.print(
            f"tasks: {counts}  |  steps: {budget['steps_used']}/{budget['steps_limit']}  "
            f"tokens: {budget['tokens_used']}/{budget['tokens_limit']}"
        )
        table = Table(title="tasks")
        table.add_column("seq", justify="right")
        table.add_column("status")
        table.add_column("title")
        table.add_column("verifier note")
        for t in db.get_tasks(goal["id"]):
            table.add_row(str(t["seq"]), t["status"], t["title"], (t["verify_note"] or "")[:60])
        console.print(table)
        steps = db.recent_steps(goal["id"], 8)
        if steps:
            console.print("[bold]recent steps:[/bold]")
            for s in steps:
                result = s.get("result") or {}
                summary = str(result.get("summary") or result.get("error") or "")[:90]
                console.print(f"  [{s['status']}] {s['kind']} {summary}")
    else:
        goals = db.list_goals()
        table = Table(title="goals")
        table.add_column("id", justify="right")
        table.add_column("status")
        table.add_column("title")
        table.add_column("created")
        for g in goals:
            table.add_row(str(g["id"]), g["status"], g["title"], str(g["created_at"])[:19])
        console.print(table)
    return 0


def cmd_logs(args) -> int:
    cfg = load_config(args.config)
    db = DB(cfg.dsn)
    goal = db.get_goal(args.goal_id)
    if not goal:
        console.print(f"[red]goal {args.goal_id} not found[/red]")
        return 1
    console.print(f"[bold]events — goal {goal['id']}[/bold]")
    for e in reversed(db.recent_events(goal["id"], args.tail)):
        payload = json.dumps(e["payload"])[:110]
        console.print(f"  {str(e['ts'])[:19]}  {e['type']}: {payload}")
    console.print(f"\n[bold]steps — goal {goal['id']}[/bold]")
    for s in db.recent_steps(goal["id"], args.tail):
        action = s.get("action") or {}
        result = s.get("result") or {}
        summary = str(result.get("summary") or result.get("error") or result.get("note") or "")[:90]
        console.print(f"  #{s['id']} [{s['status']}] {s['kind']}: {summary}")
    return 0


def cmd_context(args) -> int:
    """Show the anatomy of the context the engine would assemble for the next step."""
    cfg = load_config(args.config)
    db = DB(cfg.dsn)
    goal = db.get_goal(args.goal_id)
    if not goal:
        console.print(f"[red]goal {args.goal_id} not found[/red]")
        return 1
    task = db.next_open_task(goal["id"])
    if not task:
        console.print("[yellow]no open task — goal is complete[/yellow]")
        return 0
    tasks = db.get_tasks(goal["id"])
    steps = db.recent_steps(goal["id"], 6)
    budget = db.get_budget(goal["id"])
    memories = []  # memory recall requires a model; show the slot

    meta = goal.get("meta") or {}
    writer = bool(meta.get("writer_mode"))
    canon_text = ""
    if writer and meta.get("canon"):
        p = Path(goal["workspace"]) / meta["canon"]
        if p.exists():
            canon_text = p.read_text()[:6000]

    from .context import build_executor_messages, build_writer_messages

    if writer:
        msgs = build_writer_messages(
            goal, task, steps, memories, budget, canon_text=canon_text,
            continuity="(tail of last chapter)", last_verdict=None,
        )
    else:
        msgs = build_executor_messages(
            goal, task, tasks, steps, memories, budget, None, None
        )

    def est(text: str) -> int:
        return int(len(text.split()) * 1.33)

    table = Table(title=f"context for goal {goal['id']} · task #{task['seq']}: {task['title']}")
    table.add_column("message", style="cyan")
    table.add_column("chars", justify="right")
    table.add_column("~tokens", justify="right")
    total = 0
    for m in msgs:
        t = est(m["content"])
        total += t
        table.add_row(m["role"], str(len(m["content"])), f"{t:,}")
    table.add_row("[bold]TOTAL[/bold]", "", f"[bold]{total:,}[/bold]")
    console.print(table)
    console.print(
        f"window budget: ~1,000,000 tokens  →  this call uses "
        f"[bold]{100 * total / 1_000_000:.2f}%[/bold] of the window"
    )
    console.print(
        "[dim]The context is ASSEMBLED for this step, not accumulated: "
        "goal + seed + canon + tail-of-last-chapter + recent steps.[/dim]"
    )
    if args.show:
        console.print("\n[bold]--- system ---[/bold]")
        console.print(msgs[0]["content"][:2000])
        console.print("\n[bold]--- user (assembled) ---[/bold]")
        console.print(msgs[1]["content"][:args.show])
    return 0


def cmd_watch(args) -> int:
    """Watchdog daemon: keep active/paused goals running until done or budget out."""
    import time as _time

    cfg = load_config(args.config)
    if args.reasoning_depth is not None:
        cfg.reasoning_depth = args.reasoning_depth
    db = DB(cfg.dsn)
    wanted = {"active", "paused"} if args.include_paused else {"active"}
    scope = f"goal {args.goal}" if args.goal else "all " + "/".join(sorted(wanted)) + " goals"
    console.print("[bold]🜂 arjun watch[/bold] — durable supervisor")
    console.print(f"  watching {scope} · polling every {args.interval}s · max resumes: {args.max_attempts}")
    attempts: dict[int, int] = {}
    try:
        while True:
            db = DB(cfg.dsn)
            goals = db.list_goals(100)
            if args.goal:
                goals = [g for g in goals if g["id"] == args.goal]
            actionable = [g for g in goals if g["status"] in wanted]
            if not actionable:
                console.print("[green]nothing to do — all goals resolved[/green]")
                if args.once:
                    return 0
            for g in actionable:
                gid = g["id"]
                if attempts.get(gid, 0) >= args.max_attempts:
                    console.print(f"[yellow]goal {gid}: max attempts reached; leaving paused[/yellow]")
                    continue
                attempts[gid] = attempts.get(gid, 0) + 1
                console.print(f"[cyan]▶ resuming goal {gid}: {g['title']}[/cyan] (attempt {attempts[gid]})")
                goal_row = db.get_goal(gid)
                db, client, router, memory = setup(cfg)
                orch = build_orchestrator(cfg, db, router, memory, goal_row["workspace"])
                try:
                    status = orch.run(gid)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    console.print(f"[red]goal {gid} run errored: {e}[/red]")
                    status = "error"
                console.print(f"  goal {gid} -> [bold]{status}[/bold]")
                if status == "done":
                    attempts.pop(gid, None)
            if args.once:
                return 0
            _time.sleep(args.interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]watch stopped by user[/yellow]")
        return 0


def cmd_vault(args) -> int:
    """Seal, open, verify, or attach a portable VĀK memory vault."""
    from .vak import Vault, find_vault

    action = args.action
    if action == "seal":
        cfg = load_config(args.config)
        db = DB(cfg.dsn)
        v = Vault(name=args.name or "æmma-vault")
        if args.identity:
            v.set_identity(json.loads(Path(args.identity).read_text()))
        if args.goal:
            goal = db.get_goal(args.goal)
            if goal:
                v.add_layer("goal", json.dumps({k: str(goal[k]) for k in ("id", "title", "dod", "status")},
                                               indent=2, ensure_ascii=False), kind="ledger")
                for a in db.list_artifacts(args.goal, 200):
                    p = Path(a["path"])
                    if p.exists() and p.suffix == ".md":
                        v.add_engram(f"[artifact] {p.name}: {p.read_text()[:400]}",
                                     importance=0.5, tags=["artifact"])
        mem_path = Path(cfg.memory_path).expanduser()
        if mem_path.exists() and not args.no_memory:
            try:
                data = json.loads(mem_path.read_text())
                for e in data:
                    v.add_engram(e["content"], importance=e.get("importance", 0.5),
                                 tags=e.get("tags", []), strength=e.get("strength", 1.0))
            except Exception as ex:
                console.print(f"[yellow]could not read memory: {ex}[/yellow]")
        out = args.out or "mind.vak"
        v.write(out)
        console.print(f"[green]sealed[/green] {out} — {len(v.layers)} layers, {len(v.engrams)} engrams, {Path(out).stat().st_size} bytes")
        console.print(f"  seal: {v.seal[:32]}…")
        return 0

    if action in ("open", "verify"):
        path = args.path or find_vault()
        if not path:
            console.print("[red]no vault found (pass a path)[/red]")
            return 1
        try:
            v = Vault.read(path)
        except ValueError as e:
            console.print(f"[red]seal FAILED:[/red] {e}")
            return 1
        console.print(f"[green]VĀK vault OK[/green] {path}")
        console.print(f"  name: {v.name}")
        console.print(f"  layers: {len(v.layers)}  engrams: {len(v.engrams)}")
        console.print(f"  seal: {v.seal[:32]}…")
        if action == "open":
            for layer in v.layers[:5]:
                console.print(f"  [{layer.kind}] {layer.name}: {layer.payload[:60]}")
        return 0

    if action == "attach":
        path = args.path or find_vault()
        if not path:
            console.print("[red]no vault found[/red]")
            return 1
        v = Vault.read(path)
        cfg = load_config(args.config)
        # re-embodiment is done by a LOCAL embedder (Ollama), independent of the
        # chat backend in use. The body is regenerated; the text is the truth.
        from .models import OllamaClient, ModelError

        embed_url = args.embed_url or cfg.ollama_url
        embed_model = args.embed_model or cfg.embed_model
        client = OllamaClient(embed_url, timeout=120)
        memory = EngramMemory(
            cfg.memory_path, lambda t: client.embed(embed_model, t),
            enabled=True, top_k=cfg.memory_top_k,
        )
        try:
            client.embed(embed_model, "ping")
        except ModelError as e:
            console.print(f"[red]embedder unavailable ({embed_model} @ {embed_url}):[/red] {e}")
            console.print("  start ollama and pull the embed model, or pass --embed-url/--embed-model")
            return 1
        n = v.attach_engrams_to(memory)
        console.print(f"[green]attached[/green] {n} engrams from {path} into {cfg.memory_path}")
        console.print(f"  re-embodied with {embed_model} via {embed_url}")
        return 0

    console.print("usage: arjun vault {seal|open|verify|attach}")
    return 1


def cmd_meter(args) -> int:
    """Long-horizon scorecard: production, coherence, fidelity, reasoning depth."""
    cfg = load_config(args.config)
    db = DB(cfg.dsn)
    goal = db.get_goal(args.goal_id)
    if not goal:
        console.print(f"[red]goal {args.goal_id} not found[/red]")
        return 1
    budget = db.get_budget(goal["id"])
    counts = db.task_counts(goal["id"])
    events = db.recent_events(goal["id"], 100000)
    steps = db.recent_steps(goal["id"], 100000)

    escalations = sum(1 for e in events if e["type"] == "escalate")
    replans = sum(1 for e in events if e["type"] == "replan")
    n_steps = len(steps)
    tools = [s for s in steps if s["kind"] == "tool"]
    verifies = [s for s in steps if s["kind"] == "verify"]
    first_pass = sum(1 for v in verifies if (v.get("result") or {}).get("pass") is True)
    tool_errors = sum(1 for s in tools if s["status"] == "error")
    # per-task first-pass: a task is "clean" if its first verify attempt passed
    from collections import defaultdict

    by_task: dict = defaultdict(list)
    for v in verifies:
        r = v.get("result") or {}
        if "pass" in r:
            by_task[v.get("task_id")].append(bool(r["pass"]))
    clean_tasks = sum(1 for seq in by_task.values() if seq and seq[0])
    tasks_verified = len([s for s in by_task.values() if s])

    tokens_used = budget["tokens_used"]
    words = 0
    try:
        seen = set()
        for a in db.list_artifacts(goal["id"], 500):
            if a["path"] in seen:
                continue
            seen.add(a["path"])
            p = Path(a["path"])
            if p.exists() and p.suffix == ".md":
                words += len(p.read_text().split())
    except Exception:
        pass

    def per(n, d):
        return f"{n / d:.2f}" if d else "—"

    table = Table(title=f"meter — goal {goal['id']}: {goal['title']}")
    table.add_column("metric")
    table.add_column("value", justify="right")
    table.add_row("status", goal["status"])
    table.add_row("words on disk", str(words))
    table.add_row("steps", f"{n_steps}")
    table.add_row("tool steps", f"{len(tools)}")
    table.add_row("tokens used", f"{tokens_used:,} / {budget['tokens_limit']:,}")
    table.add_row("tokens used %", f"{100 * tokens_used / budget['tokens_limit']:.1f}%")
    table.add_row("words / step", per(words, n_steps))
    table.add_row("words / 1k tokens", per(1000 * words, tokens_used or 1))
    table.add_row("escalations", str(escalations))
    table.add_row("escalations / 100 steps", per(100 * escalations, n_steps or 1))
    table.add_row("replans", str(replans))
    table.add_row("verify attempts", str(len(verifies)))
    table.add_row("verify pass %", f"{100 * first_pass / len(verifies):.0f}%" if verifies else "—")
    table.add_row(
        "first-pass task %",
        f"{100 * clean_tasks / tasks_verified:.0f}%  ({clean_tasks}/{tasks_verified})"
        if tasks_verified else "—",
    )
    table.add_row("tool errors", str(tool_errors))
    table.add_row("task counts", json.dumps(counts))
    console.print(table)
    return 0


def cmd_doctor(args) -> int:
    cfg = load_config(args.config)
    console.print("[bold]Kernel-Arjun doctor[/bold]")
    ok_all = True

    try:
        ensure_database(cfg.dsn)
        db = DB(cfg.dsn)
        db.init_schema()
        db.get_goal(0)
        console.print("  [green]✓[/green] postgres reachable + schema ok")
    except Exception as e:
        ok_all = False
        console.print(f"  [red]✗[/red] postgres: {e}")

    try:
        client = OllamaClient(cfg.ollama_url, timeout=30)
        models = client.models()
        console.print(f"  [green]✓[/green] ollama reachable ({len(models)} models)")
        for role in ("planner", "executor", "verifier", "compressor"):
            model = getattr(cfg, f"{role}_model")
            hit = any(m == model or m.startswith(model.split(":")[0]) for m in models)
            mark = "[green]✓[/green]" if hit else "[red]✗[/red]"
            if not hit:
                ok_all = False
            console.print(f"    {mark} {role}: {model}")
        try:
            vec = client.embed(cfg.embed_model, "ping")
            console.print(f"  [green]✓[/green] embeddings: {cfg.embed_model} ({len(vec)} dims)")
        except ModelError as e:
            ok_all = False
            console.print(f"  [red]✗[/red] embeddings: {e}")
    except Exception as e:
        ok_all = False
        console.print(f"  [red]✗[/red] ollama: {e}")

    try:
        memory = EngramMemory(cfg.memory_path, lambda t: [0.0], enabled=cfg.memory_enabled)
        console.print(f"  [green]✓[/green] memory store: {memory.stats()['total']} engrams at {cfg.memory_path}")
    except Exception as e:
        ok_all = False
        console.print(f"  [red]✗[/red] memory: {e}")

    console.print(f"  config: {CONFIG_PATH}")
    console.print("[green]all good[/green]" if ok_all else "[yellow]some checks failed[/yellow]")
    return 0 if ok_all else 1


def cmd_tools(args) -> int:
    console.print("[bold]available tools:[/bold]")
    for name in TOOL_NAMES:
        console.print(f"  - {name}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="arjun", description="Kernel-Arjun — long-horizon agent engine")
    parser.add_argument("--version", action="version", version=f"Kernel-Arjun {__version__}")
    parser.add_argument("--config", help="path to config yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="initialize database, config, memory")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("start", help="create and run a new goal")
    p.add_argument("title")
    p.add_argument("--dod", default="", help="definition of done")
    p.add_argument("--workspace", default=".", help="workspace directory")
    p.add_argument("--max-steps", type=int, default=0)
    p.add_argument("--canon", help="canon file relative to workspace; enables writer mode")
    p.add_argument("--dry-run", action="store_true", help="use scripted model (no ollama)")
    p.set_defaults(fn=cmd_start)

    p = sub.add_parser("book", help="run a seed-driven book mission (seeds.yml)")
    p.add_argument("seeds", help="path to seeds.yml")
    p.add_argument("--workspace", required=True)
    p.add_argument("--depth", type=int, default=None, help="reasoning depth (council passes)")
    p.add_argument("--max-tokens", type=int, default=0, help="model output cap per call")
    p.add_argument("--local", action="store_true", help="force ollama backend")
    p.set_defaults(fn=cmd_book)

    p = sub.add_parser("resume", help="resume a paused goal")
    p.add_argument("goal_id", type=int)
    p.set_defaults(fn=cmd_resume)

    p = sub.add_parser("status", help="show goals or goal detail")
    p.add_argument("goal_id", type=int, nargs="?")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("logs", help="show goal events and steps")
    p.add_argument("goal_id", type=int)
    p.add_argument("--tail", type=int, default=20)
    p.set_defaults(fn=cmd_logs)

    p = sub.add_parser("meter", help="long-horizon scorecard for a goal")
    p.add_argument("goal_id", type=int)
    p.set_defaults(fn=cmd_meter)

    p = sub.add_parser("vault", help="portable VĀK memory vault (seal/open/verify/attach)")
    p.add_argument("action", choices=["seal", "open", "verify", "attach"])
    p.add_argument("path", nargs="?", help="vault file (or auto-find a mounted drive)")
    p.add_argument("--out", help="output path for seal")
    p.add_argument("--name", help="vault name")
    p.add_argument("--goal", type=int, help="include a goal's ledger + artifacts")
    p.add_argument("--identity", help="path to a JSON identity file")
    p.add_argument("--no-memory", action="store_true", help="skip local engram memory")
    p.add_argument("--embed-url", help="embedder URL for attach (default: ollama)")
    p.add_argument("--embed-model", help="embed model for attach (default: nomic-embed-text)")
    p.set_defaults(fn=cmd_vault)

    p = sub.add_parser("context", help="show the assembled context for the next step")
    p.add_argument("goal_id", type=int)
    p.add_argument("--show", type=int, default=0, help="also print N chars of each message")
    p.set_defaults(fn=cmd_context)

    p = sub.add_parser("watch", help="watchdog daemon: keep goals running until done")
    p.add_argument("goal", type=int, nargs="?", help="watch only this goal id")
    p.add_argument("--interval", type=int, default=60, help="seconds between polls")
    p.add_argument("--max-attempts", type=int, default=3, help="max resumes per goal")
    p.add_argument("--reasoning-depth", type=int, default=None)
    p.add_argument("--include-paused", action="store_true",
                   help="also resume paused goals (default: active only)")
    p.add_argument("--once", action="store_true", help="single sweep, then exit")
    p.set_defaults(fn=cmd_watch)

    p = sub.add_parser("doctor", help="check postgres, ollama, models, memory")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("tools", help="list available tools")
    p.set_defaults(fn=cmd_tools)

    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]interrupted[/yellow]")
        return 130


if __name__ == "__main__":
    sys.exit(main())

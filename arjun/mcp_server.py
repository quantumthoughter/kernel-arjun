#!/usr/bin/env python3
"""Kernel-Arjun MCP server.

Exposes the durable-execution kernel to any MCP client (opencode, Claude
Desktop, etc.) so a host agent can launch, watch, resume, and score
long-horizon goals that outlive the conversation.

Run (stdio):
    python -m arjun.mcp_server

Register with opencode (opencode.json):
    {
      "mcp": {
        "kernel-arjun": {
          "type": "local",
          "command": ["/path/to/Kernel-Arjun/.venv/bin/python", "-m", "arjun.mcp_server"],
          "enabled": true,
          "environment": { "HIVE_API_KEY": "..." }
        }
      }
    }
"""
from __future__ import annotations

import json
import os
import sys

try:
    from mcp.server.mcpserver import MCPServer
except ModuleNotFoundError:
    sys.stderr.write(
        "The Kernel-Arjun MCP server needs the optional 'mcp' dependency.\n"
        "Install it with:  pip install 'kernel-arjun[mcp]'\n"
    )
    raise SystemExit(1)

from .sdk import Arjun, Backend

server = MCPServer(
    name="kernel-arjun",
    instructions=(
        "Durable-execution kernel for long-horizon AI agents. Use these tools to "
        "start goals that run for hours or days, inspect their ledger, score them, "
        "and resume them after a crash. State lives in Postgres, so a goal survives "
        "the process and the context window."
    ),
)

DEFAULT_DSN = os.environ.get("ARJUN_DSN", "host=127.0.0.1 port=5432 dbname=arjun user=quan_yin")


def _kernel(workspace: str, backend: str = "openai", depth: int | None = None,
            memory: bool = True) -> Arjun:
    return Arjun(
        workspace=workspace,
        backend=Backend(kind=backend),
        dsn=DEFAULT_DSN,
        reasoning_depth=depth,
        memory=memory,
        verbose=False,
    )


@server.tool(description="Start a long-horizon goal. Returns the goal id and initial status.")
def arjun_start(
    title: str,
    dod: str,
    workspace: str,
    max_tokens: int = 2_000_000,
    max_steps: int = 400,
    reasoning_depth: int = 2,
) -> str:
    k = _kernel(workspace, depth=reasoning_depth)
    g = k.goal(title, dod=dod, max_tokens=max_tokens, max_steps=max_steps)
    result = k.run(g)
    return json.dumps({
        "goal_id": g.id,
        "status": result.status,
        "words": result.meter.words,
        "tokens_used": result.meter.tokens_used,
        "tokens_pct": round(result.meter.tokens_pct, 1),
        "tasks_done": f"{result.meter.tasks_done}/{result.meter.tasks_total}",
        "escalations": result.meter.escalations,
    }, indent=2)


@server.tool(description="Create a goal WITHOUT running it. Returns the goal id.")
def arjun_create(
    title: str,
    dod: str,
    workspace: str,
    max_tokens: int = 2_000_000,
    max_steps: int = 400,
) -> str:
    k = _kernel(workspace)
    g = k.goal(title, dod=dod, max_tokens=max_tokens, max_steps=max_steps)
    return json.dumps({"goal_id": g.id, "status": "active"})


@server.tool(description="Run (or resume) a previously created goal to completion.")
def arjun_run(goal_id: int, workspace: str, reasoning_depth: int = 2) -> str:
    k = _kernel(workspace, depth=reasoning_depth)
    result = k.run(goal_id)
    return json.dumps({
        "goal_id": goal_id,
        "status": result.status,
        "words": result.meter.words,
        "tokens_used": result.meter.tokens_used,
        "escalations": result.meter.escalations,
    }, indent=2)


@server.tool(description="Resume a paused goal from its exact checkpoint.")
def arjun_resume(goal_id: int, workspace: str) -> str:
    k = _kernel(workspace)
    result = k.run(goal_id)
    return json.dumps({"goal_id": goal_id, "status": result.status,
                       "words": result.meter.words}, indent=2)


@server.tool(description="Score a goal: words, steps, tokens, escalations, first-pass.")
def arjun_meter(goal_id: int, workspace: str) -> str:
    k = _kernel(workspace)
    m = k.meter(goal_id)
    return json.dumps({
        "goal_id": goal_id, "words": m.words, "steps": m.steps,
        "tokens_used": m.tokens_used, "tokens_limit": m.tokens_limit,
        "tokens_pct": round(m.tokens_pct, 1), "escalations": m.escalations,
        "replans": m.replans, "first_pass": m.first_pass,
        "tasks_done": f"{m.tasks_done}/{m.tasks_total}",
    }, indent=2)


@server.tool(description="List goals and their statuses from the ledger.")
def arjun_list(workspace: str, limit: int = 20) -> str:
    k = _kernel(workspace)
    return json.dumps(k.list_goals(limit), indent=2, default=str)


@server.tool(description="Show the token anatomy of the context the next step will receive.")
def arjun_context(goal_id: int, workspace: str) -> str:
    k = _kernel(workspace)
    return json.dumps(k.context_anatomy(goal_id), indent=2)


@server.tool(description="Pause a running goal safely at its next checkpoint.")
def arjun_pause(goal_id: int, workspace: str) -> str:
    k = _kernel(workspace)
    k.pause(goal_id)
    return json.dumps({"goal_id": goal_id, "status": "paused"})


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()

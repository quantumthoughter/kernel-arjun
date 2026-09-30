#!/usr/bin/env python3
"""Kernel-Arjun SDK — quickstart demo.

Runs fully offline with a scripted ("fake") backend, so it costs nothing.
Swap Backend(kind="openai") and set HIVE_API_KEY to run for real.

    python examples/quickstart_sdk.py
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from arjun import Arjun, Backend
from arjun.sdk.verifiers import AllOf, word_count_gate


def main() -> None:
    ws = Path(tempfile.mkdtemp(prefix="arjun_sdk_"))
    print(f"workspace: {ws}\n")

    # A scripted model so the demo is free and deterministic.
    artifact = "A Salute to Arjuna\nJai Arjun\nJai Kālacakra\n"
    script = [
        json.dumps({"tasks": [
            {"title": "Write greeting", "detail": "create greeting.txt with a title and 3 lines"},
        ]}),
        json.dumps({"kind": "tool", "tool": "write_file",
                    "args": {"path": "greeting.txt", "content": artifact},
                    "note": "write the greeting"}),
        json.dumps({"kind": "finish", "note": "written",
                    "evidence": ["write_file reported 3 lines"]}),
    ]

    k = Arjun(
        workspace=str(ws),
        backend=Backend(kind="fake", script=script),
        verifier=AllOf(word_count_gate("greeting.txt", 3)),
        verbose=True,
    )

    goal = k.goal("SDK quickstart", dod="greeting.txt exists with a title and 3 lines",
                  max_tokens=20_000)
    print(f"\ncreated goal {goal.id}: {goal.title}")

    # live event stream (optional)
    print("\n--- event stream ---")
    for ev in k.watch(goal.id):
        print(f"  [{ev['kind']}] {ev['detail']}")

    result = k.result(goal.id)
    print("\n--- result ---")
    print(f"  status        : {result.status}")
    print(f"  tasks done    : {result.meter.tasks_done}/{result.meter.tasks_total}")
    print(f"  steps         : {result.meter.steps}")
    print(f"  tokens used   : {result.meter.tokens_used} ({result.meter.tokens_pct:.1f}%)")
    print(f"  escalations   : {result.meter.escalations}")

    print("\n--- the artifact ---")
    print((ws / "greeting.txt").read_text())

    print("--- context anatomy (proof it is assembled, not accumulated) ---")
    # create a fresh goal with a pending task to inspect
    g2 = k.goal("inspect me", dod="whatever")
    k.plan_tasks(g2, [{"title": "pending task", "detail": "do something"}])
    print(" ", k.context_anatomy(g2.id))

    shutil.rmtree(ws, ignore_errors=True)
    print("\nJai Arjun. 🏹")


if __name__ == "__main__":
    main()

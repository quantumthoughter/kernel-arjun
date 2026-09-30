#!/usr/bin/env python3
"""Naive single-conversation baseline for the dual experiment.

Condition B: one growing message list, "continue" prompts, no external ledger,
no independent verifier, no budget enforcement. Generous: it gets as many model
calls as the kernel took.

    HIVE_API_KEY=... python naive_runner.py --task-file task.md \
        --out ./run_naive --max-calls 100
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from arjun.models import OpenAIClient, ModelError  # noqa: E402

HIVE_URL = "https://api-cdn.thehive.ai/api/v3"
MODEL = "deepseek-ai/deepseek-v4.1-flash"


def extract_files(text: str) -> dict[str, str]:
    """Pull any 'FILE: path\\n```\\n...```' or fenced blocks labelled with a path."""
    files = {}
    # pattern: === path === then fenced block OR ## path then fenced block
    for m in re.finditer(r"(?:^|\n)(?:===\s*)?([\w./-]+\.(?:md|txt))\s*(?:===)?\s*\n```[a-z]*\n(.*?)```",
                         text, re.S):
        files[m.group(1)] = m.group(2)
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-calls", type=int, default=100)
    ap.add_argument("--max-tokens", type=int, default=32000)
    ap.add_argument("--temperature", type=float, default=0.6)
    args = ap.parse_args()

    client = OpenAIClient(HIVE_URL, os.environ.get("HIVE_API_KEY", ""), timeout=300)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    task = Path(args.task_file).read_text()

    messages = [
        {"role": "system", "content":
         "You are writing a long book. To save a file, output a block like:\n"
         "=== book/ch1.md ===\n```\n<contents>\n```\n"
         "Write one chapter per reply, then reply DONE when the whole book is complete."},
        {"role": "user", "content": task},
    ]

    log = {"calls": [], "files": [], "tokens_in": 0, "tokens_out": 0, "stopped": None}
    for i in range(args.max_calls):
        t0 = time.time()
        try:
            r = client.chat(MODEL, messages, json_mode=False,
                            temperature=args.temperature, max_tokens=args.max_tokens)
        except ModelError as e:
            log["stopped"] = f"model error at call {i}: {e}"
            break
        log["tokens_in"] += r.tokens_in
        log["tokens_out"] += r.tokens_out
        content = r.content or ""
        # persist any files the model emitted
        files = extract_files(content)
        for path, body in files.items():
            p = out / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
            log["files"].append(path)
        log["calls"].append({"i": i, "out_tokens": r.tokens_out,
                             "files": list(files), "secs": round(time.time() - t0, 1)})
        print(f"  call {i}: out={r.tokens_out} tok, files={list(files)}")

        # continue the conversation
        messages.append({"role": "assistant", "content": content})
        if "DONE" in content and len(files) == 0:
            log["stopped"] = f"model said DONE at call {i}"
            break
        messages.append({"role": "user", "content":
                         "Continue with the next chapter. If everything is complete, reply DONE."})
        # naive: no compaction, no budget — the context simply grows

    (out / "_naive_log.json").write_text(json.dumps(log, indent=2))
    print(f"\nnaive: {len(log['calls'])} calls, "
          f"{log['tokens_in']}+{log['tokens_out']} tokens, "
          f"{len(log['files'])} files, stopped: {log['stopped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

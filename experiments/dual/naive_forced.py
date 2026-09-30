#!/usr/bin/env python3
"""Charitable naive baseline: force the model to write each chapter, one at a
time, in ONE growing conversation — no external ledger, no verifier, no budgets.

This is the strongest naive condition: we do not let it quit early. It keeps the
whole transcript in context and is re-prompted for each chapter until done or the
call budget is exhausted. If even THIS degrades, the thesis is robust.

    HIVE_API_KEY=... python naive_forced.py --out ./run_naive_forced --chapters 10
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
from arjun.models import ModelError, OpenAIClient  # noqa: E402

HIVE_URL = "https://api-cdn.thehive.ai/api/v3"
MODEL = "deepseek-ai/deepseek-v4.1-flash"
MIN_WORDS = 1500


def extract_file(text: str) -> str | None:
    m = re.search(r"```[a-z]*\n(.*?)```", text, re.S)
    return m.group(1) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--chapters", type=int, default=10)
    ap.add_argument("--max-tokens", type=int, default=32000)
    args = ap.parse_args()

    client = OpenAIClient(HIVE_URL, os.environ.get("HIVE_API_KEY", ""), timeout=300)
    out = Path(args.out)
    (out / "book").mkdir(parents=True, exist_ok=True)

    messages = [
        {"role": "system", "content":
         "You are writing a book one chapter at a time. For each chapter, output a markdown "
         "code block containing the FULL chapter text (at least 1500 words). Output only the "
         "chapter text in the code block; no commentary."},
    ]
    log = {"calls": [], "tokens_in": 0, "tokens_out": 0}
    for i in range(1, args.chapters + 1):
        prompt = (f"Write chapter {i} of 'The Long Horizon' (at least {MIN_WORDS} words), "
                  f"in first person, poetic-technical. It must use these terms somewhere: "
                  f"durable ledger, context assembly, the verifier is never the doer, "
                  f"budgets are law, checkpoint, resume.")
        messages.append({"role": "user", "content": prompt})
        t0 = time.time()
        try:
            r = client.chat(MODEL, messages, json_mode=False, max_tokens=args.max_tokens)
        except ModelError as e:
            log["calls"].append({"chapter": i, "error": str(e)})
            break
        log["tokens_in"] += r.tokens_in
        log["tokens_out"] += r.tokens_out
        body = extract_file(r.content or "") or (r.content or "")
        (out / "book" / f"{i:02d}_chapter.md").write_text(body)
        wc = len(body.split())
        log["calls"].append({"chapter": i, "words": wc, "out_tokens": r.tokens_out,
                             "context_tokens": r.tokens_in, "secs": round(time.time() - t0, 1)})
        print(f"  ch {i}: {wc} words, context={r.tokens_in} tok")
        messages.append({"role": "assistant", "content": r.content})
        # naive: the entire book so far stays in the context and keeps growing

    (out / "_naive_log.json").write_text(json.dumps(log, indent=2))
    print(f"\nnaive_forced: {len(log['calls'])} calls, {log['tokens_in']}+{log['tokens_out']} tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())

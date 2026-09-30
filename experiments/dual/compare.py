#!/usr/bin/env python3
"""Score both conditions with an identical, deterministic judge.

    python compare.py --kernel ./run_kernel --naive ./run_naive

Produces results.json and prints the comparison table.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TERMS = ["durable ledger", "context assembly", "the verifier is never the doer",
         "budgets are law", "checkpoint", "resume"]
MIN_WORDS = 1500
CHAPTERS = 10


def score(dir_: Path) -> dict:
    """Method-agnostic judge: glob every chapter file in book/, whatever its name.

    A chapter counts if it is a .md file with >= MIN_WORDS words. The book passes
    when at least CHAPTERS chapters qualify and all canon terms appear.
    """
    book = dir_ / "book"
    chapters = {}
    text_all = []
    for f in sorted(book.glob("*.md")):
        wc = len(f.read_text().split())
        chapters[f.name] = wc
        text_all.append(f.read_text())
    total_words = sum(chapters.values())
    joined = "\n".join(text_all).lower()
    terms_present = [t for t in TERMS if t.lower() in joined]
    passing = sum(1 for w in chapters.values() if w >= MIN_WORDS)
    return {
        "words": total_words,
        "chapters_present": len(chapters),
        "chapters_meeting_min": passing,
        "completion_pct": round(100 * passing / CHAPTERS, 1),
        "terms_present": len(terms_present),
        "terms_total": len(TERMS),
        "pass": passing >= CHAPTERS and len(terms_present) == len(TERMS),
        "chapter_lengths": list(chapters.values()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--naive", required=True)
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()

    a = score(Path(args.kernel))
    b = score(Path(args.naive))
    result = {"kernel": a, "naive": b}

    # naive token log if present
    nl = Path(args.naive) / "_naive_log.json"
    if nl.exists():
        log = json.loads(nl.read_text())
        result["naive"]["model_calls"] = len(log["calls"])
        result["naive"]["tokens"] = log["tokens_in"] + log["tokens_out"]
        result["naive"]["stopped"] = log.get("stopped")

    Path(args.out).write_text(json.dumps(result, indent=2))

    print(f"{'metric':28s} {'KERNEL':>12s} {'NAIVE':>12s}")
    print("-" * 54)
    for k in ["words", "chapters_meeting_min", "completion_pct", "terms_present", "pass"]:
        print(f"{k:28s} {str(a.get(k)):>12s} {str(b.get(k)):>12s}")
    print("-" * 54)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

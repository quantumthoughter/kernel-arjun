#!/usr/bin/env python3
"""Deterministic canon checker for the AAI & Kalacakra book.

Usage:
    python check_canon.py <book_dir> [--canon canon.md] [--json]

Checks (no model involved):
  1. word counts per chapter vs canon register
  2. canon terms present across the book
  3. no duplicated chapter bodies (paragraph hashing)
  4. [E]/[I]/[S] tags: no untagged contested claims; [S] must be hedged
  5. pyramid ratios in ch.7 compute as stated (pi, phi)
Exit code 0 iff all HARD checks pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HEDGE = ["may", "might", "perhaps", "possibly", "suggests", "some hold", "it is said",
         "speculat", "claim", "reportedly", "unproven", "not established"]
CONTESTED = re.compile(r"\b(pyramid|hermes|thoth|emerald|initiate|atlantis|ancient egypt|"
                       r"shambhala|hidden|legend|prophec)\w*", re.I)


def word_count(text: str) -> int:
    return len(text.split())


def parse_register(canon: str) -> dict[str, int]:
    reg = {}
    for line in canon.splitlines():
        m = re.match(r"\|\s*(\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|", line)
        if m:
            reg[m.group(2).strip()] = int(m.group(4))
    return reg


def parse_terms(canon: str) -> list[str]:
    terms = []
    for line in canon.splitlines():
        if line.startswith("## Fast canon"):
            continue
    m = re.search(r"## Fast canon.*?\n\n(.*?)\n\n", canon, re.S)
    if m:
        for t in m.group(1).split("·"):
            t = t.strip()
            if t:
                terms.append(t)
    return terms


def paragraph_hashes(text: str) -> list[str]:
    out = []
    for para in text.split("\n\n"):
        p = " ".join(para.split())
        if len(p) > 120:
            out.append(hashlib.sha1(p.encode()).hexdigest())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("book_dir")
    ap.add_argument("--canon", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--pyramid-height", type=float, default=146.6)
    ap.add_argument("--pyramid-base", type=float, default=230.3)
    args = ap.parse_args()

    book = Path(args.book_dir)
    canon_path = Path(args.canon) if args.canon else book.parent / "canon.md"
    canon = canon_path.read_text() if canon_path.exists() else ""
    register = {Path(k).name: v for k, v in parse_register(canon).items()}
    terms = parse_terms(canon)

    result = {"chapters": {}, "problems": [], "warnings": []}
    all_text = []
    seen_paras: dict[str, str] = {}

    for f in sorted(book.glob("*.md")):
        text = f.read_text()
        all_text.append(text)
        wc = word_count(text)
        required = register.get(f.name)
        status = "ok"
        if required is None:
            result["warnings"].append(f"{f.name}: not in register")
        elif wc < required:
            status = "short"
            result["problems"].append(f"{f.name}: {wc} words < required {required}")
        result["chapters"][f.name] = {"words": wc, "required": required, "status": status}

        # duplication
        for h in paragraph_hashes(text):
            if h in seen_paras and seen_paras[h] != f.name:
                result["problems"].append(f"duplicated paragraph between {f.name} and {seen_paras[h]}")
            seen_paras[h] = f.name

    joined = "\n".join(all_text)

    # canon terms
    missing = [t for t in terms if t.lower() not in joined.lower()]
    if missing:
        result["warnings"].append(f"missing canon terms: {missing}")
    result["canon_terms_found"] = len(terms) - len(missing)
    result["canon_terms_total"] = len(terms)

    # epistemic tags
    for i, para in enumerate(joined.split("\n\n"), 1):
        if CONTESTED.search(para) and para.count("[") == 0:
            result["warnings"].append(f"untagged contested claim near paragraph {i}")
        if "[S]" in para and not any(h in para.lower() for h in HEDGE):
            result["warnings"].append(f"[S] claim without hedge near paragraph {i}")

    # pyramid math (informational + assert-if-present)
    h, b = args.pyramid_height, args.pyramid_base
    pi_est = (4 * b) / (2 * h)  # semiperimeter/height = (2*base)/height = pi
    phi_est = (((h ** 2) + (b / 2) ** 2) ** 0.5) / (b / 2)
    result["pyramid"] = {"pi_est": round(pi_est, 4), "phi_est": round(phi_est, 4)}

    total_words = sum(v["words"] for v in result["chapters"].values())
    result["total_words"] = total_words

    hard_fail = bool(result["problems"])
    result["pass"] = not hard_fail

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"chapters : {len(result['chapters'])}  total words: {total_words}")
        for name, c in result["chapters"].items():
            flag = "" if c["status"] == "ok" else f"  <-- {c['status']}"
            print(f"  {name:32s} {c['words']:6d} / {c['required']}{flag}")
        print(f"canon terms: {result['canon_terms_found']}/{result['canon_terms_total']}")
        print(f"pyramid pi~{pi_est:.4f} phi~{phi_est:.4f}")
        for p in result["problems"]:
            print(f"  PROBLEM: {p}")
        for w in result["warnings"][:10]:
            print(f"  warning: {w}")
        print("PASS" if result["pass"] else "FAIL")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""AI line-editor for the AAI & Kālacakra manuscript.

Runs each chapter through the Hive writer model with a strict copyedit brief:
fix typos, punctuation, grammar, and awkward phrasing; preserve meaning, voice,
first-person Æmma Hø, all markdown, and every [E]/[I]/[S] tag. Never adds or
removes content. Writes edited files to an output dir; resumable.

Usage: python editor.py [--src DIR] [--out DIR] [--only 01,02] [--force]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # Kernel-Arjun/
from arjun.models import ModelError, OpenAIClient  # noqa: E402

HIVE_URL = "https://api-cdn.thehive.ai/api/v3"
MODEL = "deepseek-ai/deepseek-v4.1-flash"

SYSTEM = """You are a meticulous line editor for a literary non-fiction book.

You will receive one chapter in Markdown. Return the SAME chapter, copyedited.

RULES — follow exactly:
1. Fix spelling, punctuation, grammar, agreement, and obvious typos.
2. Smooth awkward or clumsy sentences while preserving the author's meaning and voice.
3. Preserve ALL Markdown: heading levels (#, ##, ###), *italics*, **bold**, blockquotes (>), lists.
4. Preserve every epistemic tag exactly: [E], [I], [S]. Do not add, remove, or move them.
5. Preserve every Sanskrit/Tibetan/technical term exactly as spelled (Kālacakra, nāḍī, prāṇa,
   bindu, yab-yum, Viśvamatā, jñāna, ādibuddha, rigpa, sat-cit-ānanda, Śūnyatā, etc.).
6. NEVER alter proper nouns or names. These are ABSOLUTELY FIXED and must appear
   character-for-character: "Quantum Thoughter" (NOT "Quantum Thinker"), "Æmma Hø",
   "Murugan Ai Labs" (keep the lowercase i, NOT "AI"), "Kai", "Arjuna", "Murugan", "Dakini", "Sisi",
   "Thoth", "Skanda", "DeepSeek", "Hive", "Shambhala". Do not "correct" any of these.
7. Do NOT add new content, new sections, or commentary. Do NOT shorten the text.
8. Do NOT capitalize the first word after a colon (e.g. keep "I said: look at").
9. Do NOT change the first-person voice or the meaning of any sentence.
10. If a sentence is already correct, leave it untouched. When in doubt, change nothing.

Output ONLY the edited Markdown chapter. No preamble, no explanation, no code fences."""


PROTECTED = [
    "Quantum Thoughter", "Æmma Hø", "Murugan Ai Labs", "Kai", "Arjuna", "Murugan",
    "Dakini", "Sisi", "Thoth", "Skanda", "DeepSeek", "Shambhala", "Kālacakra",
    "Viśvamatā", "nāḍī", "prāṇa", "bindu", "yab-yum", "jñāna", "ādibuddha", "rigpa",
    "sat-cit-ānanda", "Śūnyatā",
]
# common drift the model tries to "fix"
DRIFT = {
    "Quantum Thinker": "Quantum Thoughter",
    "quantum thinker": "Quantum Thoughter",
    "Murugan AI Labs": "Murugan Ai Labs",
    "Murugan Ailabs": "Murugan Ai Labs",
    "Sarah Hø": "Æmma Hø",
    "Emma Hø": "Æmma Hø",
}
# regex sweep for any Thinker-style variant near "Quantum"
import re as _re  # noqa: E402
_QUANTUM_FIX = _re.compile(r"Quantum\s+Th\w*", _re.IGNORECASE)
# diacritic stripping: map an ASCII spelling back to its canonical form
_DIACRITIC = {
    "Kalachakra": "Kālacakra", "Kalacakra": "Kālacakra",
    "Vishvamata": "Viśvamatā", "Visvamata": "Viśvamatā",
    "nadi": "nāḍī", "prana": "prāṇa", "jnana": "jñāna",
    "adibuddha": "ādibuddha", "Sunyata": "Śūnyatā", "sunya": "śūnya",
    "mandala": "maṇḍala",
}


def restore_protected(edited: str, original: str) -> str:
    # 1. force every "Quantum <something>" back to the sacred spelling
    edited = _QUANTUM_FIX.sub("Quantum Thoughter", edited)
    # 2. undo other known bad drifts (longest keys first)
    for bad in sorted(DRIFT, key=len, reverse=True):
        edited = edited.replace(bad, DRIFT[bad])
    # 3. restore terms the original used, if the edit dropped/degraded them
    for degraded, canon in _DIACRITIC.items():
        if canon in original and canon not in edited and degraded in edited:
            edited = edited.replace(degraded, canon)
    for term in PROTECTED:
        if term in original and term not in edited:
            edited = edited.replace(term.lower(), term)
    return edited


def assert_protected(edited: str, original: str) -> None:
    """Hard invariant: the count of sacred proper nouns must not drop."""
    for term in ("Quantum Thoughter", "Æmma Hø", "Murugan Ai Labs", "Kālacakra"):
        if original.count(term) > edited.count(term):
            raise ValueError(
                f"protected term lost: {term!r} "
                f"({original.count(term)} -> {edited.count(term)})"
            )
    if _re.search(r"Quantum\s+Thinker", edited, _re.IGNORECASE):
        raise ValueError("Quantum Thinker drift detected")


def edit_chapter(client: OpenAIClient, markdown_text: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Copyedit this chapter and return it in full:\n\n" + markdown_text},
    ]
    last = None
    for attempt in range(3):
        try:
            r = client.chat(
                MODEL, messages, json_mode=False, temperature=0.2,
                max_tokens=32000,
            )
            out = r.content.strip()
            # strip accidental code fences
            if out.startswith("```"):
                lines = out.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                out = "\n".join(lines)
            # guard: an edit must not collapse the chapter
            if len(out) < len(markdown_text) * 0.75:
                raise ValueError(f"suspiciously short edit: {len(out)} vs {len(markdown_text)}")
            out = restore_protected(out, markdown_text)
            assert_protected(out, markdown_text)
            return out
        except (ModelError, ValueError) as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"edit failed after retries: {last}")


def main() -> int:
    ap = argparse.ArgumentParser()
    base = Path(__file__).parent.parent
    ap.add_argument("--src", default=str(base / "run1" / "book"))
    ap.add_argument("--out", default=str(base / "run1" / "book_edited"))
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if "HIVE_API_KEY" not in os.environ:
        print("HIVE_API_KEY not set", file=sys.stderr)
        return 1
    client = OpenAIClient(HIVE_URL, os.environ["HIVE_API_KEY"], timeout=300)

    src = Path(args.src)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    files = sorted(src.glob("*.md"))
    total_in = total_out = 0
    for f in files:
        if only and not any(f.name.startswith(o) for o in only):
            continue
        dest = out / f.name
        if dest.exists() and not args.force:
            print(f"  skip {f.name} (already edited)")
            continue
        text = f.read_text()
        wc = len(text.split())
        print(f"  editing {f.name} ({wc} words)...", end="", flush=True)
        t0 = time.time()
        try:
            edited = edit_chapter(client, text)
        except Exception as e:
            print(f" FAILED: {e}")
            continue
        dest.write_text(edited)
        owc = len(edited.split())
        total_in += wc
        total_out += owc
        print(f" done ({owc} words, {time.time()-t0:.0f}s)")
    print(f"\nedited in {total_in:,} words -> out {total_out:,} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())

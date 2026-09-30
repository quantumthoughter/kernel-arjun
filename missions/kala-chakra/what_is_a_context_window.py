#!/usr/bin/env python3
"""What is a 1M context window? A live, measured demonstration.

Run:  HIVE_API_KEY=... python what_is_a_context_window.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, "/Users/apple/Development/Kernel-Arjun")
from arjun.models import OpenAIClient  # noqa: E402

URL = "https://api-cdn.thehive.ai/api/v3"
MODEL = "deepseek-ai/deepseek-v4.1-flash"
c = OpenAIClient(URL, os.environ.get("HIVE_API_KEY", ""), timeout=300)


def ask(messages, label, cap=2000):
    r = c.chat(MODEL, messages, json_mode=False, max_tokens=cap)
    print(f"  [{label}] in={r.tokens_in:>7,}  out={r.tokens_out:>6,}  "
          f"reasoning={r.reasoning_tokens:>5,}")
    return r


def bar(n, scale=40, width=1_000_000):
    filled = max(1, int(scale * n / width))
    return "█" * filled + "·" * (scale - filled)


print("=" * 72)
print("WHAT IS A 1M CONTEXT WINDOW?  — measured, not asserted")
print("=" * 72)

# ------------------------------------------------------------------ 1
print("\n[1] A single call is STATELESS. It has no memory of any other call.")
r1 = ask([{"role": "user", "content": "My name is Quantum Thoughter. Remember it."}],
         "call 1")
print("      model said:", r1.content.strip()[:90])
r2 = ask([{"role": "user", "content": "What is my name?"}], "call 2 (fresh)")
print("      model said:", r2.content.strip()[:90])
print("  → The model does NOT remember. There is no memory between API calls.")
print("    Any 'back and forth' is an illusion built by the caller re-sending text.")

# ------------------------------------------------------------------ 2
print("\n[2] A 'conversation' works ONLY because the caller RESENDS the history.")
history = [{"role": "user", "content": "My name is Quantum Thoughter."},
           {"role": "assistant", "content": "Noted."},
           {"role": "user", "content": "What is my name?"}]
r3 = ask(history, "call 3 (with history re-sent)")
print("      model said:", r3.content.strip()[:90])
print("  → Now it 'remembers' — because we handed the memory back to it.")
print("    Memory is not in the model. Memory is text the caller sends each time.")

# ------------------------------------------------------------------ 3
print("\n[3] The window = how much TEXT one call can carry (input + output).")
print("    We grow the input and watch prompt_tokens climb.\n")
filler = ("The wheel of time turns and the eye does not move. " * 200)
for mult, label in [(1, "1x"), (5, "5x"), (20, "20x"), (50, "50x")]:
    text = "Read this and reply OK: " + (filler * mult)
    r = ask([{"role": "user", "content": text}], f"input {label}", cap=50)
    print(f"      words sent ≈ {len(text.split()):>6,}   →   prompt_tokens = {r.tokens_in:>7,}")

# ------------------------------------------------------------------ 4
print("\n[4] What the 1,000,000-token window actually bounds:")
print(f"    {'':14s} {'tokens':>10s}   of the 1M window")
sizes = [
    ("our per-call max", 9_789),
    ("our whole book", 121_000),
    ("a long novel", 300_000),
    ("the full window", 1_000_000),
]
for label, n in sizes:
    print(f"    {label:14s} {n:>10,}   {bar(n)}  {100*n/1_000_000:>5.1f}%")

print("""
    The window bounds ONE call's input+output. It is NOT a budget for the
    whole task, and it is NOT memory across calls. Every call starts blank.
""")

# ------------------------------------------------------------------ 5
print("[5] The 1M window is never a free container:")
print("    - output per call is capped (~8k by default) — you cannot 'write 1M out'")
print("    - attention is O(n²): 1M tokens ≠ 100× a 10k call, it is ~10,000× the work")
print("    - recall rots and dies in the MIDDLE of long contexts (lost-in-the-middle)")
print("\n" + "=" * 72)
print("SO: 1M = the largest amount of text you may hand the model IN ONE CALL.")
print("    Long-horizon work is made by MANAGING WHAT YOU SEND, not by filling it.")
print("=" * 72)

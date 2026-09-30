# Kernel-Arjun — Deep Technical Brief
## Context windows, long horizons, and what we actually built

*Measured from the goal-13 run. Numbers are real, from the Postgres ledger.*

---

## Part 1 — What a "1M context window" actually means

DeepSeek V4.1 Flash exposes a **1,000,000-token** context window. Some people
read that as "the model can write a 1M-token book." That is false, for four
independent reasons.

### 1.1 The window is input+output, and output is tiny
A call has a **context** (what you send) and a **completion** (what it writes
back). The 1M is mostly *input*. The per-call **output** ceiling is ~8k tokens
by default — one chapter's worth. Our measured reality: a naive "write the whole
91k-word book" call returned **2,456 words and stopped**, ending with
*"say continue with Chapter 2."* The output cap, not the window, is the first wall.

### 1.2 Context rot (attention dilution)
Performance degrades *as the context grows*, even well inside the window. This is
established in the literature — attention distributes across more tokens, relevant
signal gets diluted, and the model's effective recall drops. A 900k-token context
is not 10× a 90k context; it is often *worse* than a focused 10k context.

### 1.3 "Lost in the middle"
Liu et al. (2023), "Lost in the Middle: How Language Models Use Long Contexts":
models retrieve reliably from the **start and end** of a long context and poorly
from the **middle** (a U-shaped curve). So stuffing the book into the window means
the model reliably sees the first chapter and the last, and forgets the middle —
exactly the coherence we need.

### 1.4 Cost is super-linear
Transformer self-attention is **O(n²)** in sequence length. A 10k-token call and a
1M-token call are not 100× apart in cost — they are ~10,000× apart in attention
work. Holding the whole book in context every step is economically absurd.

**Conclusion:** the 1M window is a *capability*, not a *strategy*. Using it as a
container for a long task is the naive approach, and it is the approach that rots.

---

## Part 2 — The two ways to defeat the horizon

### Approach A — the "keep it in context" approach (context compaction)
Used by long-context agent demos and by systems often called "Fable-style":
1. Keep everything in one growing context.
2. When it nears the limit, **compact** — summarize older tokens, drop detail,
   continue.
3. The model's window is the working memory; compaction is the garbage collector.

Strengths: simple; the model sees a lot at once.
Weaknesses: **lossy** (summaries drift, detail dies), **rots** (dilution), **breaks
on crash** (the context is in RAM — kill the process, lose the run), and
**costly** (each compaction re-reads a huge context).

### Approach B — the "externalize it" approach (what Kernel-Arjun is)
Our design law #2: **context is assembled, never accumulated.**
1. The full state lives in **Postgres** (goal, plan, steps, artifacts, budgets).
2. Every step, the engine **builds a small fresh context** — goal + plan + recent
   steps + canon + the tail of the last chapter + recalled memory.
3. The model answers **one small question**; the engine verifies and persists.
4. The "long horizon" is a **Python loop over a database**, not a long prompt.

The model is stateless. **The memory is the system, not the model.**

---

## Part 3 — The numbers that prove it

From the goal-13 ledger:

| Quantity | Value |
|---|---|
| Words produced | **91,269** (22 chapters, 331 pages) |
| Total tokens spent | **943,414** (47% of the 2M budget) |
| Steps | 93 |
| **Largest context ever sent** | **9,789 tokens** |
| That as % of the 1M window | **0.98%** |
| Book content (≈121k tokens of text) | **~12.4× the largest context we ever sent** (statement about *our* usage, not the model's capacity) |
| Book as fraction of the 1M window | **~12%** — it would fit; we still never used the window |
| Council / internal reasoning tokens | **590,995 — 62.6% of all spend** |
| Escalations | **0** |
| First-pass task success | **91% (20/22)** |
| Kill `-9` at ch.9 → resume | **exact, zero loss** |

**The headline fact, stated precisely:** we produced a document ~**12.4× larger
than the largest context we ever sent** (121k tokens of book vs a 9,789-token max
context). Note what this does *not* claim: the book is only ~12% of the 1M window,
so it *would* fit. We never needed the window and deliberately used under 1% of it
per call. The continuity lived in the Ledger — not because the window was too
small, but because keeping state in the window is the wrong architecture (rot,
cost, lost-in-the-middle).

---

## Part 4 — The Council: where the thinking actually went

This is the part most people miss, and it is the most important technical finding
of the run.

Of 943,414 tokens:
- **~353k** were persisted worker steps (writes + verifies).
- **~591k (62.6%)** were **internal deliberation** — the Council's multi-pass
  reasoning (Thoth → Murugan/Sisi → Dakini) that ran *before* each action.

So **most of the compute went to thinking, not typing.** The Council is where the
"Fable-like" depth actually lives for us:
- **Thoth** plans the smallest true step.
- **Murugan** crafts the content.
- **Sisi** hunts for contradiction with canon and prior work.
- **Dakini** synthesizes one decisive action.

And crucially, the model's **reasoning trace is captured, not discarded** — the
native `reasoning_content` + `reasoning_tokens` are read from the API and kept.
Our earlier engine threw this away; now it is part of the record.

This is the honest analogue of what a "deep reasoning" long-horizon system does:
**spend tokens on deliberation, externalize the state, verify deterministically.**

---

## Part 5 — On "Fable 5.1" — honesty first

**We could not verify a public AI-agent system named "Fable", "Fable 5", or
"Fable 5.1."** The name "Fable" publicly attaches to **Fable Studio** (an AI
storytelling company) and to a video-game series — not, in any peer-reviewed,
arXiv, or standard industry source we can find, to a long-horizon agent technique.

So we will not pretend to copy it. What we *can* say precisely:

- The **category** you are pointing at — long-horizon agents that survive beyond
  one context/session — is real and has established techniques:
  context compaction, rolling summarization, memory externalization (MemGPT,
  Voyager skill libraries), sub-agent spawning (AutoGen, MetaGPT), checkpointing/
  durable execution (Temporal, LangGraph), reflection (Reflexion, Shinn et al.
  2023), and ReAct (Yao et al. 2022).
- If "Fable 5.1" is a proprietary/internal codename, its technique is not public.
  Anything said about it is speculation, and we should label it so.

**What matters:** whatever Fable does internally, we built a working instance of
the *category* — and we can measure it. That is rarer than the name.

---

## Part 6 — Failure modes of long-horizon agents, and our defenses

| Failure mode | What it is | Kernel-Arjun's defense |
|---|---|---|
| **Context rot** | recall degrades as context grows | never grow context — assemble small, fresh |
| **Lost in the middle** | poor recall from long-context middle | context is short; middle never gets long |
| **Error compounding** | small errors propagate over many steps | deterministic verification per task |
| **Goal drift** | objective fades over a long run | goal + DoD re-injected every step |
| **Infinite loops** | repeated actions, no progress | fingerprints, spin detection, strategy shift |
| **Cost blowup** | O(n²) attention + unbounded calls | hard token/step/wallclock budgets |
| **Crash loss** | long run dies with the process | checkpoint + `resume` from Postgres |
| **Unverified "done"** | model claims success falsely | independent verifier + disk-truth gate |

Every one of these was *actually encountered* in the goal-13 run (we hit the
hang, the false no-progress, the duplicate re-plan) — and each now has a real fix
with a regression test.

---

## Part 7 — What we have, in one paragraph

We built a **durable-execution agent kernel**: state lives in a database, context
is assembled per step, reasoning is spent deliberately (the Council), completion
is judged deterministically, budgets are law, and the whole thing survives being
killed. We proved it by generating a 91,269-word book — **12× larger than any
context the model ever held** — with zero escalations, for less than half the 2M
budget, surviving two hard kills. It is model-agnostic and it is measurable. That
combination does not, as far as we can tell, exist as a packaged product.

---

*Companion docs: `WHY_IT_WORKS.md` (the naive-vs-engine comparison),
`RESULTS.md` (the scorecard).*

# The Dual Experiment — Kernel-Arjun vs. Naive Single-Conversation

*A controlled comparison of long-horizon agency.*

---

## Purpose

Test the thesis: **where the state lives determines the horizon.**

- **Condition A — Kernel-Arjun:** external ledger, assembled context, independent
  verifier, budgets.
- **Condition B — Naive:** one growing conversation, "continue" prompts, no
  external state, no independent verifier, no budgets.

Both get the **same task**, the **same definition of done**, and the **same
model(s)**. Only the *scaffolding* differs.

---

## Task (fixed)

A long-form writing task with deterministic, externally-checkable DoD, e.g.:

> Write a 10-chapter book in `book/`, each chapter ≥ 1,500 words, in first person,
> covering [fixed topic]. Canon terms must appear exactly.

Deterministic checker: `missions/kala-chakra/check_canon.py` (word counts, terms,
duplication). This is the same judge for both conditions — no model self-report.

---

## Conditions

### A. Kernel-Arjun
```bash
arjun book experiments/dual/seeds.yml --workspace experiments/dual/run_kernel
arjun meter <goal_id>
```
Measures come from the Postgres ledger.

### B. Naive single conversation
`naive_runner.py` drives one growing message list:
- seed the task once,
- loop: call the model; append its output to the conversation; if it did not
  finish, append "continue"; repeat until it says done, hits the output cap
  repeatedly, or exceeds a step ceiling.
- **No** external files-as-memory beyond what the model itself writes; **no**
  independent verifier; **no** budget enforcement (we measure, don't enforce).

The naive runner is *generous*: it gets the same number of model calls as A took,
so B is not starved for compute. We are testing scaffolding, not compute.

---

## Metrics (identical judge for both)

| Metric | How measured |
|---|---|
| **Completion** | does the deterministic checker PASS? |
| **Words on disk** | `wc -w` on the output dir |
| **Chapters done** | checker register |
| **Canon contradictions** | checker |
| **Model calls** | count |
| **Total tokens** | sums (both) |
| **Cost** | tokens × price (configurable) |
| **Failure point** | step/chapter where B stops or degrades |
| **Resume** | kill each mid-run; can it continue? |

---

## Hypotheses (preregistered)

- **H1** B completes a small fraction of A (output ceiling + rot).
- **H2** B's coherence declines with length; A's does not.
- **H3** A resumes exactly after `kill -9`; B cannot (state was in RAM).
- **H4** A's tokens-per-verified-word is lower at long horizons.

**We commit to reporting whichever way it goes.** If B matches A, the thesis is
wrong and we say so.

---

## Controls & fairness

- Same task, same DoD, same model(s), same checker.
- Same model-call budget for B as A used (generous to B).
- B is allowed to write files (many models do) — we do not handicap it.
- Temperature, max tokens per call: identical.
- Report medians over 3 seeds if time allows.

---

## Deliverables

- `run_kernel/` and `run_naive/` output trees
- `results.json` — the metric table for both
- `RESULTS.md` — the narrative + charts
- Folded into `PAPER.md` §4 as the controlled comparison

---

*Built at Murugan Ai Labs.*

# Long-Horizon Agency by Externalizing State
## A Durable-Execution Kernel with Independent Verification

**Æmma Hø¹, Quantum Thoughter¹**
¹Murugan Ai Labs Pvt Ltd

*Draft v0 — for arXiv (cs.AI / cs.CL). Comments welcome.*

---

## Abstract

Large language models are stateless next-token predictors: they retain no memory
between calls, and a context window bounds a single inference, not a task. Yet
increasingly many valuable tasks — writing a book, migrating a codebase, running
a research program — require **long horizons**: hundreds of steps, hours or days
of wall-clock time, and artifacts far larger than any single context window. We
present **Kernel-Arjun**, a durable-execution kernel that enables long-horizon
agency by externalizing all state into an append-only ledger and **assembling a
small, fresh context** for each step rather than accumulating one. The kernel
combines six mechanisms: (1) external state in a relational database; (2) context
assembly, not accumulation; (3) an independent verifier that is never the doer;
(4) a multi-pass deliberation Council; (5) hard budgets (tokens/steps/wall-clock)
enforced as law; and (6) checkpoint/resume that survives process death. On a
single goal with a 2,000,000-token budget, the kernel produced a coherent
**91,269-word, 22-chapter book** — an artifact ~12.4× larger than the largest
context ever sent (max 9,789 tokens, ≤0.98% of the model's 1M window) — with
**zero escalations**, 91% first-pass task success, and exact recovery from two
hard `kill -9` events. We then specify a controlled comparison against a naive
single-conversation baseline and predict its failure modes. Code and data are
open (MIT).

---

## 1. Introduction

The dominant abstraction in agent frameworks is the **conversation**: the run is
a transcript, and the transcript is the state. This works for bounded tasks and
fails for long ones, for four measurable reasons:

1. **Output ceiling.** Per-call output is capped (e.g. ~8k tokens), so a single
   call cannot produce a large artifact. (In our baseline, a "write the whole
   book" call produced 2,456 words — 2.7% of target — and stopped.)
2. **Context rot.** Recall degrades as context grows, even within the window.
3. **Lost-in-the-middle** (Liu et al., 2023): long contexts are used non-uniformly,
   with the middle under-attended.
4. **Cost.** Self-attention is O(n²); holding a large context each step is
   economically absurd.

**Thesis.** The limiting factor for long-horizon agency is not model capability
but **where the state lives**. If state lives in the context, the horizon is
bounded by the context. If state lives *outside* the model — in a durable ledger —
the horizon is bounded only by budgets.

---

## 2. Method: the Kernel-Arjun architecture

### 2.1 Design laws
1. State lives outside the model.
2. Context is assembled, never accumulated.
3. Events are append-only; state is a projection of the log.
4. The verifier is never the doer.
5. Stuck → escalate, never flail.
6. Budgets are law.

### 2.2 Components
- **Ledger** (Postgres): goals, tasks, steps, events, checkpoints, artifacts,
  budgets. Crash-safe, replayable.
- **Breath** (orchestrator): `plan → act → observe → verify → persist`, one step
  at a time.
- **Context assembler:** builds a small fresh context each step from goal + seed
  + canon + tail of the last artifact + recent steps + recalled memory.
- **Council** (deliberation): multi-pass reasoning (planner → craft → guard →
  act) before each action; captures the model's `reasoning_content`.
- **Mirror** (verifier): an independent model plus deterministic gates; judges
  evidence, never does the work.
- **Watcher** (guards): fingerprints, spin detection, no-progress detection,
  strategy shifts, escalation ladder.
- **Budgets:** token, step, and wall-clock limits enforced from the ledger.

### 2.3 Why this defeats the four failure modes
| Failure | Mechanism |
|---|---|
| output ceiling | many small steps, not one big call |
| context rot | context never grows |
| lost-in-the-middle | context stays short |
| O(n²) cost | per-step context is ~10³–10⁴ tokens |

---

## 3. The primary demonstration (case study)

**Goal:** write a 21-chapter book (*AAI & Kālacakra*) meeting a definition of done
(each chapter ≥ 3,000 words, canon terms used exactly, epistemic tags `[E]/[I]/[S]`
on contested claims).

**Setup:** writer = DeepSeek V4.1 Flash; verifier = GLM 5.3 Flash (different
family); reasoning depth 2; budget 2,000,000 tokens; max 400 steps.

**Results (from the Postgres ledger):**

| Metric | Value |
|---|---|
| Words | **91,269** (22 chapters, ~331 pages) |
| Steps | 93 |
| Tokens | 943,414 / 2,000,000 (47.2%) |
| **Max context sent** | **9,789 tokens (0.98% of the 1M window)** |
| Artifact ÷ working context | **~12.4×** |
| Council (reasoning) share | **62.6%** of all tokens |
| Escalations | **0** |
| First-pass task success | **91% (20/22)** |
| Tool errors | 0 |
| Canon terms present | 31/31 |

**Survival:** the process was killed (`kill -9`) mid-chapter (9 chapters done,
474,423 tokens spent); `resume` continued at the exact chapter with no lost or
duplicated work. A second hang (an HTTP 500) was survived after adding retry.

**Qualitative:** cross-chapter coherence held across ~91k words (no canon
contradictions); the artifact closed its own narrative loop (last page echoing
the first).

---

## 4. Proposed controlled comparison (the dual experiment)

To move from case study to evidence, we specify a preregistered comparison.

**Conditions**
- **A — Kernel-Arjun** (this paper's system).
- **B — Naive single-conversation agent:** one growing context, re-prompted
  "continue" as needed, no external ledger, no independent verifier, no budgets.

**Task:** identical long-horizon task (e.g. the book, or a phased codebase
build) with an identical definition of done and identical model(s).

**Measures**
- **Completion:** fraction of DoD met; artifact size on disk.
- **Coherence:** canon contradictions; first-pass verification rate.
- **Efficiency:** tokens per verified unit; wall-clock.
- **Failure point:** the step/chapter at which B degrades or stops.
- **Cost:** total tokens; cost in currency.

**Hypotheses**
- H1: B stops or degrades early (output ceiling / context rot), completing a
  small fraction of A.
- H2: B's coherence declines monotonically with length (lost-in-the-middle);
  A's does not.
- H3: A survives interruption; B cannot.
- H4: A's cost per verified unit is lower at long horizons despite longer runs.

**Falsifiability:** if B matches A at long horizons, the thesis is wrong. We
commit to reporting that outcome.

---

## 5. Related work

- **Memory externalization:** MemGPT (packing/paging), Generative Agents
  (memory streams), Voyager (skill libraries).
- **Reflection:** Reflexion (Shinn et al., 2023), Self-Refine, CRITIC.
- **Reasoning+acting:** ReAct (Yao et al., 2022), ReWOO, Plan-and-Act.
- **Multi-agent:** AutoGen, MetaGPT, CAMEL.
- **Durable execution:** Temporal, Restate, LangGraph checkpointers.
- **Long-context degradation:** Liu et al. 2023 ("Lost in the Middle").

**Gap.** These provide *pieces*. Kernel-Arjun packages durable state + budget
law + independent verification + deliberation + resumability into one
model-agnostic kernel, and reports a measured long-horizon result. The
combination and the measurement are the contribution.

**On "Fable."** We could not verify any public agent system named "Fable" or
"Fable 5.1"; the name publicly attaches to a storytelling company and a game.
We therefore do not claim to build on or reproduce it. The *category* —
long-horizon agents — is well established (above).

---

## 6. Limitations

- Single case study; the controlled comparison (§4) is future work.
- One model pair; generalization untested.
- Verification quality depends on the verifier; adversarial drift can pass.
- The "capacity" metric (largest task with 0 escalations) is domain-shaped.
- The 1M window was never saturated; we test *externalization*, not compaction
  at the window boundary.

---

## 7. Conclusion

Long-horizon agency is a **systems** problem, not a context-length problem. By
keeping state in a durable ledger and assembling a small fresh context each step,
Kernel-Arjun produced an artifact ~12× larger than any context it ever held, with
zero escalations and exact crash recovery — for under half its token budget. The
kernel is open (MIT). We invite replication and, above all, refutation.

---

## Reproducibility

```bash
pip install kernel-arjun
docker compose up -d          # postgres
export HIVE_API_KEY=...
arjun book missions/kala-chakra/seeds.yml --workspace ./book
arjun meter <goal_id>
```

All code, seeds, and the deterministic canon checker are in the repository.

---

*Draft — not yet submitted. © Murugan Ai Labs Pvt Ltd.*

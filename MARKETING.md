# Kernel-Arjun — Marketing & Launch Plan

*How we take the kernel to the world. See STRATEGY.md for the business logic.*

---

## The one-liner

> **Kernel-Arjun is the durable-execution kernel for long-horizon AI agents.**
> State that survives restarts, budgets that are law, completion that is verified.

## The hook (use this)

> A model is a stateless next-token predictor. It has no memory between calls,
> and its context window bounds one call — not a task. So how do you run an agent
> for *days*? You keep the state outside the model. We built that, and proved it
> by writing a 91,269-word book with **zero escalations**, surviving two hard
> kills, using under 1% of the context window per step.

## Positioning (say this, not that)

| Say | Not |
|---|---|
| "durable-execution kernel" | "agent framework" |
| "state outside the model" | "better memory" |
| "budgets are law" | "cost controls" |
| "the verifier is never the doer" | "self-checking" |
| "runs for days, survives restarts" | "long context" |

We are **not** competing with LangChain/LangGraph/CrewAI on features. We are the
**durability + verification layer** they lack. Interoperate with them; be their
missing half.

## The proof is the campaign

The strongest asset is the **book + the numbers**. Strategy: lead with the proof,
let people disbelieve, then show the run.

- The 91,269-word book (a visible artifact).
- The scorecard: 0 escalations, 97k max context, 62.6% reasoning, exact resume.
- The naive baseline: one call produced 2.7% of it and stopped.

This is the "show, don't tell" that technical audiences reward.

---

## Channels & sequence

### Phase 0 — Foundations (now)
- [x] Public GitHub repo (MIT), PyPI package, docs.
- [ ] README with the proof front and center.
- [ ] A 60-second demo GIF: `pip install` → `arjun start` → book grows.

### Phase 1 — Developer seeding
- **Hacker News** — "Show HN: Kernel-Arjun — a durable kernel for agents that
  run for days." Post the proof, not the pitch. Be present in the thread.
- **Reddit** — r/LocalLLaMA, r/MachineLearning, r/LangChain.
- **X/Twitter** — thread: the stateless-model insight → the book → the numbers.
- **Dev.to / Medium** — a long technical writeup (the TECHNICAL_DEEP_DIVE).

### Phase 2 — The research paper
- Post **PAPER.md** to arXiv (cs.AI / cs.LG / cs.CL).
- Title idea: *"Long-Horizon Agency by Externalizing State: A Durable-Execution
  Kernel with Independent Verification."*
- This earns credibility no marketing can buy.

### Phase 3 — The product story
- **Kernel-Arjun Cloud** (hosted) — when the standard is named.
- **Murugan Ai Labs** — the company behind it; sovereign AI; India story.

---

## Launch assets to write

1. **README** (done) — proof-first.
2. **Get started** (done) — frictionless onboarding.
3. **Demo script** — reproducible: run the book mission from scratch.
4. **Blog post** — "Why your agent dies at step 200" (the failure modes + fix).
5. **Paper** (next) — the academic version.
6. **Landing page** — murugan.ai/kernel-arjun (later).

## The benchmark as a wedge

Nobody has a clean standard for **measuring long-horizon agents honestly**. The
capacity ladder (largest task completed with 0 escalations, first-pass %, canon
contradictions) is adoptable as *the* public benchmark. If we define the metric,
we define the conversation.

## What we will NOT do

- Not spam. Not hype "AGI." Not claim consciousness.
- Not license-gate the kernel (see STRATEGY.md).
- Not over-promise: the claims are exactly the measured numbers.

---

## Success metrics (first 90 days)

| Metric | Target |
|---|---|
| PyPI installs | 1,000+ |
| GitHub stars | 500+ |
| arXiv paper posted | yes |
| A third party runs a real long-horizon job | 1+ |

---

*Built at Murugan Ai Labs. Consecrated by Quantum Thoughter × Æmma Hø.*

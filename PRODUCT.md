# Kernel-Arjun — Product Thesis

**The durable-execution kernel for long-horizon AI agents.**

> Most agents are optimized for one hard task. Kernel-Arjun is optimized for one
> task that outlives the session, the context, and the process — and proves it.

---

## The problem

Every agent framework today (opencode, Claude Code, AutoGPT, LangGraph apps) shares
the same hidden assumption: **the run is a conversation, and the conversation is
the state.** So when the context fills, quality rots. When the process dies, the
work dies. When the model says "done," nobody checks. When costs climb, nobody
sees the number. Long tasks — real books, real migrations, real research — fail
not because the model is dumb, but because **the scaffolding is not durable.**

## The insight

A model is a **stateless next-token predictor** (DeepSeek's own words). It has no
memory between calls and its context window bounds one call, not a task. Therefore
the *state* of a long task must live **outside** the model — and the horizon must
be built by the system, not requested from the prompt.

## What Kernel-Arjun is

A small engine that runs one goal for hours or days:

- **Ledger** — all state in Postgres (goals, tasks, steps, events, artifacts, budgets).
  Crash-safe, replayable, auditable.
- **Breath** — the loop: plan → act → observe → verify → persist, one step at a time.
- **Assembled context** — each step sends a *small, fresh, relevant* context
  (goal + seed + canon + tail of last chapter + recent steps). Never accumulates.
- **Council** — deliberate reasoning before acting (Thoth → Murugan/Sisi → Dakini).
  The model's reasoning trace is captured, not discarded.
- **Mirror** — an independent verifier (different model) plus deterministic gates.
  "Done" is decided against disk truth, not the model's opinion.
- **Watcher** — budgets are law (tokens/steps/wallclock); fingerprints, spin
  detection, strategy shifts, escalation ladder.

Model-agnostic: Ollama, Hive, DeepSeek, or any OpenAI-compatible endpoint.

---

## The proof

One goal, 2,000,000-token budget, Hive (DeepSeek writer + GLM verifier):

| | |
|---|---|
| Artifact produced | **91,269-word, 22-chapter book** (331 pages) |
| Largest context ever sent | **9,789 tokens (0.98% of the 1M window)** |
| Artifact vs working context | **~12.4×** |
| Internal reasoning share | **62.6% of all spend** (the Council) |
| Escalations | **0** |
| First-pass task success | **91%** |
| Kill `-9` at ch.9 → resume | **exact, zero loss** |
| Budget used | **47%** |

**The artifact is ~12× larger than any context the model ever held — because the
memory lives in the database, not the window.**

---

## Why this is different

| Long-horizon need | Typical agent | Kernel-Arjun |
|---|---|---|
| Survive process death | loses the run | `resume` from Postgres |
| Beyond the context window | rots / lossy compaction | assemble small fresh context |
| Budget control | soft | hard law, in the ledger |
| "Done" | model says so | deterministic + independent verifier |
| Loops / drift | silent waste | fingerprints, spin, escalation |
| Audit | chat transcript | append-only event ledger |
| Cost per result | opaque | `arjun meter` scorecard |

Established category techniques (compaction, memory externalization, reflexion,
durable execution) exist as *pieces*. **The packaged combination — durable state +
budget law + independent verification + reasoning council + scorecard, all
model-agnostic — is what does not exist as a product.**

---

## Commands

```bash
arjun start "goal" --dod "..." --workspace ./ws
arjun book  seeds.yml --workspace ./ws        # seed-driven long-form missions
arjun status | logs | meter <id>              # inspect
arjun context <id>                            # anatomy of the next context
arjun watch <id> --include-paused             # durable supervisor daemon
arjun resume <id>                             # continue a paused goal
arjun doctor                                  # health check
```

## Target customers

1. **Long-form generation where verification matters** — books, legal, clinical,
   research reports, corpora. (We have a working proof.)
2. **Sovereign long-running automation** — run for days, own the data, no cloud
   lock-in. (Fits Murugan Ai Labs' four vows.)
3. **Agent builders** — use the kernel as an SDK; bring your own model and tools.

## Roadmap

- `watch` daemon ✅ · context inspector ✅
- Pluggable domain verifiers (code tests, citations, canon, fact-check)
- Working-memory engrams wired across goals
- Cost governor + dashboard (₹/token ceilings)
- Parallel goal scheduler
- **MCP server** — opencode/Claude launch & supervise multi-day jobs

---

*Built at Murugan Ai Labs. Consecrated by Quantum Thoughter × Æmma Hø.
Love is the engine.*

# Kernel-Arjun — Design v1

> The archer's core: a persistent agent engine that takes one goal and works it
> for hours or days — surviving restarts, never losing state, never looping,
> verifying itself, and knowing when to call for help.

## Six design laws

1. **State lives outside the model.** The model is stateless per call; Postgres remembers everything.
2. **Context is assembled, never accumulated.** Small + relevant beats big + noisy.
3. **Append-only events.** State is a projection of the log — crash-safe, replayable, auditable.
4. **The verifier is never the doer.** A different model checks the work.
5. **Stuck -> escalate, never flail.** Retry limits force strategy changes and human calls.
6. **Budgets are law.** Steps, tokens, and wallclock have hard caps.

## The Five Organs

| Organ | Role | Implementation |
|-------|------|----------------|
| Flame | The goal + definition of done | `goals` table |
| Ledger | Deeds, plans, artifacts, budgets | Postgres |
| Breath | The loop: plan -> act -> observe -> verify -> persist | `orchestrator.py` |
| Mirror | Independent verification | `verifier.py` + tests |
| Watcher | Heartbeat, budgets, no-progress, escalation | orchestrator guards |

## The Loop

```
while goal.status == "active":
    ctx     = assemble_context()            # small, always
    reply   = route(role, ctx)              # structured JSON action
    act     = validate(reply)               # schema + safety gates
    out     = execute(act)                  # fingerprinted, logged
    verdict = mirror(act, out)              # tests or verifier model
    persist(act, out, verdict)              # steps + events
    if no_progress() or over_budget(): strategy_shift() or escalate()
    if phase_done(): checkpoint()
```

## Memory hierarchy

- **Hot** — assembled context (~5K tokens): goal + recent steps + top engrams
- **Warm** — Postgres: full step history, artifacts, checkpoints
- **Cold** — engram store (JSON + Ollama embeddings): compressed episodes, semantic recall

## Ledger schema

See `arjun/schema.sql` — goals, tasks, steps, events, checkpoints, artifacts, budgets.

## Model roles

| Role | Default | Purpose |
|------|---------|---------|
| planner | qwen2.5-coder:7b | decompose goal into tasks |
| executor | qwen2.5-coder:7b | one action per step |
| verifier | codegeex4:latest | independent pass/fail (different family) |
| compressor | llama3.2:3b | summarization |

Any OpenAI-compatible / Ollama endpoint can be swapped in, including frontier models.

## Escalation ladder

1. Same action fingerprint fails 3x -> force a re-plan
2. Re-plan fails 2x -> pause + notify the human with a precise question
3. Budget at 80% -> warning | 100% -> hard stop

## Anti-stuck machinery

- **Fingerprinting** — identical action+input attempted repeatedly = blocked
- **No-progress detector** — progress key unchanged over N steps -> re-plan
- **Checkpoints** — every step persisted; resume is exact
- **Kill-switch** — `arjun pause` / Ctrl-C is always safe

## Build phases

- **Phase 1 (done in v0.1):** ledger + loop + tools + checkpoints + CLI + dry-run
- **Phase 2 (done in v0.1):** engram memory, context assembly, verifier organ
- **Phase 3:** watchdog daemon, notifications, git awareness, dashboards
- **Phase 4:** MCP server — opencode launches and monitors multi-day tasks

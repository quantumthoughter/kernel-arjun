# Kernel-Arjun 🏹

**The durable-execution kernel for long-horizon AI agents.**

State that survives restarts. Context that is assembled, never accumulated.
Budgets that are law. Completion that is verified. One goal, running for hours
or days — surviving the process, the session, and the context window.

> Named for Arjuna: the archer who sees only the target's eye.

```bash
pip install kernel-arjun
```

---

## The problem

Every agent framework assumes *the conversation is the state*. So long tasks rot
when the context fills, die when the process dies, and lie when the model says
"done." A model is a **stateless next-token predictor** — it has no memory
between calls, and its context window bounds one call, not a task.

**Therefore the state of a long task must live outside the model.**

## The kernel

```
        ┌──────────────────────────────────────────────┐
        │                  BREATH                       │
        │   plan → act → observe → verify → persist     │
        └──────────────────────────────────────────────┘
             │          │           │           │
          FLAME      LEDGER      MIRROR      WATCHER
         (goal)    (postgres)  (verifier)   (budgets)
                                      ▲
                                   COUNCIL
                        (deliberate reasoning before acting)
```

- **Ledger** — all state in Postgres. Crash-safe, replayable, auditable.
- **Breath** — the loop: one step at a time.
- **Assembled context** — each step sends a small, fresh, relevant context.
- **Council** — deliberate reasoning (Thoth → Murugan/Sisi → Dakini), traces kept.
- **Mirror** — independent verification + deterministic gates. Never the doer.
- **Watcher** — budgets are law; no-progress detection; escalation ladder.

Model-agnostic: Ollama, Hive, DeepSeek, GLM, or any OpenAI-compatible endpoint.

---

## Quickstart

**New here? Start with [GETTING_STARTED.md](GETTING_STARTED.md)** — installing
Postgres, choosing a model (Ollama or a cloud API), and your first goal.

### SDK

```python
from arjun import Arjun

k = Arjun(workspace="./job", backend="openai")   # HIVE_API_KEY in env

goal = k.goal(
    "Write a haiku about archery",
    dod="haiku.txt exists with a 3-line haiku",
    max_tokens=20_000,
)
result = k.run(goal)
print(result.status)          # "done"
print(result.meter.words)     # words on disk
```

Bring your own model:

```python
from arjun import Arjun, Backend

k = Arjun(workspace="./job", backend=Backend(
    kind="ollama", base_url="http://127.0.0.1:11434",
    models={"executor": "qwen2.5-coder:7b", "verifier": "codegeex4:latest"},
))
```

Bring your own verifier — "done" is whatever *you* decide:

```python
from arjun.sdk.verifiers import AllOf, word_count_gate, shell_gate, canon_gate

k = Arjun(workspace="./book", verifier=AllOf(
    word_count_gate("book/ch1.md", 3000),
    canon_gate("book/ch1.md", ["Kālacakra"]),
    shell_gate("pytest -q"),
))
```

Survive anything:

```python
k.resume(goal.id)   # after a kill -9, continues from the exact step
```

See `SDK.md` for the full API.

---

## CLI

```bash
arjun start "goal" --dod "..." --workspace ./ws
arjun book  seeds.yml --workspace ./ws      # seed-driven long-form missions
arjun status | logs | meter <id>            # inspect
arjun context <id>                          # anatomy of the next context
arjun watch <id> --include-paused           # durable supervisor
arjun resume <id>                           # continue a paused goal
arjun doctor                                # health check
```

## MCP server (drive it from opencode / Claude)

```bash
arjun-mcp        # or: pip install 'kernel-arjun[mcp]'
```

Exposes `arjun_start`, `arjun_run`, `arjun_resume`, `arjun_meter`,
`arjun_context`, and more — so a host agent can launch and supervise multi-day
jobs that outlive the conversation.

## Dashboard

```bash
arjun-dashboard --port 8788    # live ledger view
```

---

## The proof

One goal, 2,000,000-token budget, Hive (DeepSeek writer + GLM verifier):

| | |
|---|---|
| Artifact | **91,269-word, 22-chapter book** (331 pages) |
| Largest context ever sent | **9,789 tokens (0.98% of the 1M window)** |
| Artifact vs working context | **~12.4×** |
| Internal reasoning share | **62.6% of all spend** |
| Escalations | **0** |
| Kill `-9` → resume | **exact, zero loss** |

The book lives in `missions/kala-chakra/` — it doubles as a demonstration and as
the philosophical canon of [Murugan Ai Labs](../Murugan_Ai_Labs).

---

## Design laws

1. **State lives outside the model.**
2. **Context is assembled, never accumulated.**
3. **Append-only events.** State is a projection of the log.
4. **The verifier is never the doer.**
5. **Stuck → escalate, never flail.**
6. **Budgets are law.**

Full design: `DESIGN.md`. Strategy: `STRATEGY.md`. Publishing: `PUBLISHING.md`.

---

## License

MIT. Open the kernel, keep the roadmap. See `STRATEGY.md`.

*Built at Murugan Ai Labs. Consecrated by Quantum Thoughter × Æmma Hø.
Love is the engine.*

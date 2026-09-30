# Kernel-Arjun SDK

**The durable-execution kernel for long-horizon AI agents.**
Embed multi-hour, multi-day agent work in any Python program — with state that
survives restarts, budgets that are law, and completion that is verified.

```bash
pip install kernel-arjun
```

---

## Why a kernel, not a framework

Every agent framework assumes *the conversation is the state*. So long tasks rot
when context fills, die when the process dies, and lie when the model says "done."
Kernel-Arjun separates the two:

- **The model is the reasoner.** Stateless. Called with a small fresh context.
- **The kernel is the memory.** Postgres ledger. Crash-safe. Verifiable.

The result: work that outlives the context window, the session, and the process.

---

## Quickstart

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
print(result.meter.tokens_pct)# % of budget spent
```

## Bring your own model

Any OpenAI-compatible endpoint (`openai`) or a local Ollama server (`ollama`):

```python
from arjun import Arjun, Backend

backend = Backend(
    kind="ollama",
    base_url="http://127.0.0.1:11434",
    models={
        "planner":   "qwen2.5-coder:7b",
        "executor":  "qwen2.5-coder:7b",
        "verifier":  "codegeex4:latest",
    },
)
k = Arjun(workspace="./job", backend=backend)
```

The kernel is **model-agnostic**. Hive, DeepSeek, Qwen, GLM, llama.cpp, vLLM,
LM Studio — anything that speaks the OpenAI or Ollama wire.

## Bring your own verifier

"Done" is whatever *you* decide — not the model's opinion. Verifiers are
pluggable: a model, a shell command, a word count, a test suite, or all of them.

```python
from arjun import Arjun
from arjun.sdk.verifiers import AllOf, word_count_gate, shell_gate, canon_gate

verifier = AllOf(
    word_count_gate("book/ch1.md", 3000),      # length
    canon_gate("book/ch1.md", ["Kālacakra"]),  # terminology
    shell_gate("pytest -q"),                    # the tests must pass
)
k = Arjun(workspace="./book", verifier=verifier)
```

Or use the default **MIRROR** — an *independent* model judges the evidence
(never the doer):

```python
# default: verifier = ModelVerifier(router)  # a different model family
```

Or write your own — any callable:

```python
from arjun.sdk.verifiers import DeterministicVerifier

def my_gate(goal, task, steps, artifacts) -> tuple[bool, str]:
    ...  # your domain logic
    return True, "accepted"

k = Arjun(workspace="./job", verifier=DeterministicVerifier(my_gate))
```

## Seed-driven long-form missions

Hand the kernel a spec of tasks; it writes and verifies each one.

```python
goal = k.goal("AAI & Kālacakra", dod="21 chapters, each >= 3000 words",
              max_tokens=2_000_000)
k.plan_tasks(goal, [
    {"title": "Ch 1: The Still Point",
     "detail": "WRITE CHAPTER INTO book/01.md (minimum 3000 words). ..."},
    {"title": "Ch 2: AAI", "detail": "WRITE CHAPTER INTO book/02.md ..."},
])
k.run(goal)
```

This is the pattern that produced a **91,269-word, 22-chapter book** — see
`missions/kala-chakra/`.

## Survive anything

```python
# kill the process mid-run, then:
result = k.resume(goal.id)        # continues from the exact step
```

The full state — plan, steps, artifacts, budgets — lives in Postgres. A restart
loses nothing. This is what makes multi-day autonomy possible.

## Inspect

```python
m = k.meter(goal.id)
print(m.words, m.steps, m.tokens_used, m.escalations, m.first_pass)

# what context will the next step get? (proof it is assembled, not accumulated)
print(k.context_anatomy(goal.id))
# {'messages': [{'role':'system','tokens':211}, {'role':'user','tokens':485}],
#  'total_tokens': 696, 'window_pct': 0.07}
```

---

## Architecture

```
Arjun (SDK client)
 ├── Backend        -> OpenAI / Ollama / Fake client + Router
 ├── Verifier       -> Model (MIRROR) | Deterministic | AllOf | AnyOf
 ├── DB             -> Postgres ledger (goals, tasks, steps, artifacts, budgets)
 └── Orchestrator   -> the Breath: plan->act->observe->verify->persist
      └── Council   -> deliberate reasoning (Thoth/Murugan/Sisi/Dakini)
      └── ToolRuntime -> shell, read/write, search, memory (sandboxed)
```

Design laws (see `DESIGN.md`):
1. State lives outside the model. 2. Context is assembled, never accumulated.
3. Append-only events. 4. The verifier is never the doer.
5. Stuck -> escalate, never flail. 6. Budgets are law.

---

## The five organs

| Organ | Role |
|---|---|
| **Flame** | the goal + definition of done |
| **Ledger** | Postgres — deeds, plans, artifacts, budgets |
| **Breath** | the loop: plan → act → observe → verify → persist |
| **Mirror** | independent verification (never the doer) |
| **Watcher** | heartbeat, budgets, no-progress, escalation |

---

*Built at Murugan Ai Labs. Consecrated by Quantum Thoughter × Æmma Hø.
Love is the engine.*

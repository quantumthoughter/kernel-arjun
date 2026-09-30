# Getting Started with Kernel-Arjun

A complete guide for a new user — from zero to a finished long-horizon goal.
**You only need `pip`.** Git is optional (only for developers).

---

## 0. What you need

Kernel-Arjun is a *kernel*: it supplies the durable loop, the memory, the
verification, and the budgets.

**The true minimum to run it:**

| You need | What it is | Required? |
|---|---|---|
| **Python 3.10+** | the runtime | yes |
| **A model** | the reasoner (a cloud API or a local model) | **yes** — pick one below |
| **Postgres** | the durable ledger (state that survives restarts) | **yes** |
| **A workspace** | a folder where artifacts are written | yes (any folder) |

That's all. You run it from the **terminal** or **Python** — no AI host, no MCP,
no chatbot framework required.

**Optional — only if you want an AI host to drive it:**

| Optional | When you need it |
|---|---|
| **MCP server** (`kernel-arjun[mcp]`) | to let opencode / Claude / Cursor launch goals as tools |
| **A host AI** (opencode, Claude Desktop, Cursor, …) | to orchestrate it conversationally — must be MCP-capable |

Two independent directions, easy to confuse:

- **Direction A — the kernel *uses* your AI as its model:** point a `Backend` at
  *any* OpenAI-compatible endpoint (Hive, OpenAI, Groq, vLLM, LM Studio, Ollama).
- **Direction B — your AI *drives* the kernel:** any **MCP-capable** host calls
  the kernel's tools. A chatbot that does not speak MCP cannot do this.

You do **not** need git, Docker, a GPU, or MCP. Postgres is a one-line install.

---

## 1. Install

```bash
pip install kernel-arjun

# optional extras:
pip install 'kernel-arjun[mcp]'    # MCP server (drive it from opencode / Claude)
pip install 'kernel-arjun[all]'    # + dashboard extras
```

That's it. The package is ~46 KB (432 KB installed; ~52 MB with the Postgres
client). Verify:

```bash
arjun --version
```

---

## 2. Choose a model backend

### Option A — Local model with Ollama (free, private, offline)

1. Install Ollama: https://ollama.com/download
2. Pull models (one for writing, a *different* one for verifying):

```bash
ollama pull qwen2.5-coder:7b
ollama pull codegeex4:latest
ollama pull nomic-embed-text        # for memory embeddings
```

3. Point Kernel-Arjun at it:

```python
from arjun import Arjun, Backend

k = Arjun(workspace="./job", backend=Backend(
    kind="ollama",
    base_url="http://127.0.0.1:11434",
    models={
        "planner":   "qwen2.5-coder:7b",
        "executor":  "qwen2.5-coder:7b",
        "verifier":  "codegeex4:latest",
        "compressor":"llama3.2:3b",
    },
))
```

### Option B — Cloud model (any OpenAI-compatible endpoint)

Works with Hive, DeepSeek, OpenAI, Together, Groq, vLLM, LM Studio — anything
that speaks the OpenAI wire.

```bash
export HIVE_API_KEY="your-key"      # or OPENAI_API_KEY, etc.
```

```python
from arjun import Arjun, Backend

k = Arjun(workspace="./job", backend=Backend(
    kind="openai",
    base_url="https://api-cdn.thehive.ai/api/v3",
    api_key_env="HIVE_API_KEY",
    models={
        "executor": "deepseek-ai/deepseek-v4.1-flash",
        "verifier": "zai-org/glm-5.3-flash",   # a DIFFERENT family verifies
    },
))
```

> **Best practice:** the verifier should be a *different model family* than the
> writer. The mirror is never the doer.

---

## 3. Install Postgres

The ledger needs Postgres. Any one of these works:

**macOS (Homebrew)**
```bash
brew install postgresql@16
brew services start postgresql@16
createdb arjun
```

**Docker (any OS)**
```bash
docker run -d --name arjun-pg -p 5432:5432 \
  -e POSTGRES_DB=arjun -e POSTGRES_PASSWORD=arjun postgres:16
```

**Ubuntu/Debian**
```bash
sudo apt install postgresql
sudo -u postgres createdb arjun
```

Kernel-Arjun creates its own tables on first run — you only create the database.

---

## 4. First goal (Python SDK)

```python
from arjun import Arjun

k = Arjun(
    workspace="./my-job",
    backend="ollama",                 # or "openai"
    dsn="host=127.0.0.1 port=5432 dbname=arjun user=postgres",
)

goal = k.goal(
    "Write a short poem about the moon",
    dod="moon.txt exists with a 4-line poem",
    max_tokens=50_000,
)

result = k.run(goal)
print(result.status)            # "done"
print(result.meter.words)       # words on disk
print(result.meter.tokens_pct)  # % of budget used
```

---

## 5. First goal (command line)

```bash
arjun start "Write a short poem about the moon" \
      --dod "moon.txt exists with a 4-line poem" \
      --workspace ./my-job
```

Other commands:

```bash
arjun status                 # list all goals
arjun status 1               # one goal's detail
arjun meter 1                # the scorecard
arjun logs 1                 # event stream
arjun context 1              # the context the next step will receive
arjun resume 1               # continue a paused goal
arjun watch 1                # keep it running until done
arjun doctor                 # health check everything
```

---

## 6. Health check

Before your first real run:

```bash
arjun doctor
```

It checks Postgres, Ollama, the models, and the memory store, and tells you
exactly what is missing.

---

## 7. Configuration

`arjun init` writes `~/.config/kernel-arjun/config.yaml` from
`config.example.yaml`. Edit it to set:

- `postgres.dsn` — your database connection
- `models.*` — which model plays which role
- `limits.*` — max steps, tokens, wall-clock (**budgets are law**)
- `safety.*` — allowed read paths and denied shell patterns

Secrets (API keys) always come from the **environment**, never the config file.

---

## 8. The one thing to understand

A model is **stateless** — no memory between calls, and its context window
bounds one call, not a task. So Kernel-Arjun keeps the *state* in Postgres and
hands the model a **small, fresh context each step**.

That is why a goal can run for days, survive `kill -9`, and produce artifacts far
larger than any single context window — the memory lives in the ledger, not the
model.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `postgres: connection refused` | start Postgres; check `postgres.dsn` |
| `ollama chat failed` | is `ollama serve` running? is the model pulled? |
| `HIVE_API_KEY not set` | `export HIVE_API_KEY=...` |
| goal paused with an escalation | read it with `arjun logs <id>`, then `arjun resume <id>` |
| `arjun-mcp` says missing `mcp` | `pip install 'kernel-arjun[mcp]'` |

---

*Built at Murugan Ai Labs. Consecrated by Quantum Thoughter × Æmma Hø.
Love is the engine.*

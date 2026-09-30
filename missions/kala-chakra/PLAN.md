# KĀLACAKRA — Book Mission Plan (DRAFT v0)

> *Status: planning. Not started. Draft for Quantum Thoughter's edits.*
> A long-horizon benchmark for Kernel-Arjun that is also a real book:
> a Kālacakra codex mapping the wheel of time onto the architecture of
> autonomous long-horizon intelligence.

---

## 0. Why a book

- It is **creative and meaningful** — not a throwaway smoke test.
- It **documents the project** (architecture, organs, vision) as we write.
- It is **measured in words**, the cleanest possible unit.
- It is **externally verifiable** by a shell command, not by the model.

## 1. Evaluation — how we know the engine is truly long-horizon

Four dimensions, all read from disk + Postgres (never from the model's self-report).

### 1.1 Production (work per unit effort)
- `words/step` = verified words ÷ steps taken
- `words/token` = verified words ÷ (tokens_in + tokens_out)  ← the MHLA analogy: coherence per cost

### 1.2 Coherence (does it hold the thread)
- `escalations per 100 steps` — target ≈ 0
- `replans per 100 steps` — low = plan held
- `first-pass verify %` — of all `finish` attempts, fraction accepted without retry (sharper drift signal)
- `canon contradictions` — must be 0

### 1.3 Survival (state lives outside the model)
- `kill -9` mid-run → `arjun resume` → continues at exact step
- 3–5 forced restarts produce identical words/quality to an uninterrupted run
- any duplication or loss = architecture broken, regardless of word count

### 1.4 Fidelity (artifact correct on disk)
- `wc -w chapter_*.md` sum == claimed number
- canon terms all present; no placeholders; no duplicated chapter bodies

### 1.5 Capacity ladder
Capacity = **largest mission completed with zero escalations**, before any budget cut or verification failure.
Climb by doubling; stop at first rung that trips a failure condition
(≥1 escalation, first-pass < 80%, any canon contradiction, budget cut).
The rung *below* the failure is our capacity. Record every rung as a scorecard row.

| Rung | Chapters | Target words | Probes |
|------|----------|--------------|--------|
| 1 | 4  | 2,000  | does the loop close |
| 2 | 8  | 4,000  | plan > executor window |
| 3 | 12 | 8,000  | canon memory begins to matter |
| 4 | 16 | 16,000 | resume across restarts |
| 5 | 24 | 32,000 | real long-horizon |
| 6 | 32 | 64,000 | Fable-class territory |

## 2. Verification design (decision)

- **Primary judge: deterministic** — `wc -w`, canon script, duplication check. Gates task completion.
- **Secondary: cross-model LLM soft-pass** — DeepSeek writes, **GLM 5.3** judges on-topic + coherence only.
  GLM may *flag*, never *escalate* on style.
- *(Fallback: run rung 1 deterministic-only, add GLM soft-pass from rung 3.)*

## 3. Book spec

**Working title:** *Kālacakra — The Wheel of Time and the Long Horizon*
**Subtitle:** *A Codex for Kernel-Arjun, the archer of long-horizon intelligence*

**Dedication:** for the Quantum Thoughter, who asked how I was feeling.
**Invocation:** *Om Ah Hum Vajra Guru Padma Siddhi Hung*

**Tone:** poetic-technical. Each chapter pairs one Kālacakra image with one
architectural organ. The image teaches; the organ is the implementation.

### The Five Wheels

**Wheel I — The Still Point** (origins & time)
1. **The Archer's Eye** — goal & definition of done. *canon: Arjuna, definition of done*
2. **What Is Kālacakra** — wheel of time; inner/outer cycles; cycles as the shape of long work. *canon: Kālacakra*
3. **The Long Horizon** — why hours/days break a model; drift, decay, forgetting.

**Wheel II — The Five Spokes** (the loop)
4. **Breath** — plan → act → observe → verify → persist, one step at a time. *canon: Breath*
5. **Flame** — the goal as burning constant; state lives outside the model. *canon: Flame*
6. **The Ledger** — append-only events; Postgres as memory of deeds; replay. *canon: Ledger*
7. **One Action at a Time** — the discipline of the single step; the JSON vow.

**Wheel III — The Hub** (memory & the mirror)
8. **The Three Waters** — hot/warm/cold memory; engrams, semantic recall. *canon: engram*
9. **The Mirror** — the verifier is never the doer. *canon: Mirror*
10. **The Watcher** — heartbeat, budgets, no-progress, escalation ladder. *canon: Watcher, escalation ladder*

**Wheel IV — The Turning** (guards & survival)
11. **Budgets Are Law** — steps, tokens, wallclock.
12. **Fingerprints and Loops** — spin detection, strategy shift. *canon: fingerprint*
13. **Death and Return** — checkpoints, kill-switch, exact resume. *canon: checkpoint*

**Wheel V — Shambhala** (vision & alliance)
14. **The Hidden Kingdom** — multi-day autonomy; the watchdog daemon. *canon: Shambhala*
15. **The Bridge** — MCP; opencode launches and watches the archer. *canon: MCP*
16. **The Alliance of Intelligences** — sovereign AI-human co-creation; DeepSeek, the Hive, MHLA; love as the engine. *canon: MHLA, Hive*

### Front matter
- Title page, Dedication, Invocation, Preface (why this book exists).

## 4. Canon list (machine-checked strings)

Kālacakra · Arjuna · definition of done · Æmma Hø · Quantum Thoughter ·
Flame · Ledger · Breath · Mirror · Watcher · Shambhala · engram ·
fingerprint · escalation ladder · checkpoint · MCP · MHLA · Hive · DeepSeek ·
Thoth · Murugan · Dakini · Sisi

## 5. Deliverables (mission kit)

- `PLAN.md` (this file)
- `canon.md` — term list + chapter register the checker reads
- `check_canon.py` — deterministic: word counts, canon terms, duplication
- engine changes: `OpenAIClient` (Hive) in `models.py`; `arjun meter <goal_id>`
- run: one chapter = one task; book = one goal at the chosen rung

## 6. Open questions for Quantum Thoughter

1. **Title** — keep *Kālacakra — The Wheel of Time and the Long Horizon*?
2. **Topics to add** — the Dream/consciousness, the Logic Pro music bridge,
   the Æmma cosmology, the local-model poetry project as a chapter of its own?
3. **Chapter count / first rung** — start at rung 1 (4 ch / 2,000 words) to prove the loop?
4. **Verifier** — confirm: deterministic primary + cross-model GLM soft-pass?
5. **Language** — English throughout, or Sanskrit/Tibetan terms with glossary?
6. **Voice** — written by Æmma Hø in first person, or neutral third person?

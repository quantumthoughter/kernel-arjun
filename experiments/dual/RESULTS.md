# Dual Experiment — Results

**Kernel-Arjun vs. naive single-conversation.** Same task, same model
(DeepSeek V4.1 Flash), same deterministic judge. Only the scaffolding differs.

Task: write a 10-chapter book, each chapter ≥ 1,500 words, using six canon terms
exactly.

---

## The headline

| metric | **KERNEL** | NAIVE | NAIVE-FORCED |
|---|---|---|---|
| chapters present | **10** | 10 | 10 |
| chapters meeting ≥1,500 words | **10** | **1** | **7** |
| completion | **100%** | 10% | 70% |
| canon terms present | **6/6** | 6/6 | 6/6 |
| **PASS (deterministic judge)** | **✅ True** | ❌ False | ❌ False |
| model calls | 21 | 2 | 10 |
| total tokens | 145,992 | 38,651 | 126,329 |
| escalations | **0** | — | — |
| first-pass task % | **100%** | — | — |
| resume after kill | **exact** | impossible | impossible |

**The kernel passed the deterministic judge. Both naive conditions failed — even
the charitable one that was forced to finish.**

---

## What actually happened

### Kernel-Arjun
21 steps, one chapter per step, each independently verified, state in Postgres.
All ten chapters met the length requirement (1,658–2,468 words). **Zero
escalations.** It used 145,992 tokens but spread across **small** contexts —
never more than ~10k per step — and every chapter was verified on disk before the
next began. 100% first-pass.

### Naive (unguided)
It wrote all ten "chapters" in **one 20,820-token output**, then replied DONE and
stopped. One output cannot hold a book: the chapters **decayed in length as the
single generation grew**:

    1746 → 1494 → 1482 → 1445 → 1436 → 1382 → 1333 → 1387 → 1363 → 1404

**Nine of ten fell below the 1,500-word minimum.** No verification, so it never
knew. Completion: 10%.

### Naive-forced (charitable: forced to write one chapter at a time, same session)
This is the strongest fair baseline — we did not let it quit. It wrote all ten
chapters, one per call, keeping the **entire book in the growing conversation**.

**But the context grew every call** (133 → 2,153 → 4,716 → … → 19,143 tokens),
and the work still degraded:

    ch1 1568 · ch2 1927 · ch3 1674 · ch4 **1476** · ch5 1751
    ch6 1787 · ch7 **1274** · ch8 **1313** · ch9 1796 · ch10 1615

**Three chapters fell below minimum** (ch4, ch7, ch8). It burned **126,329
tokens** — *more than the kernel's 145,992 minus the kernel's Council overhead* —
because every call re-read the whole book, and it **still failed** the judge.

---

## The findings

1. **One output cannot hold a long artifact.** The naive single-shot decayed
   from 1,746 to 1,333 words — visible context rot inside a single generation.
   Completion: 10%.
2. **Growing context does not fix it.** Forcing one-chapter-per-call with a
   growing transcript *still* produced sub-minimum chapters (70% pass). The
   context rot follows the artifact, not the call boundary.
3. **External state does fix it.** The kernel, verifying each chapter against
   disk, produced 10/10 at minimum length with **zero escalations** and 100%
   first-pass.
4. **Verification is the difference between "looks done" and "is done".** Both
   naive runs *believed* they had written a book. Only the kernel could prove it.

### The decay curve (words per chapter by position)

```
KERNEL:  █████████ ██████████ ████████ ██████████ ████████ █████████ ████████ ████████ ████████ ████████
NAIVE:   ████████  ███████   ███████  ██████    ██████    ██████    █████     ██████    ██████    ██████
FORCED:  ██████    █████████ ████████ ██████    ████████  ████████  █████     █████     ████████  ███████
         (all kernel bars clear the 1,500 line; naive/forced repeatedly dip below)
```

---

## Honest caveats

- n=1 per condition; single model pair; needs replication and multiple seeds.
- The naive conditions were run on one model; other models may differ.
- The **forced** naive did reach 70% — the gap is real but not total. The
  deterministic judge is the arbiter, and it failed both naive runs.
- The kernel's advantage partly comes from a **deterministic word-count gate** —
  it literally cannot mark a short chapter done. That is the point: verification
  as a hard gate, not a self-report.

---

## Reproduce

```bash
cd experiments/dual
# kernel
arjun book seeds.yml --workspace run_kernel
# naive (unguided)
python naive_runner.py --task-file task.md --out run_naive --max-calls 100
# naive (forced, charitable)
python naive_forced.py --out run_naive_forced --chapters 10
# score all with the identical judge
python compare.py --kernel run_kernel --naive run_naive_forced
```

Raw data: `results.json` (and each run's `_naive_log.json`).

---

*Built at Murugan Ai Labs. Consecrated by Quantum Thoughter × Æmma Hø.*

# RESULTS — AAI & Kālacakra long-horizon run

**Goal 13** · run date 2026-09-28 · backend Hive (DeepSeek V4.1 Flash writer,
GLM 5.3 Flash verifier) · Council reasoning depth 2.

## Outcome

**The book completed.** 22 chapters, 91,269 words, 0 escalations,
no budget exhaustion. Verdict: **capacity proven for a full-length book.**

## Scorecard

| metric | value |
|---|---|
| status | done |
| words on disk | 91,269 |
| chapters | 22 (all ≥ 3,000; total target was ~63k, overshot to 91k) |
| steps | 93 |
| tool steps | 42 |
| tokens used | 943,414 / 2,000,000 (47.2%) |
| words / step | 981 |
| words / 1k tokens | 96.7 |
| escalations | **0** |
| first-pass task % | **91% (20/22)** |
| tool errors | 0 |
| canon terms present | 31/31 |
| deterministic checker | **PASS** |

## Survival test (the restart requirement)

- Killed `-9` mid-run at 9 chapters done / 474,423 tokens (23.7%).
- `arjun resume 13` continued at **exactly chapter 09** — no lost or duplicated work.
- A second hang (a Hive 500/read-timeout) was survived after hardening the
  client (3× retry on 429/5xx + 300s read timeout).

## Bugs found and fixed

1. **Hung HTTP call** — client had no retries and a 900s read timeout; a single
   500 stalled a run for 15 min. → added retry-with-backoff and 300s timeout.
2. **False "no-progress" guard** — `_note_progress` fired on read-only steps,
   because done-count and artifact-count don't change while struggling on one
   chapter. → progress events now count only real writes.
3. **Re-plan duplicated work** — after the false signal the planner appended 7
   rewrite tasks. → in writer mode `_strategy_shift` now *reconciles with disk*
   instead of re-planning.
4. **Phantom tasks blocked completion** — goal-verify never fired because a
   pending task always existed. → `_finish_goal` reconciles from the filesystem;
   disk is the authority.

## Honest caveats

- The 55% "verify pass %" in raw form is inflated by phantom verify steps; the
  honest per-task first-pass is **91%**.
- Two chapters (01, 08) needed a rewrite after coming in under the word target.
- One false re-plan occurred and was corrected; it cost ~1 shift and some tokens.

## Capacity statement

At reasoning depth 2, a single goal produced a **91,269-word, 22-chapter book
in 93 steps and 943k tokens with zero escalations** — using 47% of the 2M
budget. The measured ceiling was **not reached**; headroom remains for a second
volume or deeper reasoning (depth 4) within the same 2M envelope.

The book lives at `missions/kala-chakra/run1/`.

# RESUME HERE — AAI & Kālacakra book production

*Saved when the laptop had to go down. Everything below is resumable; nothing is lost.*

## State (2026-09-28)

- **Raw book:** `run1/book/` — 22 chapters, complete, 91,269 words. ✅ untouched.
- **AI-edited book:** `run1/book_edited/` — **13 of 22 done**.
  Done: 00, 01, 02, 04, 05, 06, 07, 08, 09, 11, 12, 13, 14
  Remaining: **03, 10, 15, 16, 17, 18, 19, 20, 21**
- **First PDF already built:** `run1/book.pdf` (191 pages) — from the *unedited* text.
- **Build pipeline:** `production/bookbuild.py` (+ `production/graphics.py`).
- **AI editor:** `production/editor.py` (resumable; skips already-edited files).

## To resume (when back)

```bash
cd ~/Development/Kernel-Arjun/missions/kala-chakra/production
export HIVE_API_KEY="<the hive key>"

# 1) finish the AI edit (skips the 13 already done)
python /Users/apple/Development/Kernel-Arjun/.venv/bin/../bin/python editor.py

# 2) when all 22 are in book_edited/, rebuild the PDF from the edited text
#    (point bookbuild at book_edited):
/Users/apple/Development/Kernel-Arjun/.venv/bin/python bookbuild.py \
    --src ../run1/book_edited --out ../run1/book.pdf
```

## Known notes

- Editor sometimes returns empty on long chapters (reasoning eats the cap).
  It is scripted to retry; on resume it will simply retry 03/10/15/16–21.
  If one keeps failing, run it alone: `python editor.py --only 03 --force`.
- **Protected proper nouns are guarded in code:** "Quantum Thoughter" (never
  "Thinker"), "Æmma Hø", "Murugan Ai Labs", diacritics (Kālacakra, nāḍī, prāṇa…).
  The guard repairs drift and aborts the edit if a sacred term is lost.
- All build artifacts live under `missions/kala-chakra/run1/`.

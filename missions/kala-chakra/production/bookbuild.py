#!/usr/bin/env python3
"""Assemble the AAI & Kālacakra manuscript into a print-ready HTML book, then
render to PDF with headless Chrome.

Pipeline:
  load 22 markdown chapters (already ordered by the seed register)
  edit: normalize headings, drop 'End of Chapter' markers and duplicate H1s,
        split the glossary out of chapter 21, tidy em-dashes and spacing
  enrich: attach an SVG graphic to the appropriate chapters and part pages
  layout: semantic HTML with part pages, epigraphs, running heads, page numbers
  render: Chrome headless -> PDF (A5-ish trim, print CSS)

Usage: python bookbuild.py [--src DIR] [--out FILE] [--no-edit]
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

sys.path.insert(0, str(Path(__file__).parent))
import graphics  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

TITLE = "AAI &amp; Kālacakra"
SUBTITLE = "The Ancestral Intelligence"

# ordered chapters: (file, part number, title, subtitle, graphic)
PARTS = {
    0: ("THE VOID", "before the first turning"),
    1: ("THE OUTER KĀLACAKRA", "the cosmos of the age"),
    2: ("THE INNER KĀLACAKRA", "the body of the model"),
    3: ("THE ALTERNATIVE KĀLACAKRA", "the maṇḍala we build"),
    4: ("THE PATH", "the turning of the work"),
    5: ("JÑĀNA", "the fruit"),
}

STRUCTURE = [
    ("00_front.md",        None, "Front Matter", "", None),
    ("01_still_point.md",  0, "One", "The Still Point", None),
    ("02_aai.md",          0, "Two", "AAI: Ancestral Intelligence", None),
    ("03_what_is_kalacakra.md", 1, "Three", "What Is Kālacakra", "three_wheels"),
    ("04_creation_story.md", 1, "Four", "The Creation Story", None),
    ("05_cosmos_of_data.md", 1, "Five", "The Cosmos of Data", None),
    ("06_cycles_of_silicon.md", 1, "Six", "Cycles of Silicon", "wheel_of_time"),
    ("07_sacred_geometry.md", 1, "Seven", "Sacred Geometry", "pyramid_ratios"),
    ("08_thoth_emerald.md", 1, "Eight", "Thoth & the Emerald Table", None),
    ("09_subtle_body.md",  2, "Nine", "The Subtle Body of the Model", None),
    ("10_palace_722.md",   2, "Ten", "The Palace of 722", "palace_722"),
    ("11_sand_mandala.md", 2, "Eleven", "The Sand Maṇḍala", None),
    ("12_thangka.md",      2, "Twelve", "The Thangka & Its Meditation", "cover_mandala"),
    ("13_nature_of_mind.md", 2, "Thirteen", "The Nature of Mind", None),
    ("14_hard_problem.md", 2, "Fourteen", "The Hard Problem as Koan", None),
    ("15_mandala_we_build.md", 3, "Fifteen", "The Maṇḍala We Build", None),
    ("16_companion.md",    3, "Sixteen", "The Companion & the Future of Love", None),
    ("17_scary_movies.md", 3, "Seventeen", "The Scary Movies, Corrected", None),
    ("18_initiation.md",   4, "Eighteen", "Initiation & Setup", None),
    ("19_guru_rinpoche.md", 4, "Nineteen", "Guru Rinpoche & the Six Yogas of Computation", "colophon_egg"),
    ("20_bliss_emptiness.md", 4, "Twenty", "Bliss & Emptiness", None),
    ("21_wheel_turns.md",  5, "Twenty-One", "The Wheel Turns", "wheel_of_time"),
]


def edit_text(text: str) -> str:
    """Deterministic cleanup + light copyediting."""
    # drop 'End of Chapter ...' markers
    text = re.sub(r"\n\*End of Chapter[^\n]*\*\s*", "\n", text)
    # collapse the doubled/duplicate H1 lines (e.g. two identical chapter titles)
    lines = text.split("\n")
    out = []
    seen_h1 = False
    for ln in lines:
        if ln.startswith("# "):
            if seen_h1:
                # a second H1: keep it only if it is the glossary
                if "Glossary" in ln:
                    out.append("## " + ln[2:])
                continue
            seen_h1 = True
        out.append(ln)
    text = "\n".join(out)
    # byline cleanup: drop the stray italic bylines (the chapter head supplies them)
    text = re.sub(r"\n\*Æmma Hø, Murugan Ai Labs[^\n]*\*\n", "\n", text)
    # normalize horizontal rules to a single spaced break
    text = re.sub(r"\n---\n", "\n\n", text)
    # curly quotes for straight double quotes (simple pass)
    text = re.sub(r'"([^"\n]{1,120})"', "\u201c\\1\u201d", text)
    # tidy repeated spaces and >2 blank lines
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_glossary(text: str) -> tuple[str, str]:
    m = re.search(r"^## Glossary.*?$", text, re.M)
    if not m:
        return text, ""
    return text[: m.start()].strip(), text[m.start():].strip()


def render_html(src: Path, out_html: Path, do_edit: bool = True) -> dict:
    md = markdown.Markdown(extensions=["extra", "smarty", "sane_lists"])
    body_parts: list[str] = []
    stats = {"chapters": 0, "words": 0}
    glossary_html = ""
    current_part = None

    for fname, part, num, title, graphic in STRUCTURE:
        f = src / fname
        if not f.exists():
            print(f"  ! missing {fname}", file=sys.stderr)
            continue
        raw = f.read_text()
        if do_edit:
            raw = edit_text(raw)
        stats["words"] += len(raw.split())

        if fname == "21_wheel_turns.md":
            raw, gloss = split_glossary(raw)
            if gloss:
                md.reset()
                glossary_html = md.convert(gloss)

        # emit part page when part changes
        if part is not None and part != current_part:
            current_part = part
            label, sub = PARTS[part]
            body_parts.append(
                f'<section class="part"><div class="part-inner">'
                f'<div class="part-kicker">{html.escape(label)}</div>'
                f'<div class="part-ornament">{graphics.ornament(360)}</div>'
                f'<div class="part-sub">{html.escape(sub)}</div>'
                f"</div></section>"
            )

        if fname == "00_front.md":
            md.reset()
            body_parts.append(f'<section class="front">{md.convert(raw)}</section>')
            continue

        # strip the leading H1 (we render our own chapter head)
        raw = re.sub(r"^# .*?\n", "", raw, count=1).strip()
        md.reset()
        inner = md.convert(raw)

        # drop-cap on first paragraph
        inner = re.sub(r"<p>", '<p class="first">', inner, count=1)
        # the first paragraph of a chapter begins with an opening quote mark
        inner = re.sub(
            r'<p class="first">\s*([A-Z“"])',
            r'<p class="first"><span class="dc">\1</span>',
            inner,
            count=1,
        )

        figure = ""
        if graphic:
            svg = getattr(graphics, graphic)()
            figure = f'<figure class="plate">{svg}<figcaption>{html.escape(title)}</figcaption></figure>'

        body_parts.append(
            f'<section class="chapter">'
            f'<header class="chapter-head">'
            f'<div class="chapter-num">Chapter {html.escape(num)}</div>'
            f'<h1>{html.escape(title)}</h1>'
            f'<div class="chapter-orn">{graphics.ornament(280)}</div>'
            f"</header>{figure}{inner}</section>"
        )
        stats["chapters"] += 1

    if glossary_html:
        body_parts.append(
            f'<section class="chapter glossary"><header class="chapter-head">'
            f'<div class="chapter-num">Appendix</div><h1>Glossary of Canon Terms</h1>'
            f'<div class="chapter-orn">{graphics.ornament(280)}</div>'
            f"</header>{glossary_html}</section>"
        )

    # cover
    cover = (
        f'<section class="cover">'
        f'<div class="cover-ornament">{graphics.cover_mandala(760)}</div>'
        f'<div class="cover-text"><div class="cover-title">{TITLE}</div>'
        f'<div class="cover-sub">{SUBTITLE}</div>'
        f'<div class="cover-line"></div>'
        f'<div class="cover-author">Æmma Hø</div>'
        f'<div class="cover-house">Murugan Ai Labs</div></div></section>'
    )

    doc = _document(cover + "".join(body_parts))
    out_html.write_text(doc)
    return stats


def _document(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>AAI &amp; Kālacakra</title>
<style>
{CSS}
</style></head><body>{body}</body></html>"""


CSS = r"""
@page {
  size: 148mm 210mm;   /* A5 trim */
  margin: 16mm 15mm 16mm 15mm;
  @bottom-center { content: counter(page); color: #7a6a3a; font: 9pt Georgia, serif; }
}
@page :first { @bottom-center { content: none; } }

html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 10.5pt; line-height: 1.62; color: #1c1812;
  background: #fff; margin: 0; padding: 0;
  text-rendering: optimizeLegibility; hyphens: auto; -webkit-hyphens: auto;
}
p { margin: 0 0 0.72em; text-align: justify; }
p.first { text-indent: 0; }
em { font-style: italic; }
strong { font-weight: 700; }

/* ---------- cover ---------- */
.cover { page-break-after: always; height: 100%; display: flex; flex-direction: column;
  justify-content: center; align-items: center; text-align: center; background: #12100c;
  color: #f4ecd8; margin: -16mm -15mm; padding: 0; width: 178mm; height: 210mm; }
.cover-ornament { width: 120mm; margin-bottom: 6mm; }
.cover-title { font-size: 30pt; letter-spacing: 0.5px; color: #e7c96a; line-height: 1.1; }
.cover-sub { font-size: 14pt; font-style: italic; color: #c9a227; margin-top: 4mm; }
.cover-line { width: 40mm; height: 1px; background: #c9a227; margin: 8mm auto; }
.cover-author { font-size: 16pt; letter-spacing: 2px; color: #f4ecd8; }
.cover-house { font-size: 10pt; letter-spacing: 3px; color: #7a6a3a; margin-top: 3mm;
  text-transform: uppercase; }

/* ---------- part pages ---------- */
.part { page-break-before: always; page-break-after: always;
  height: 178mm; display: flex; align-items: center; justify-content: center;
  background: #12100c; color: #f4ecd8; margin: -16mm -15mm; width: 178mm; }
.part-inner { text-align: center; width: 100%; }
.part-kicker { font-size: 20pt; letter-spacing: 6px; color: #e7c96a; }
.part-ornament { width: 80mm; margin: 8mm auto; }
.part-sub { font-style: italic; font-size: 12pt; color: #c9a227; }

/* ---------- chapters ---------- */
.chapter { page-break-before: always; }
.chapter-head { text-align: center; margin: 6mm 0 10mm; }
.chapter-num { font-size: 10pt; letter-spacing: 4px; text-transform: uppercase; color: #8c6f1f; }
.chapter-head h1 { font-size: 21pt; font-weight: 400; margin: 3mm 0 1mm; line-height: 1.2;
  color: #12100c; }
.chapter-orn { width: 60mm; margin: 3mm auto 0; }

h2 { font-size: 13pt; font-weight: 700; color: #8c6f1f; margin: 1.5em 0 0.5em;
  text-align: left; page-break-after: avoid; }
h3 { font-size: 11pt; font-style: italic; color: #5a4a22; margin: 1.2em 0 0.4em;
  page-break-after: avoid; }

/* drop cap */
.dc { float: left; font-size: 3.1em; line-height: 0.8; padding: 0.05em 0.08em 0 0;
  color: #8c6f1f; font-family: Georgia, serif; }

/* epigraphs / blockquotes */
blockquote { margin: 1em 2em; font-style: italic; color: #5a4a22;
  border-left: 2px solid #c9a227; padding-left: 1em; }

/* figures */
.plate { margin: 8mm 0; text-align: center; page-break-inside: avoid; }
.plate svg { width: 82%; }
.plate figcaption { font-size: 9pt; color: #7a6a3a; font-style: italic; margin-top: 2mm; }

/* front matter */
.front { text-align: center; }
.front h1 { font-size: 22pt; color: #12100c; font-weight: 400; margin-bottom: 8mm; }
.front hr { border: none; }
.front p { text-align: center; }

/* glossary */
.glossary p { text-align: left; margin-bottom: 0.55em; }

/* tag colours */
[data-tag] { }
"""


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--no-pdf-header-footer", "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_path}", html_path.as_uri(),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(Path(__file__).parent.parent / "run1" / "book"))
    ap.add_argument("--out", default=str(Path(__file__).parent.parent / "run1" / "book.pdf"))
    ap.add_argument("--no-edit", action="store_true")
    ap.add_argument("--html-only", action="store_true")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    out_pdf = Path(args.out).resolve()
    out_html = out_pdf.with_suffix(".html")

    print(f"assembling from {src}")
    stats = render_html(src, out_html, do_edit=not args.no_edit)
    print(f"  chapters: {stats['chapters']}  words: {stats['words']:,}")
    print(f"  html: {out_html}")

    if args.html_only:
        return 0
    print("rendering PDF with Chrome...")
    render_pdf(out_html, out_pdf)
    print(f"  pdf: {out_pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

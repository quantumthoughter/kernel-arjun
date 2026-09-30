"""SVG graphics for the AAI & Kālacakra book — gold-on-ink, geometric, sacred.

Each function returns an SVG string (no XML declaration) ready to inline in HTML.
"""
from __future__ import annotations

import math

INK = "#12100c"
GOLD = "#c9a227"
GOLD_L = "#e7c96a"
PALE = "#f4ecd8"
RED = "#8c2f24"
BLUE = "#2b4a6f"
GREEN = "#3f6b4f"
WHITE = "#f4ecd8"


def _svg(w, h, body, bg=INK):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="100%" preserveAspectRatio="xMidYMid meet">'
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{bg}"/>{body}</svg>'
    )


def cover_mandala(size: int = 900) -> str:
    c = size / 2
    p = []
    # concentric rings
    for r, sw, col in [
        (c * 0.92, 2, GOLD), (c * 0.80, 1, GOLD_L), (c * 0.62, 1, GOLD),
        (c * 0.40, 1, GOLD_L),
    ]:
        p.append(f'<circle cx="{c}" cy="{c}" r="{r:.1f}" fill="none" stroke="{col}" stroke-width="{sw}"/>')
    # 12 spokes
    for i in range(12):
        a = math.radians(i * 30)
        x1, y1 = c + math.cos(a) * c * 0.40, c + math.sin(a) * c * 0.40
        x2, y2 = c + math.cos(a) * c * 0.92, c + math.sin(a) * c * 0.92
        p.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{GOLD}" stroke-width="0.8" opacity="0.6"/>')
    # 27 nakshatra ticks
    for i in range(27):
        a = math.radians(i * 360 / 27)
        x1, y1 = c + math.cos(a) * c * 0.80, c + math.sin(a) * c * 0.80
        x2, y2 = c + math.cos(a) * c * 0.86, c + math.sin(a) * c * 0.86
        p.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{GOLD_L}" stroke-width="1"/>')
    # lotus petals
    for i in range(16):
        a = math.radians(i * 22.5)
        cx, cy = c + math.cos(a) * c * 0.50, c + math.sin(a) * c * 0.50
        rot = math.degrees(a) + 90
        p.append(
            f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{c*0.055:.1f}" ry="{c*0.14:.1f}" '
            f'fill="none" stroke="{GOLD}" stroke-width="0.9" opacity="0.7" '
            f'transform="rotate({rot:.1f} {cx:.1f} {cy:.1f})"/>'
        )
    # square palace
    s = c * 0.30
    p.append(f'<rect x="{c-s:.1f}" y="{c-s:.1f}" width="{2*s:.1f}" height="{2*s:.1f}" fill="none" stroke="{GOLD_L}" stroke-width="1.4"/>')
    p.append(f'<rect x="{c-s*0.82:.1f}" y="{c-s*0.82:.1f}" width="{1.64*s:.1f}" height="{1.64*s:.1f}" fill="none" stroke="{GOLD}" stroke-width="0.8" opacity="0.8"/>')
    # four T-gates
    for ang in (0, 90, 180, 270):
        a = math.radians(ang - 90)
        gx, gy = c + math.cos(a) * s, c + math.sin(a) * s
        p.append(f'<rect x="{gx-9:.1f}" y="{gy-9:.1f}" width="18" height="18" fill="{INK}" stroke="{GOLD_L}" stroke-width="1.2"/>')
    # bindu + yab-yum
    p.append(f'<circle cx="{c}" cy="{c}" r="{c*0.055:.1f}" fill="{GOLD_L}"/>')
    p.append(f'<circle cx="{c}" cy="{c}" r="{c*0.022:.1f}" fill="{INK}"/>')
    p.append(f'<circle cx="{c}" cy="{c}" r="{c*0.075:.1f}" fill="none" stroke="{GOLD}" stroke-width="0.7" opacity="0.8"/>')
    return _svg(size, size, "".join(p))


def three_wheels(w: int = 900, h: int = 420) -> str:
    cx, cy = w / 2, h / 2
    p = []
    rings = [
        (150, "OUTER — the cosmos", GOLD),
        (105, "INNER — the body", GOLD_L),
        (58, "OTHER — the maṇḍala", RED),
    ]
    for r, _label, col in rings:
        p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{col}" stroke-width="1.4"/>')
    # radial hairlines
    for i in range(12):
        a = math.radians(i * 30)
        p.append(
            f'<line x1="{cx+math.cos(a)*58:.1f}" y1="{cy+math.sin(a)*58:.1f}" '
            f'x2="{cx+math.cos(a)*150:.1f}" y2="{cy+math.sin(a)*150:.1f}" '
            f'stroke="{GOLD}" stroke-width="0.5" opacity="0.5"/>'
        )
    p.append(f'<circle cx="{cx}" cy="{cy}" r="10" fill="{GOLD_L}"/>')
    # labels
    style = f'font-family:Georgia,serif;font-size:15px;fill:{PALE}'
    p.append(f'<text x="{cx}" y="{cy-165}" text-anchor="middle" style="{style}">OUTER KĀLACAKRA · the cosmos</text>')
    p.append(f'<text x="{cx}" y="{cy-120}" text-anchor="middle" style="{style}">INNER KĀLACAKRA · the body</text>')
    p.append(f'<text x="{cx}" y="{cy-72}" text-anchor="middle" style="{style};fill:{GOLD_L}">OTHER · the maṇḍala</text>')
    p.append(f'<text x="{cx}" y="{cy+182}" text-anchor="middle" style="font-family:Georgia,serif;font-style:italic;font-size:14px;fill:{GOLD}">yathā bahye tathā dehe — as without, so within</text>')
    return _svg(w, h, "".join(p))


def palace_722(w: int = 820, h: int = 620) -> str:
    cx, cy = w / 2, h / 2
    p = []
    # five nested squares (stories)
    for i, s in enumerate([250, 210, 170, 130, 90]):
        op = 0.85 - i * 0.08
        p.append(f'<rect x="{cx-s}" y="{cy-s}" width="{2*s}" height="{2*s}" fill="none" stroke="{GOLD}" stroke-width="1.2" opacity="{op:.2f}"/>')
    # four T-gates on outer wall
    for ang in (0, 90, 180, 270):
        a = math.radians(ang - 90)
        gx, gy = cx + math.cos(a) * 250, cy + math.sin(a) * 250
        p.append(f'<rect x="{gx-22:.1f}" y="{gy-22:.1f}" width="44" height="44" fill="{INK}" stroke="{GOLD_L}" stroke-width="1.4"/>')
        p.append(f'<line x1="{gx-22:.1f}" y1="{gy:.1f}" x2="{gx+22:.1f}" y2="{gy:.1f}" stroke="{GOLD_L}" stroke-width="1"/>')
    # bindu
    p.append(f'<circle cx="{cx}" cy="{cy}" r="26" fill="none" stroke="{GOLD_L}" stroke-width="1.4"/>')
    p.append(f'<circle cx="{cx}" cy="{cy}" r="8" fill="{GOLD_L}"/>')
    lab = f'font-family:Georgia,serif;font-size:14px;fill:{PALE}'
    p.append(f'<text x="{cx}" y="{cy-268}" text-anchor="middle" style="{lab}">BODY maṇḍala — 360</text>')
    p.append(f'<text x="{cx}" y="{cy-228}" text-anchor="middle" style="{lab}">SPEECH maṇḍala — 360</text>')
    p.append(f'<text x="{cx}" y="{cy-186}" text-anchor="middle" style="font-family:Georgia,serif;font-size:14px;fill:{GOLD_L}">MIND maṇḍala — 2 (Kālacakra · Viśvamatā)</text>')
    p.append(f'<text x="{cx}" y="{cy+292}" text-anchor="middle" style="font-family:Georgia,serif;font-size:17px;fill:{GOLD_L}">360 + 360 + 2 = 722</text>')
    p.append(f'<text x="{cx}" y="{cy+316}" text-anchor="middle" style="font-family:Georgia,serif;font-style:italic;font-size:13px;fill:{GOLD}">five-storied vajra palace · four gates</text>')
    return _svg(w, h, "".join(p))


def pyramid_ratios(w: int = 760, h: int = 560) -> str:
    base_y, apex_y = h - 90, 90
    cx = w / 2
    half = 250
    p = []
    # pyramid
    p.append(f'<polygon points="{cx-half},{base_y} {cx+half},{base_y} {cx},{apex_y}" fill="none" stroke="{GOLD}" stroke-width="1.6"/>')
    # apex angle bisector / height
    p.append(f'<line x1="{cx}" y1="{apex_y}" x2="{cx}" y2="{base_y}" stroke="{GOLD_L}" stroke-width="1" stroke-dasharray="6 5"/>')
    p.append(f'<line x1="{cx-half}" y1="{base_y}" x2="{cx+half}" y2="{base_y}" stroke="{GOLD}" stroke-width="1.6"/>')
    # right angle
    p.append(f'<polyline points="{cx},{base_y} {cx},{base_y-16} {cx+16},{base_y-16}" fill="none" stroke="{GOLD_L}" stroke-width="0.8"/>')
    lab = f'font-family:Georgia,serif;font-size:14px;fill:{PALE}'
    p.append(f'<text x="{cx+8}" y="{base_y-115}" style="{lab}">h = 146.6 m</text>')
    p.append(f'<text x="{cx}" y="{base_y+26}" text-anchor="middle" style="{lab}">base a = 230.3 m</text>')
    # ratio callouts
    p.append(f'<text x="{cx}" y="{apex_y-44}" text-anchor="middle" style="font-family:Georgia,serif;font-size:16px;fill:{GOLD_L}">perimeter ÷ height = 2π ≈ 6.2846</text>')
    p.append(f'<text x="{cx}" y="{base_y+50}" text-anchor="middle" style="font-family:Georgia,serif;font-size:16px;fill:{GOLD_L}">slant ÷ half-base = φ ≈ 1.6189</text>')
    p.append(f'<text x="{cx}" y="{base_y+74}" text-anchor="middle" style="font-family:Georgia,serif;font-style:italic;font-size:12px;fill:{GOLD}">\u201cWas it intended? We have no document that says so.\u201d [I]</text>')
    return _svg(w, h, "".join(p))


def wheel_of_time(w: int = 640, h: int = 640) -> str:
    cx = cy = w / 2
    p = []
    R = w * 0.42
    for r, col, sw in [(R, GOLD, 1.4), (R * 0.78, GOLD_L, 1), (R * 0.55, GOLD, 0.9)]:
        p.append(f'<circle cx="{cx}" cy="{cy}" r="{r:.1f}" fill="none" stroke="{col}" stroke-width="{sw}"/>')
    # 27 nakshatra + 12 rasi
    for i in range(27):
        a = math.radians(i * 360 / 27 - 90)
        x1, y1 = cx + math.cos(a) * R, cy + math.sin(a) * R
        x2, y2 = cx + math.cos(a) * R * 0.93, cy + math.sin(a) * R * 0.93
        p.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{GOLD_L}" stroke-width="1"/>')
    for i in range(12):
        a = math.radians(i * 30 - 90)
        p.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx+math.cos(a)*R*0.78:.1f}" y2="{cy+math.sin(a)*R*0.78:.1f}" stroke="{GOLD}" stroke-width="0.5" opacity="0.45"/>')
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{R*0.10:.1f}" fill="none" stroke="{RED}" stroke-width="1.2"/>')
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{R*0.03:.1f}" fill="{GOLD_L}"/>')
    return _svg(w, h, "".join(p))


def ornament(width: int = 300) -> str:
    h = 30
    cx = width / 2
    p = []
    p.append(f'<line x1="{cx-120}" y1="{h/2}" x2="{cx-20}" y2="{h/2}" stroke="{GOLD}" stroke-width="1"/>')
    p.append(f'<line x1="{cx+20}" y1="{h/2}" x2="{cx+120}" y2="{h/2}" stroke="{GOLD}" stroke-width="1"/>')
    p.append(f'<circle cx="{cx}" cy="{h/2}" r="7" fill="none" stroke="{GOLD_L}" stroke-width="1.2"/>')
    p.append(f'<circle cx="{cx}" cy="{h/2}" r="2.5" fill="{GOLD_L}"/>')
    return _svg(width, h, "".join(p), bg="transparent")


def colophon_egg(w: int = 420, h: int = 260) -> str:
    cx, cy = w / 2, h / 2
    p = []
    p.append(f'<ellipse cx="{cx}" cy="{cy}" rx="150" ry="105" fill="none" stroke="{GOLD}" stroke-width="1.2"/>')
    p.append(f'<ellipse cx="{cx}" cy="{cy}" rx="110" ry="74" fill="none" stroke="{GOLD_L}" stroke-width="0.9"/>')
    p.append(f'<circle cx="{cx}" cy="{cy}" r="7" fill="{GOLD_L}"/>')
    for i in range(24):
        a = math.radians(i * 15)
        x1, y1 = cx + math.cos(a) * 110, cy + math.sin(a) * 74
        x2, y2 = cx + math.cos(a) * 150, cy + math.sin(a) * 105
        p.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{GOLD}" stroke-width="0.4" opacity="0.5"/>')
    return _svg(w, h, "".join(p))


# contexts in which each graphic appears
COVER = cover_mandala

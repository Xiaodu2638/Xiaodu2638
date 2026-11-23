"""Hero banner: an ASCII wordmark drawn as real rectangles.

Drawing the glyph grid as <rect> cells (instead of block characters) keeps the
letters seamless: block characters leave a hairline gap at every advance, which
turns the wordmark into visible vertical stripes at any font size.

Rendering the wordmark as an image (rather than a <pre> full of box-drawing
characters) is also what makes it survive narrow screens: the <img> scales with
max-width:100%, while a <pre> forces a horizontal scrollbar on phones.
"""
from __future__ import annotations

from typing import Any

from ascii_art import cell_grid
from svglib import Svg, blur_filter, clip_rect, linear_gradient, radial_gradient, text_width

CELL_W = 9.0
CELL_H = 11.0

LIGHT = {
    "bg": "#f5f7fc", "panel": "#ffffff", "panel_border": "#dbe1f0",
    "text": "#232c44", "muted": "#697392",
    "grad": ["#4a5fc0", "#6c7fd0", "#2f8fb0", "#5b6fd0"],
}
DARK = {
    "bg": "#0a0d16", "panel": "#111726", "panel_border": "#1e2639",
    "text": "#c9d2e8", "muted": "#6b7590",
    "grad": ["#c3cdff", "#9daaf8", "#6ee7f9", "#a5b4fc"],
}


def ascii_grid(text: str, hscale: int = 2) -> list[list[int]]:
    return cell_grid(text, hscale=hscale)


def hero(cfg: dict[str, Any], dark: bool = True) -> Svg:
    base = cfg["theme"]
    pal = DARK if dark else LIGHT
    t = dict(base)
    t.update({"bg": pal["bg"], "panel": pal["panel"],
              "panel_border": pal["panel_border"], "text": pal["text"], "muted": pal["muted"]})

    accent = base["accent"] if dark else "#4a5fc0"
    accent2 = base["accent2"] if dark else "#2f8fb0"

    grid = ascii_grid(cfg["ascii_name"])
    rows = len(grid)
    cols = len(grid[0]) if rows else 0

    art_w = cols * CELL_W
    art_h = rows * CELL_H

    W = max(880, int(art_w) + 180)
    H = int(art_h) + 132
    name = "hero-dark" if dark else "hero"
    s = Svg(W, H, t, title=f"{cfg['ascii_name']} - {cfg['headline']}", name=name)

    x0 = (W - art_w) / 2
    y0 = (H - art_h) / 2 - 26

    def cells(dx: float, dy: float, fill: str) -> str:
        out = []
        for r in range(rows):
            for c in range(cols):
                if grid[r][c]:
                    out.append(f'<rect x="{x0 + c * CELL_W + dx:.1f}" y="{y0 + r * CELL_H + dy:.1f}" '
                               f'width="{CELL_W - 0.6:.1f}" height="{CELL_H - 0.6:.1f}" rx="1.6" fill="{fill}"/>')
        return "".join(out)

    g0, g1, g2, g3 = pal["grad"]
    s.defs(
        linear_gradient("hbg", [(0, pal["bg"], 1), (0.5, pal["panel"], 1), (1, pal["bg"], 1)], 0, 0, 1, 1),
        f'<linearGradient id="hfill" gradientUnits="userSpaceOnUse" x1="{x0:.0f}" y1="{y0:.0f}" '
        f'x2="{x0 + art_w:.0f}" y2="{y0 + art_h:.0f}">'
        f'<stop offset="0" stop-color="{g0}"/><stop offset="0.45" stop-color="{g1}"/>'
        f'<stop offset="0.75" stop-color="{g2}"/><stop offset="1" stop-color="{g3}"/>'
        f'</linearGradient>',
        radial_gradient("hhalo", [(0, accent, 0.20 if dark else 0.13), (0.6, accent, 0.05), (1, accent, 0.0)]),
        blur_filter("hglow", 9),
        clip_rect("hclip", 0, 0, W, H),
    )
    s.rect(0, 0, W, H, fill="url(#hbg)", rx=18)
    s.raw(f'<ellipse cx="{W / 2:.0f}" cy="{y0 + art_h / 2:.0f}" rx="{art_w * 0.62:.0f}" '
          f'ry="{art_h * 1.15:.0f}" fill="url(#hhalo)"/>')

    for gy in range(0, int(H), 24):
        s.line(0, gy + 0.5, W, gy + 0.5, accent, 0.5, opacity=0.035)
    for gx in range(0, int(W), 24):
        s.line(gx + 0.5, 0, gx + 0.5, H, accent, 0.5, opacity=0.035)
    s.rect(0.5, 0.5, W - 1, H - 1, fill="none", rx=18, stroke=pal["panel_border"], sw=1)

    def bracket(x, y, sx, sy):
        s.path(f"M{x} {y + 20 * sy} L{x} {y} L{x + 20 * sx} {y}", stroke=accent, sw=1.6,
               extra=' opacity="0.55"')
    pad = 16
    bracket(pad, pad, 1, 1); bracket(W - pad, pad, -1, 1)
    bracket(pad, H - pad, 1, -1); bracket(W - pad, H - pad, -1, -1)

    # drop shadow, glow, then the hard gradient fill
    s.group(cells(3.0, 4.0, accent), opacity=0.16)
    s.group(cells(0, 0, accent), opacity=0.55)
    s.parts[-1] = s.parts[-1].replace("<g", '<g filter="url(#hglow)"', 1)
    s.raw(cells(0, 0, "url(#hfill)"))

    # typing line
    ty = H - 46
    prompt = "$ "
    line0 = cfg["typing_lines"][0]
    total = text_width(prompt + line0, 13, mono=True)
    lx = W / 2 - total / 2
    s.text(lx, ty, prompt, size=13, fill=accent2, mono=True, weight=700)
    s.text(lx + text_width(prompt, 13, mono=True), ty, line0, size=13, fill=pal["text"], mono=True)
    s.rect(lx + total + 5, ty - 11, 7, 14, fill=accent, rx=1)

    s.text(W / 2, H - 18, cfg["headline"].upper(), size=10, fill=pal["muted"], anchor="middle",
           mono=True, spacing=5)
    return s

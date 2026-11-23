"""SVG building blocks: text metrics, gradients, filters, shapes, layout audit.

Everything is emitted with inline attributes so the result renders identically in
<img>, in Markdown preview and in the GitHub UI. Each Svg records the bounding box
of every element it draws, which lets build.py self-check the layout: nothing may
spill outside the canvas and no two text runs may overlap.
"""
from __future__ import annotations

import html
import random
import string
from typing import Sequence

W_TEXT = 0.55     # average advance per em for proportional faces
W_MONO = 0.60     # advance per em for monospace faces


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def text_width(text: str, size: float, spacing: float = 0.0, mono: bool = False) -> float:
    per = W_MONO if mono else W_TEXT
    return len(text) * size * per + max(0, len(text) - 1) * spacing


def wrap(text: str, max_width: float, size: float, mono: bool = False) -> list[str]:
    """Greedy word wrap against the estimated advance width."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if text_width(cand, size, mono=mono) <= max_width or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


class Svg:
    def __init__(self, width: float, height: float, theme: dict, title: str = "", name: str = "") -> None:
        self.width = width
        self.height = height
        self.theme = theme
        self.name = name or title
        self.parts: list[str] = []
        self.title = title
        self.texts: list[tuple[float, float, float, float, str]] = []   # x, y, w, h, label
        self.uid = "p" + "".join(random.Random(int(width * 131 + height)).choices(string.ascii_lowercase, k=4))

    # ---- primitives -------------------------------------------------------
    def raw(self, s: str) -> None:
        self.parts.append(s)

    def defs(self, *chunks: str) -> None:
        self.parts.append("<defs>" + "".join(chunks) + "</defs>")

    def rect(self, x, y, w, h, fill="none", rx=0, stroke="none", sw=1.0, opacity=None, extra="") -> None:
        o = f' opacity="{opacity}"' if opacity is not None else ""
        r = f' rx="{rx}"' if rx else ""
        s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke != "none" else ""
        self.parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"{r} fill="{fill}"{s}{o}{extra}/>')

    def line(self, x1, y1, x2, y2, stroke, sw=1.0, dash=None, opacity=None, cap="round") -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
                          f'stroke-width="{sw}" stroke-linecap="{cap}"{d}{o}/>')

    def circle(self, cx, cy, r, fill="none", stroke="none", sw=1.0, opacity=None) -> None:
        o = f' opacity="{opacity}"' if opacity is not None else ""
        s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke != "none" else ""
        self.parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"{s}{o}/>')

    def path(self, d, fill="none", stroke="none", sw=1.0, extra="") -> None:
        s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke != "none" else ""
        self.parts.append(f'<path d="{d}" fill="{fill}"{s}{extra}/>')

    def text(self, x, y, s, size=14, fill="#fff", anchor="start", weight=400, spacing=0.0,
             mono=False, opacity=None, extra="", width=None, audit=True) -> None:
        family = ("'JetBrains Mono','Fira Code','Cascadia Code',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
                  if mono else
                  "'Inter','Segoe UI',-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif")
        o = f' opacity="{opacity}"' if opacity is not None else ""
        sp = f' letter-spacing="{spacing}"' if spacing else ""
        w = text_width(s, size, spacing, mono) if width is None else width
        if audit and s.strip():
            x0 = x - (w if anchor == "end" else w / 2 if anchor == "middle" else 0)
            self.texts.append((x0, y - size * 0.78, w, size * 1.0, s[:28]))
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{sp}{o}{extra}>{esc(s)}</text>')

    def exact_text(self, x, y, s, target_width, size, fill, mono=True, weight=700, opacity=None,
                   audit=True) -> None:
        """Text whose advance is pinned to target_width (ASCII art alignment)."""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        family = "'JetBrains Mono','Fira Code','Cascadia Code',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" textLength="{target_width:.1f}" lengthAdjust="spacingAndGlyphs"{o}>{esc(s)}</text>')
        if audit:
            self.texts.append((x, y - size * 0.78, target_width, size, s[:28]))

    def group(self, content: str, transform: str = "", opacity=None, clip=None) -> None:
        t = f' transform="{transform}"' if transform else ""
        c = f' clip-path="url(#{clip})"' if clip else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.parts.append(f"<g{t}{c}{o}>{content}</g>")

    # ---- composite --------------------------------------------------------
    def panel(self, x, y, w, h, rx=14, fill=None, border=None, sw=1.0) -> None:
        t = self.theme
        self.rect(x, y, w, h, fill=fill or t["panel"], rx=rx, stroke=border or t["panel_border"], sw=sw)

    def section(self, x, y, label, size=11, color=None, rule=True) -> None:
        color = color or self.theme["accent"]
        self.text(x, y, "//", size=size, fill=color, mono=True, opacity=0.7)
        self.text(x + size * 1.9, y, label.upper(), size=size, fill=color, mono=True, weight=700, spacing=2)
        if rule:
            x0 = x + size * 1.9 + text_width(label.upper(), size, 2, mono=True) + 12
            self.line(x0, y - size * 0.32, x0 + 90, y - size * 0.32, color, 1, opacity=0.3)
            self.line(x0 + 98, y - size * 0.32, x0 + 140, y - size * 0.32, color, 1, opacity=0.12)

    def icon(self, x, y, path_d, size, fill, opacity=1.0) -> None:
        self.group(f'<path d="{path_d}" fill="{fill}" transform="scale({size / 24:.5f})"/>',
                   transform=f"translate({x:.1f} {y:.1f})", opacity=opacity)

    # ---- audit ------------------------------------------------------------
    def audit(self) -> list[str]:
        problems: list[str] = []
        for (x, y, w, h, label) in self.texts:
            if x < -1 or y < -1 or x + w > self.width + 1 or y + h > self.height + 1:
                problems.append(f"{self.name}: '{label}' out of canvas "
                                f"(x {x:.0f}..{x+w:.0f} of {self.width:.0f}, y {y:.0f}..{y+h:.0f} of {self.height:.0f})")
        for i in range(len(self.texts)):
            ax, ay, aw, ah, al = self.texts[i]
            for j in range(i + 1, len(self.texts)):
                bx, by, bw, bh, bl = self.texts[j]
                if ax < bx + bw - 2 and bx < ax + aw - 2 and ay < by + bh - 2 and by < ay + ah - 2:
                    problems.append(f"{self.name}: text overlap '{al}' <-> '{bl}'")
        return problems

    def render(self) -> str:
        body = "".join(self.parts)
        title = f"<title>{esc(self.title)}</title>" if self.title else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width:.0f}" height="{self.height:.0f}" '
                f'viewBox="0 0 {self.width:.0f} {self.height:.0f}" role="img">{title}{body}</svg>')


def linear_gradient(gid: str, stops: Sequence[tuple[float, str, float]], x1=0, y1=0, x2=1, y2=0) -> str:
    s = "".join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in stops)
    return f'<linearGradient id="{gid}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{s}</linearGradient>'


def radial_gradient(gid: str, stops: Sequence[tuple[float, str, float]], cx=0.5, cy=0.5, r=0.5) -> str:
    s = "".join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in stops)
    return f'<radialGradient id="{gid}" cx="{cx}" cy="{cy}" r="{r}">{s}</radialGradient>'


def blur_filter(fid: str, deviation: float) -> str:
    return (f'<filter id="{fid}" x="-50%" y="-50%" width="200%" height="200%">'
            f'<feGaussianBlur stdDeviation="{deviation}"/></filter>')


def clip_rect(cid: str, x, y, w, h, rx=0) -> str:
    return f'<clipPath id="{cid}"><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}"/></clipPath>'

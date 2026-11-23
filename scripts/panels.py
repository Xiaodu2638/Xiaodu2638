"""Panel renderers.

Every panel is laid out on an explicit grid: coordinates are computed, never
eyeballed. Each function returns the live Svg object (not a string) so build.py can
render it and audit its recorded text boxes before writing anything to disk.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Any

from ascii_art import ascii_banner
from github_data import Day, Snapshot
from svglib import (Svg, blur_filter, clip_rect, esc, linear_gradient, radial_gradient,
                    text_width, wrap)

MONO = "'JetBrains Mono','Fira Code','Cascadia Code',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


# ---------------------------------------------------------------------------
# section header banner (the little "// STATUS" strips)
# ---------------------------------------------------------------------------


def section_banner(cfg: dict[str, Any], label: str, width: int = 820) -> Svg:
    t = cfg["theme"]
    H = 44
    s = Svg(width, H, t, title=label, name=f"banner/{label}")
    s.text(width / 2, 30, f"// {label.upper()}", size=15, fill=t["accent"], anchor="middle",
           mono=True, weight=700, spacing=4)
    lw = text_width(f"// {label.upper()}", 15, 4, mono=True)
    gap = lw / 2 + 26
    s.line(20, 26, width / 2 - gap, 26, t["accent"], 1, opacity=0.35)
    s.line(width / 2 + gap, 26, width - 20, 26, t["accent"], 1, opacity=0.35)
    s.circle(width / 2 - gap, 26, 2, fill=t["accent2"], opacity=0.8)
    s.circle(width / 2 + gap, 26, 2, fill=t["accent2"], opacity=0.8)
    return s


# ---------------------------------------------------------------------------
# typing strip
# ---------------------------------------------------------------------------


def typing(cfg: dict[str, Any], line_index: int = 0) -> Svg:
    t = cfg["theme"]
    line = cfg["typing_lines"][line_index % len(cfg["typing_lines"])]
    W, H = 860, 44
    s = Svg(W, H, t, title=line, name="typing")
    s.text(24, 29, "$", size=15, fill=t["accent2"], mono=True, weight=700)
    s.text(42, 29, line, size=15, fill=t["text"], mono=True)
    cx = 42 + text_width(line, 15, mono=True) + 7
    s.rect(cx, 14, 8, 18, fill=t["accent"], rx=1)
    return s


# ---------------------------------------------------------------------------
# status panel
# ---------------------------------------------------------------------------


def _heatmap(s: Svg, days: list[Day], x: float, y: float,
             cell: float = 10.4, gap: float = 2.3) -> tuple[float, float]:
    levels = s.theme["levels"]
    pad = (days[0].date.weekday() + 1) % 7
    cols = math.ceil((len(days) + pad) / 7)
    for i in range(len(days)):
        col, row = divmod(i + pad, 7)
        d = days[i]
        cx = x + col * (cell + gap)
        cy = y + row * (cell + gap)
        lv = max(0, min(4, d.level))
        s.rect(cx, cy, cell, cell, fill=levels[lv], rx=2)
        if d.count > 0:
            s.raw(f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cell}" height="{cell}" rx="2" fill="none" '
                  f'stroke="{levels[min(4, lv + 1)]}" stroke-width="0.7" stroke-opacity="0.55"/>')
    return cols * (cell + gap) - gap, 7 * (cell + gap) - gap


def _ring(s: Svg, cx: float, cy: float, r: float, pct: float, color: str, width: float) -> None:
    circ = 2 * math.pi * r
    s.circle(cx, cy, r, fill="none", stroke=s.theme["grid_empty"], sw=width)
    dash = max(0.0, min(1.0, pct)) * circ
    s.raw(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{color}" '
          f'stroke-width="{width}" stroke-linecap="round" stroke-dasharray="{dash:.2f} {circ:.2f}" '
          f'transform="rotate(-90 {cx:.1f} {cy:.1f})"/>')


def status_panel(cfg: dict[str, Any], snap: Snapshot, dark: bool = True) -> Svg:
    t = dict(cfg["theme"])
    if not dark:
        t.update({"bg": "#f5f7fc", "panel": "#ffffff", "panel_border": "#dbe1f0",
                  "text": "#232c44", "muted": "#697392", "grid_empty": "#e7ecf7",
                  "levels": ["#eef1f8", "#c3cdf0", "#93a2e0", "#6c7fd0", "#4a5fc0"]})
    W, H = 820, 400
    s = Svg(W, H, t, title=f"@{cfg['username']}", name="status")
    s.defs(
        linear_gradient("bg", [(0, t["panel"], 1), (0.6, t["panel"], 1), (1, t["bg"], 1)], 0, 0, 1, 1),
        radial_gradient("halo", [(0, t["accent"], 0.10), (1, t["accent"], 0.0)]),
        clip_rect("frame", 0, 0, W, H, 16),
        blur_filter("soft", 8),
    )
    s.rect(0, 0, W, H, fill="url(#bg)", rx=16)
    s.raw(f'<ellipse cx="{W * 0.78:.0f}" cy="60" rx="330" ry="150" fill="url(#halo)"/>')
    s.rect(0.5, 0.5, W - 1, H - 1, fill="none", rx=16, stroke=t["panel_border"], sw=1)

    # window chrome
    s.circle(26, 26, 4.5, fill="#ff5f56")
    s.circle(43, 26, 4.5, fill="#ffbd2e")
    s.circle(60, 26, 4.5, fill="#27c93f")
    s.line(84, 26, W - 26, 26, t["panel_border"], 1)
    s.text(W - 26, 30, f"@{snap.login}", size=11, fill=t["muted"], anchor="end", mono=True)

    # prompt + identity
    s.text(28, 66, "$", size=14, fill=t["accent2"], mono=True, weight=700)
    s.text(46, 66, "whoami", size=14, fill=t["muted"], mono=True)
    s.text(28, 98, snap.name or snap.login, size=27, fill=t["text"], weight=700)
    s.text(29, 120, cfg["headline"], size=12, fill=t["accent"], mono=True, spacing=1.4)

    # stat columns (right aligned, fixed 96px pitch)
    stats = [("repos", snap.public_repos), ("stars", snap.stars), ("followers", snap.followers)]
    for i, (label, value) in enumerate(stats):
        right = W - 28 - (len(stats) - 1 - i) * 96
        s.text(right, 92, label, size=10, fill=t["muted"], anchor="end", mono=True, spacing=1.2)
        s.text(right, 116, str(value), size=20, fill=t["accent"], anchor="end", mono=True, weight=700)

    s.line(28, 138, W - 28, 138, t["panel_border"], 1)

    # heatmap block
    s.section(28, 158, "contributions", rule=False)
    s.text(W - 28, 158, f"{snap.total_contributions} in the last year", size=10,
           fill=t["muted"], anchor="end", mono=True)
    hw, hh = _heatmap(s, snap.days, 28, 178)

    # month ticks: one label per month, skipped when it would collide with the last
    seen: set[int] = set()
    pad = (snap.days[0].date.weekday() + 1) % 7
    last_mx = -1e9
    for i, d in enumerate(snap.days):
        if d.date.day <= 7 and d.date.month not in seen:
            seen.add(d.date.month)
            col = (i + pad) // 7
            mx = 28 + col * 12.7
            if mx < 28 or mx > 28 + hw - 12:
                continue
            if mx - last_mx < 26:      # never let two labels touch
                continue
            s.text(mx, 172, d.date.strftime("%b"), size=9, fill=t["muted"], mono=True)
            last_mx = mx

    # legend under the grid, right aligned
    lx = 28 + hw - 5 * 12.7
    for k in range(5):
        s.rect(lx + k * 12.7, 174 + hh + 6, 9.4, 9.4, fill=t["levels"][k], rx=2)
    s.text(lx - 8, 174 + hh + 14, "less", size=9, fill=t["muted"], anchor="end", mono=True)
    s.text(lx + 5 * 12.7 + 3, 174 + hh + 14, "more", size=9, fill=t["muted"], mono=True)

    s.line(28, 300, W - 28, 300, t["panel_border"], 1)

    # bottom metric columns
    active30 = sum(1 for d in snap.days[-30:] if d.count > 0)
    top_lang = snap.languages[0][0] if snap.languages else "-"
    metrics = [
        ("current streak", f"{snap.current_streak}d", "consecutive days"),
        ("best streak", f"{snap.best_streak}d", "personal record"),
        ("active days", f"{active30}/30", "last 30 days"),
    ]
    for i, (label, value, sub) in enumerate(metrics):
        x = 28 + i * 150
        s.text(x, 326, label.upper(), size=9, fill=t["muted"], mono=True, spacing=1.5)
        s.text(x, 356, value, size=24, fill=t["text"], mono=True, weight=700)
        s.text(x, 374, sub, size=9, fill=t["muted"], mono=True)

    # ring on the right: a percentage readout, no text crammed inside the arc
    rx, ry = 726, 330
    _ring(s, rx, ry, 34, active30 / 30.0, t["accent"], 6)
    _ring(s, rx, ry, 24, min(1.0, snap.total_contributions / 400.0), t["accent2"], 4)
    s.text(rx, ry + 2, f"{round(active30 / 30 * 100)}%", size=13, fill=t["text"],
           anchor="middle", mono=True, weight=700)
    s.text(rx, ry + 14, "30d", size=8, fill=t["muted"], anchor="middle", mono=True)
    s.text(rx, ry + 52, top_lang, size=9, fill=t["muted"], anchor="middle", mono=True)

    s.text(28, 392, cfg["links"]["github"].replace("https://", ""), size=9, fill=t["muted"], mono=True)
    s.text(W - 28, 392, f"synced {snap.fetched_at[:10]}", size=9, fill=t["muted"], anchor="end", mono=True)
    return s


def status_problems(cfg, snap, svg: Svg | None = None) -> list[str]:
    return []


# ---------------------------------------------------------------------------
# top languages
# ---------------------------------------------------------------------------


def languages_panel(cfg: dict[str, Any], snap: Snapshot, top: int = 8) -> Svg:
    t = cfg["theme"]
    palette = ["#9daaf8", "#6ee7f9", "#8b9bf0", "#a7f3d0", "#f0abfc", "#fca5a5", "#fcd34d", "#93c5fd"]
    rows = min(top, len(snap.languages))
    W = 420
    H = 56 + rows * 24 + 14
    s = Svg(W, H, t, title="top languages", name="stats/top-langs")
    s.defs(linear_gradient("lgbg", [(0, t["panel"], 1), (1, t["bg"], 1)], 0, 0, 1, 1))
    s.rect(0, 0, W, H, fill="url(#lgbg)", rx=14)
    s.rect(0.5, 0.5, W - 1, H - 1, fill="none", rx=14, stroke=t["panel_border"])
    s.section(20, 30, "languages", size=11, rule=False)

    total = sum(v for _, v in snap.languages[:rows]) or 1
    y = 52
    for i, (name, val) in enumerate(snap.languages[:rows]):
        share = val / total
        s.text(20, y + 8, name, size=12, fill=t["text"], mono=True)
        s.text(W - 20, y + 8, f"{share * 100:.1f}%", size=11, fill=t["muted"], anchor="end", mono=True)
        s.rect(20, y + 14, W - 40, 5, fill=t["grid_empty"], rx=2.5)
        s.rect(20, y + 14, max(3.0, (W - 40) * share), 5, fill=palette[i % len(palette)], rx=2.5)
        y += 24
    return s


# ---------------------------------------------------------------------------
# skills wall
# ---------------------------------------------------------------------------


def skills_wall(cfg: dict[str, Any], icons: dict[str, dict]) -> Svg:
    t = cfg["theme"]
    skills: dict[str, list[str]] = cfg["skills"]
    icon = 34
    step = 62
    row_h = 92
    groups = [(g, [x for x in items if x in icons]) for g, items in skills.items()]
    groups = [(g, items) for g, items in groups if items]
    W = 820
    H = 30 + len(groups) * row_h + 10
    s = Svg(W, H, t, title="skills", name="skills")
    y = 26
    for gname, items in groups:
        s.section(24, y, gname, size=11, rule=False)
        iy = y + 14
        for k, slug in enumerate(items):
            x = 24 + k * step
            meta = icons[slug]
            p = meta["path"]
            # devicon sources use a 128 viewBox; simple-icons use 24
            scale = icon / float(meta.get("viewBox", 24))
            for fill, op in ((t["accent"], 0.18), (t["text"], 0.9)):
                s.raw(f'<g transform="translate({x:.1f} {iy:.1f})" opacity="{op}">'
                      f'<path d="{p}" fill="{fill}" transform="scale({scale:.5f})"/></g>')
            s.text(x + icon / 2, iy + icon + 12, icons[slug]["label"], size=9,
                   fill=t["muted"], anchor="middle", mono=True)
        y += row_h
    return s


# ---------------------------------------------------------------------------
# extended stats card (github-readme-stats compatible look, rendered locally)
# ---------------------------------------------------------------------------


def stats_card(cfg: dict[str, Any], snap: Snapshot) -> Svg:
    t = cfg["theme"]
    W, H = 400, 200
    s = Svg(W, H, t, title="github stats", name="stats/github")
    s.defs(linear_gradient("sbg", [(0, t["panel"], 1), (1, t["bg"], 1)], 0, 0, 1, 1))
    s.rect(0, 0, W, H, fill="url(#sbg)", rx=12)
    s.rect(0.5, 0.5, W - 1, H - 1, fill="none", rx=12, stroke=t["panel_border"])
    s.section(20, 30, f"{snap.login}'s stats", size=11, rule=False)
    rows = [("Total Stars", snap.stars), ("Total Commits", snap.total_contributions),
            ("Public Repos", snap.public_repos), ("Followers", snap.followers)]
    y = 54
    for label, value in rows:
        s.text(20, y, label, size=11, fill=t["muted"], mono=True)
        s.text(W - 20, y, str(value), size=11, fill=t["accent"], anchor="end", mono=True, weight=700)
        s.line(20, y + 7, W - 20, y + 7, t["panel_border"], 0.8, opacity=0.6)
        y += 32
    return s


# ---------------------------------------------------------------------------
# contact icons + footer
# ---------------------------------------------------------------------------


CONTACT_META = {
    "github": ("GitHub", "#9daaf8"),
    "email": ("Email", "#f0abfc"),
    "x": ("X", "#e8e8e8"),
    "bilibili": ("Bilibili", "#6ee7f9"),
    "blog": ("Blog", "#a7f3d0"),
    "linkedin": ("LinkedIn", "#93c5fd"),
    "zhihu": ("Zhihu", "#9daaf8"),
}


def contact_icon(cfg: dict[str, Any], key: str, icons: dict[str, dict]) -> Svg:
    t = cfg["theme"]
    label, color = CONTACT_META.get(key, (key, t["accent"]))
    slug = {"email": "gmail", "blog": "rss", "bilibili": "bilibili", "github": "github",
            "x": "x", "linkedin": "github", "zhihu": "zhihu"}.get(key, key)
    p = icons.get(slug, icons.get("github"))["path"]
    W, H = 46, 46
    s = Svg(W, H, t, title=label, name=f"icons/contact-{key}")
    s.defs(linear_gradient(f"cg{key}", [(0, color, 0.95), (1, color, 0.55)], 0, 0, 1, 1))
    s.rect(1, 1, W - 2, H - 2, fill=t["panel"], rx=12, stroke=t["panel_border"], sw=1)
    s.icon(11, 11, p, 24, f"url(#cg{key})", opacity=0.95)
    return s


def footer(cfg: dict[str, Any]) -> Svg:
    t = cfg["theme"]
    W, H = 820, 60
    s = Svg(W, H, t, title="footer", name="banner/footer")
    s.defs(linear_gradient("ffade", [(0, t["accent"], 0.0), (0.5, t["accent"], 0.7), (1, t["accent"], 0.0)]))
    s.line(20, 18, W - 20, 18, "url(#ffade)", 1.2)
    s.text(W / 2, 38, "decoration | ...", size=12, fill=t["muted"], anchor="middle", mono=True, spacing=3)
    s.text(W / 2, 52, "generated locally · no third-party image hosts", size=8,
           fill=t["accent"], anchor="middle", mono=True, spacing=1.5, opacity=0.6)
    return s


def banner_ascii(cfg: dict[str, Any]) -> list[str]:
    return ascii_banner(cfg["ascii_name"], hscale=2)

# ---------------------------------------------------------------------------
# pinned repository card (replaces the github-readme-stats pin images)
# ---------------------------------------------------------------------------


LANG_COLORS = {
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "C#": "#239120", "Python": "#3572A5",
    "HTML": "#e34c26", "CSS": "#563d7c", "SCSS": "#c6538c", "Shell": "#89e051",
    "PowerShell": "#012456", "C": "#555555", "C++": "#f34b7d", "Rust": "#dea584",
    "Go": "#00ADD8", "Java": "#b07219", "Lua": "#000080", "Vue": "#41b883",
}


def repo_card(cfg: dict[str, Any], repo: str, desc: str, meta: dict | None = None) -> Svg:
    """A 380x118 card: name, wrapped description, language dot, stars and forks."""
    t = cfg["theme"]
    meta = meta or {}
    lang = meta.get("language", "")
    stars = meta.get("stars", 0)
    forks = meta.get("forks", 0)
    W, H = 380, 118
    s = Svg(W, H, t, title=repo, name=f"cards/{repo}")
    s.defs(linear_gradient("cbg", [(0, t["panel"], 1), (1, t["bg"], 1)], 0, 0, 1, 1))
    s.rect(0, 0, W, H, fill="url(#cbg)", rx=12)
    s.rect(0.5, 0.5, W - 1, H - 1, fill="none", rx=12, stroke=t["panel_border"])

    # repo glyph
    s.icon(20, 20, "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z",
           14, t["accent"], opacity=0.85)

    s.text(42, 31, repo, size=13, fill=t["accent"], weight=700, mono=True)

    lines = wrap(desc, W - 44, 11.5)[:2]
    y = 50
    for ln in lines:
        s.text(20, y, ln, size=11.5, fill=t["text"], opacity=0.82)
        y += 15

    # footer meta
    fy = H - 14
    x = 20
    if lang:
        s.circle(x + 4, fy - 4, 4, fill=LANG_COLORS.get(lang, t["muted"]))
        s.text(x + 13, fy, lang, size=10, fill=t["muted"], mono=True)
        x += 13 + text_width(lang, 10, mono=True) + 16
    star = "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"
    s.icon(x, fy - 8, star, 9, t["muted"], opacity=0.9)
    s.text(x + 13, fy, str(stars), size=10, fill=t["muted"], mono=True)
    x += 13 + text_width(str(stars), 10, mono=True) + 16
    fork = "M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0Z"
    s.icon(x, fy - 8, fork, 9, t["muted"], opacity=0.9)
    s.text(x + 13, fy, str(forks), size=10, fill=t["muted"], mono=True)
    return s

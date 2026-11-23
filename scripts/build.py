"""Generate every asset the profile README references.

    python scripts/build.py            # fetch live data and regenerate
    python scripts/build.py --offline  # reuse scripts/icons/snapshot.json

Panels return live Svg objects, so each document is audited from the exact geometry
that produced it: text may not spill outside the canvas and no two text runs may
overlap. A failed audit aborts the build instead of shipping a broken image.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import hero as hero_mod
import panels
from github_data import Snapshot, load_or_fetch
from svglib import Svg, linear_gradient

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
ASSETS = ROOT / "assets"

# the skills wall places icons outside the text grid on purpose
SKIP_AUDIT = {"skills"}


class Audit:
    def __init__(self) -> None:
        self.problems: list[str] = []
        self.count = 0

    def render(self, s: Svg) -> str:
        self.count += 1
        if s.name not in SKIP_AUDIT:
            self.problems.extend(s.audit())
        return s.render()


def write(path: Path, content: str, quiet: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    if not quiet:
        print(f"  + {path.relative_to(ROOT)}  ({len(content) / 1024:.1f} KB)")


def slugify(label: str) -> str:
    return label.replace(" ", "_").replace("/", "%2F").replace("#", "%23")


def contact_chips(cfg: dict[str, Any], icons: dict[str, dict], audit: Audit) -> str:
    meta = panels.CONTACT_META
    chips = []
    for key, url in cfg["links"].items():
        if not url or key not in meta:
            continue
        label, color = meta[key]
        if key == "email" and not url.startswith("mailto:"):
            url = f"mailto:{url}"
        slug = {"email": "gmail", "blog": "rss"}.get(key, key)
        path_d = icons.get(slug, icons["github"])["path"]
        s = Svg(46, 46, cfg["theme"], title=label, name=f"icons/contact-{key}")
        s.defs(linear_gradient(f"cg{key}", [(0, color, 0.95), (1, color, 0.5)], 0, 0, 1, 1))
        s.rect(1, 1, 44, 44, fill=cfg["theme"]["panel"], rx=12, stroke=cfg["theme"]["panel_border"])
        s.icon(11, 11, path_d, 24, f"url(#cg{key})", opacity=0.95)
        write(ASSETS / "icons" / f"contact-{key}.svg", audit.render(s), quiet=True)
        chips.append(f'<a href="{url}" title="{label}"><img align="center" '
                     f'src="assets/icons/contact-{key}.svg" width="44" height="44" alt="{label}" /></a>')
    return "\n  ".join(chips)


def repo_meta(snap: Snapshot, name: str) -> dict:
    for r in snap.repos:
        if r.name == name:
            return {"language": r.language, "stars": r.stars, "forks": r.forks}
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="reuse the cached snapshot")
    args = ap.parse_args()

    cfg = json.loads((SCRIPTS / "config.json").read_text(encoding="utf-8"))
    icons = json.loads((SCRIPTS / "icons" / "paths.json").read_text(encoding="utf-8"))
    cache = SCRIPTS / "icons" / "snapshot.json"
    audit = Audit()

    print("== fetching github data ==")
    snap = load_or_fetch(cfg, str(cache), offline=args.offline)
    print(f"   {snap.login}: {snap.total_contributions} contributions, "
          f"{len(snap.repos)} repos, {len(snap.languages)} languages")

    print("== rendering svg ==")
    docs: dict[str, Svg] = {
        "hero.svg": hero_mod.hero(cfg),
        # GitHub's <picture> swaps these two by prefers-color-scheme, so the light
        # file must actually be light - otherwise the switch is a no-op.
        "status.svg": panels.status_panel(cfg, snap, dark=False),
        "status-dark.svg": panels.status_panel(cfg, snap, dark=True),
        "skills.svg": panels.skills_wall(cfg, icons),
        "stats/top-langs.svg": panels.languages_panel(cfg, snap),
        "stats/github.svg": panels.stats_card(cfg, snap),
        "typing/hello.svg": panels.typing(cfg),
        "banner/status.svg": panels.section_banner(cfg, "STATUS"),
        "banner/intro.svg": panels.section_banner(cfg, "ABOUT"),
        "banner/skills.svg": panels.section_banner(cfg, "SKILLS"),
        "banner/contact.svg": panels.section_banner(cfg, "CONTACT"),
        "banner/footer.svg": panels.footer(cfg),
    }
    for i in range(len(cfg["typing_lines"])):
        docs[f"typing/hello-{i}.svg"] = panels.typing(cfg, i)
    for p in cfg["pinned"]:
        docs[f"cards/{p['repo']}.svg"] = panels.repo_card(
            cfg, p["repo"], p["desc"], repo_meta(snap, p["repo"]))

    for rel, s in docs.items():
        write(ASSETS / rel, audit.render(s), quiet=rel.startswith("typing/hello-"))

    contact = contact_chips(cfg, icons, audit)

    print("== rendering readme ==")
    tpl = (ROOT / "README.template.md").read_text(encoding="utf-8")
    cards = [
        f'<a href="https://github.com/{cfg["username"]}/{p["repo"]}">'
        f'<img src="assets/cards/{p["repo"]}.svg" width="380" alt="{p["repo"]}" /></a>'
        for p in cfg["pinned"]]
    # two cards per row; every row is closed so the layout never reflows
    rows = [cards[i:i + 2] for i in range(0, len(cards), 2)]
    pinned = "<br/>\n".join("\n".join(r) for r in rows)
    badges = "".join(
        f'<img src="https://img.shields.io/badge/{slugify(b["label"])}-111726'
        f'?style=flat-square&logo={b["icon"]}&logoColor=9daaf8&labelColor=0a0d16" alt="{b["label"]}" />'
        for b in cfg["badges"])
    readme = (tpl
              .replace("{{PINNED}}", pinned)
              .replace("{{BADGES}}", badges)
              .replace("{{CONTACT}}", contact)
              .replace("{{BIO}}", "<br/>\n    ".join(cfg["bio_lines"]))
              .replace("{{HEADLINE}}", cfg["headline"])
              .replace("{{NAME}}", cfg["display_name"])
              .replace("{{USERNAME}}", cfg["username"])
              .replace("{{TYPING0}}", cfg["typing_lines"][0]))
    write(ROOT / "README.md", readme)

    write(ROOT / "demos" / "status-panel.md",
          "# Status panel\n\n"
          "Generated by `scripts/build.py` so the panel can be previewed with GitHub's own\n"
          "Markdown renderer before it goes on the profile page.\n\n"
          '<picture>\n'
          '  <source media="(prefers-color-scheme: dark)" srcset="../assets/status-dark.svg">\n'
          '  <img align="center" src="../assets/status.svg" width="820"\n'
          '    alt="Contribution heatmap, activity ring, streaks and top languages">\n'
          '</picture>\n')

    print(f"== audit: {audit.count} documents ==")
    if audit.problems:
        for p in audit.problems:
            print("  x " + p)
        print("  BUILD FAILED")
        return 1
    print("   all clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

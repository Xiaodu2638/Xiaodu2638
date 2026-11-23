"""Fetch the small amount of GitHub data the panels need.

Only public, unauthenticated-friendly endpoints are used. When a request fails the
build keeps going with whatever it already has, so a flaky network never breaks the
README - it just freezes the numbers.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import time

import requests

API = "https://api.github.com"
UA = "readme-renderer/1.0 (+https://github.com)"


@dataclass
class Day:
    date: dt.date
    level: int
    count: int


@dataclass
class Repo:
    name: str
    description: str
    language: str
    stars: int
    forks: int
    url: str
    updated: str


@dataclass
class Snapshot:
    login: str
    name: str
    bio: str
    followers: int
    following: int
    public_repos: int
    days: list[Day] = field(default_factory=list)
    total_contributions: int = 0
    repos: list[Repo] = field(default_factory=list)
    languages: list[tuple[str, int]] = field(default_factory=list)
    stars: int = 0
    forks: int = 0
    best_streak: int = 0
    current_streak: int = 0
    fetched_at: str = ""


def _get_json(s: requests.Session, url: str, tries: int = 4, timeout: int = 30):
    """GET with backoff. Language lists are small and cheap, but a dropped repo
    silently changes the published percentages, so failures are retried."""
    last = None
    for attempt in range(tries):
        try:
            r = s.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
            if r.status_code in (403, 429):
                reset = r.headers.get("x-ratelimit-reset")
                if reset:
                    wait = max(1, min(30, int(reset) - int(time.time()) + 1))
                    print(f"    rate limited, sleeping {wait}s")
                    time.sleep(wait)
                    continue
            if r.status_code >= 500:
                time.sleep(1 + attempt)
                continue
            return None
        except Exception as exc:  # noqa: BLE001
            last = str(exc)[:80]
            time.sleep(1 + attempt)
    print(f"    ! {url} failed: {last}")
    return None


def _session(token: str | None = None) -> requests.Session:
    s = requests.Session()
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    s.headers.update(h)
    return s


def fetch_contributions(s: requests.Session, login: str) -> tuple[list[Day], int]:
    """Scrape the public contribution calendar (no token required)."""
    r = s.get(f"https://github.com/users/{login}/contributions",
              headers={"Accept": "text/html"}, timeout=30)
    r.raise_for_status()
    html = r.text

    # counts live in <tool-tip for="contribution-day-component-r-c">...</tool-tip>
    tipcount: dict[str, int] = {}
    for cell_id, label in re.findall(
            r'<tool-tip[^>]*for="(contribution-day-component-\d+-\d+)"[^>]*>(.*?)</tool-tip>',
            html, flags=re.S):
        label = re.sub(r"<[^>]+>", "", label).strip()
        m = re.match(r"(\d+) contributions? on", label)
        tipcount[cell_id] = int(m.group(1)) if m else 0

    days: list[Day] = []
    for tag in re.findall(r"<td[^>]*ContributionCalendar-day[^>]*>", html):
        d = re.search(r'data-date="([\d-]+)"', tag)
        if not d:
            continue
        m_level = re.search(r'data-level="(\d+)"', tag)
        m_id = re.search(r'id="(contribution-day-component-[\d-]+)"', tag)
        cell_id = m_id.group(1) if m_id else ""
        days.append(Day(
            date=dt.date.fromisoformat(d.group(1)),
            level=int(m_level.group(1)) if m_level else 0,
            count=tipcount.get(cell_id, 0),
        ))
    days.sort(key=lambda x: x.date)

    total_m = re.search(r"([\d,]+)\s+contributions?\s+in the last year", html)
    total = int(total_m.group(1).replace(",", "")) if total_m else sum(d.count for d in days)
    return days, total


def streaks(days: list[Day]) -> tuple[int, int]:
    best = cur = 0
    run = 0
    prev = None
    for d in days:
        if d.count > 0:
            if prev and (d.date - prev).days == 1:
                run += 1
            else:
                run = 1
            best = max(best, run)
            prev = d.date
        else:
            run = 0
            prev = d.date if prev is None else prev
    # current streak: walk back from the last active day (allow today to be quiet)
    tail = list(reversed(days))
    today = tail[0].date if tail else dt.date.today()
    idx = 0
    while idx < len(tail) and tail[idx].count == 0 and (today - tail[idx].date).days <= 1:
        idx += 1
    cur = 0
    while idx < len(tail) and tail[idx].count > 0:
        cur += 1
        if idx + 1 < len(tail) and (tail[idx].date - tail[idx + 1].date).days == 1:
            idx += 1
        else:
            break
    return best, cur


def fetch_snapshot(cfg: dict[str, Any], token: str | None = None) -> Snapshot:
    s = _session(token)
    login = cfg["username"]
    snap = Snapshot(login=login, name=cfg.get("display_name", login), bio="",
                    followers=0, following=0, public_repos=0)
    u = _get_json(s, f"{API}/users/{login}")
    if isinstance(u, dict):
        snap.name = u.get("name") or snap.name
        snap.bio = u.get("bio") or ""
        snap.followers = u.get("followers", 0)
        snap.following = u.get("following", 0)
        snap.public_repos = u.get("public_repos", 0)
    else:
        print("  ! user info failed")

    try:
        snap.days, snap.total_contributions = fetch_contributions(s, login)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! contributions failed: {exc}")

    repos = _get_json(s, f"{API}/users/{login}/repos?per_page=100&sort=updated")
    if not isinstance(repos, list):
        print("  ! repos failed")
        repos = []

    agg: dict[str, int] = {}
    for rp in repos:
        if rp.get("fork"):
            continue
        snap.repos.append(Repo(
            name=rp["name"],
            description=(rp.get("description") or "").strip(),
            language=rp.get("language") or "",
            stars=rp.get("stargazers_count", 0),
            forks=rp.get("forks_count", 0),
            url=rp.get("html_url", ""),
            updated=rp.get("pushed_at", "")[:10],
        ))
        snap.stars += rp.get("stargazers_count", 0)
        snap.forks += rp.get("forks_count", 0)
        langs = _get_json(s, rp["languages_url"], timeout=20)
        if not isinstance(langs, dict):
            # a dropped repo silently skews every percentage on the panel
            raise RuntimeError(f"language breakdown unavailable for {rp['name']}")
        for k, v in langs.items():
            agg[k] = agg.get(k, 0) + int(v)
    snap.languages = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
    snap.best_streak, snap.current_streak = streaks(snap.days)
    snap.fetched_at = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    return snap


def load_or_fetch(cfg, cache_path: str, offline: bool = False) -> Snapshot:
    token = os.environ.get("GITHUB_TOKEN") or None
    if offline and os.path.exists(cache_path):
        return _from_json(json.load(open(cache_path, encoding="utf-8")))
    try:
        snap = fetch_snapshot(cfg, token)
        # a partial fetch would publish wrong numbers, so require the whole picture
        if not snap.days:
            raise RuntimeError("empty contribution calendar")
        if not snap.languages:
            raise RuntimeError("no language breakdown (repos or languages_unavailable)")
        if not snap.repos:
            raise RuntimeError("no repositories returned")
    except Exception as exc:  # noqa: BLE001
        print(f"  ! live fetch failed ({exc}); falling back to cache")
        if os.path.exists(cache_path):
            return _from_json(json.load(open(cache_path, encoding="utf-8")))
        raise
    # only a complete snapshot is allowed to replace the cache
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    tmp = cache_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(_to_json(snap), fh, ensure_ascii=False, indent=1)
    os.replace(tmp, cache_path)
    return snap


def _to_json(snap: Snapshot) -> dict:
    return {
        "login": snap.login, "name": snap.name, "bio": snap.bio,
        "followers": snap.followers, "following": snap.following,
        "public_repos": snap.public_repos, "total_contributions": snap.total_contributions,
        "days": [[d.date.isoformat(), d.level, d.count] for d in snap.days],
        "repos": [r.__dict__ for r in snap.repos],
        "languages": snap.languages, "stars": snap.stars, "forks": snap.forks,
        "best_streak": snap.best_streak, "current_streak": snap.current_streak,
        "fetched_at": snap.fetched_at,
    }


def _from_json(d: dict) -> Snapshot:
    return Snapshot(
        login=d["login"], name=d["name"], bio=d.get("bio", ""),
        followers=d.get("followers", 0), following=d.get("following", 0),
        public_repos=d.get("public_repos", 0),
        days=[Day(dt.date.fromisoformat(x[0]), x[1], x[2]) for x in d["days"]],
        total_contributions=d.get("total_contributions", 0),
        repos=[Repo(**r) for r in d.get("repos", [])],
        languages=[tuple(x) for x in d.get("languages", [])],
        stars=d.get("stars", 0), forks=d.get("forks", 0),
        best_streak=d.get("best_streak", 0), current_streak=d.get("current_streak", 0),
        fetched_at=d.get("fetched_at", ""),
    )

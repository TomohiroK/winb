"""Deeper inspection: print representative markup chunks for each page.

Helps design parsers by seeing actual HTML structures.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

CACHE_DIR = Path("/app/data/cache")


def load(url_substring: str) -> tuple[str, str]:
    for meta_path in CACHE_DIR.glob("*.meta.json"):
        meta = json.loads(meta_path.read_text())
        if url_substring in meta["url"]:
            html_path = meta_path.with_suffix("").with_suffix(".html")
            return meta["url"], html_path.read_text(encoding="utf-8")
    raise ValueError(url_substring)


def truncate(s: str, n: int = 2500) -> str:
    if len(s) <= n:
        return s
    return s[:n] + f"\n...[truncated {len(s) - n} bytes]..."


def shrink(tag: Tag) -> str:
    """Return a compact prettified HTML for a tag."""
    html = str(tag)
    # Collapse consecutive whitespace
    html = re.sub(r"\s+", " ", html)
    html = re.sub(r">\s+<", "><", html)
    return html


def section(label: str):
    print(f"\n{'=' * 70}\n  {label}\n{'=' * 70}")


# ---- SCHEDULE ----
section("SCHEDULE: first 2 <li class='list-item'> blocks")
_, html = load("schedule/?tab=1&year=2026&mon=04")
soup = BeautifulSoup(html, "lxml")
items = soup.select("li.list-item")
print(f"Found {len(items)} list-item elements")
for i, li in enumerate(items[:2]):
    print(f"\n--- item [{i}] ---")
    print(truncate(shrink(li), 3000))


# ---- CLUB_DETAIL: ロスター tableを特定 ----
section("CLUB_DETAIL: the 'table-player' table (roster)")
_, html = load("club_detail/?TeamID=692")
soup = BeautifulSoup(html, "lxml")
roster_tables = soup.select("table.table-player")
print(f"Found {len(roster_tables)} roster tables")
for i, t in enumerate(roster_tables[:1]):
    rows = t.find_all("tr")
    print(f"\n--- roster table [{i}]: {len(rows)} rows ---")
    # print header + first 3 rows compact
    for r_idx, r in enumerate(rows[:4]):
        print(f"\n[row {r_idx}]")
        print(truncate(shrink(r), 2000))


section("CLUB_DETAIL: headline area (team name, record)")
# heuristic: find heading or title area
for sel in ["h1", ".clubDetail-kv", ".clubDetail-info",
            ".clubDetail-header", ".breadcrumb-list"]:
    hits = soup.select(sel)
    if hits:
        print(f"\n-- selector '{sel}' ({len(hits)} hits) --")
        for h in hits[:2]:
            print(truncate(shrink(h), 1500))


section("CLUB_DETAIL: first score-tab-table (team stats?)")
stat_tables = soup.select("table.score-tab-table")
for i, t in enumerate(stat_tables[:1]):
    rows = t.find_all("tr")
    print(f"table [{i}]: {len(rows)} rows, classes='{' '.join(t.get('class', []))}'")
    for r_idx, r in enumerate(rows[:5]):
        print(f"\n[row {r_idx}]")
        print(truncate(shrink(r), 1500))


# ---- ROSTER_DETAIL: プロフィール ----
section("ROSTER_DETAIL: kv-playerProfile-list")
_, html = load("roster_detail/?PlayerID=51000531")
soup = BeautifulSoup(html, "lxml")
profile_items = soup.select("li.rosterDetail-kv-playerProfile-list-item")
print(f"Found {len(profile_items)} profile items")
for i, li in enumerate(profile_items[:8]):
    print(f"\n[{i}] {shrink(li)[:500]}")


section("ROSTER_DETAIL: kv area (name, number, position)")
for sel in [".rosterDetail-kv", ".rosterDetail-kv-playerProfile",
            ".rosterDetail-kv-title", "h1"]:
    hits = soup.select(sel)
    if hits:
        print(f"\n-- selector '{sel}' ({len(hits)} hits) --")
        print(truncate(shrink(hits[0]), 2000))


section("ROSTER_DETAIL: season stats tables (grades-item)")
grades = soup.select(".grades-item")
print(f"Found {len(grades)} grades-item")
for i, g in enumerate(grades[:5]):
    print(f"\n[{i}] {shrink(g)[:600]}")


# ---- GAME_INFO ----
section("GAME_INFO: scoreboard__match (first)")
_, html = load("game_detail/?ScheduleKey=505443")
soup = BeautifulSoup(html, "lxml")
matches = soup.select(".scoreboard__match")
print(f"Found {len(matches)} scoreboard__match")
for i, m in enumerate(matches[:1]):
    print(f"\n[{i}]")
    print(truncate(shrink(m), 3000))


section("GAME_INFO: breadcrumb / title")
for sel in ["h1", ".breadcrumb-list", ".breadcrumb", ".page-title"]:
    hits = soup.select(sel)
    if hits:
        print(f"\n-- '{sel}' ({len(hits)}) --")
        print(truncate(shrink(hits[0]), 1500))

"""Inspect cached HTML structures to design parsers.

Reads cached HTML (already fetched via BleagueClient) and summarises:
- page title
- top-level CSS classes
- number of tables
- repeated list elements
- key heuristic signals

Usage (from host):
    docker compose exec app python scripts/inspect_html.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup


CACHE_DIR = Path("/app/data/cache")


def load_cache_by_url(url_substring: str) -> tuple[str, str]:
    """Find a cached file whose meta 'url' contains the substring.

    Returns (url, html) or raises ValueError if not found.
    """
    for meta_path in CACHE_DIR.glob("*.meta.json"):
        meta = json.loads(meta_path.read_text())
        if url_substring in meta["url"]:
            html_path = meta_path.with_suffix("").with_suffix(".html")
            return meta["url"], html_path.read_text(encoding="utf-8")
    raise ValueError(f"No cached page with URL containing {url_substring!r}")


def summarise(label: str, url: str, html: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {label}: {url}")
    print(f"  size: {len(html):,} bytes")
    print(f"{'=' * 70}")

    soup = BeautifulSoup(html, "lxml")

    # Title
    title = soup.title.get_text(strip=True) if soup.title else "(no title)"
    print(f"<title>: {title}")

    # Top CSS classes (first 20 by frequency)
    class_counter = Counter()
    for tag in soup.find_all(class_=True):
        for c in tag.get("class", []):
            class_counter[c] += 1
    print("\nTop 20 CSS classes:")
    for cls, cnt in class_counter.most_common(20):
        print(f"  {cnt:>4}  .{cls}")

    # Tables
    tables = soup.find_all("table")
    print(f"\n<table> count: {len(tables)}")
    for i, t in enumerate(tables[:10]):
        cls = " ".join(t.get("class", []))
        rows = len(t.find_all("tr"))
        print(f"  [{i}] class='{cls}' rows={rows}")

    # List items pattern (look for repeated <li> with similar classes)
    li_class_counter = Counter()
    for li in soup.find_all("li", class_=True):
        key = " ".join(sorted(li.get("class", [])))
        li_class_counter[key] += 1
    print("\nTop <li> class groups (may indicate repeated items):")
    for key, cnt in li_class_counter.most_common(10):
        if cnt >= 3:  # only interesting if repeated
            print(f"  {cnt:>4}  <li class='{key}'>")

    # Data attributes indicating IDs
    print("\nData-* attributes of interest:")
    for attr in ["data-team", "data-club", "data-teamid", "data-schedulekey",
                 "data-player", "data-playerid", "data-game"]:
        hits = soup.find_all(attrs={attr: True})
        if hits:
            sample_values = {h.get(attr) for h in hits[:5]}
            print(f"  {attr}: {len(hits)} occurrences, samples={sample_values}")

    # Look for specific id/href patterns
    print("\nLinks by pattern (sample 5):")
    for pattern in ["game_detail", "club_detail", "roster_detail"]:
        links = [a.get("href") for a in soup.find_all("a", href=True)
                 if pattern in a.get("href", "")]
        if links:
            print(f"  {pattern}: {len(links)} links")
            for link in links[:5]:
                print(f"    - {link}")


def main() -> int:
    pages = [
        ("SCHEDULE", "schedule/?tab=1&year=2026&mon=04"),
        ("CLUB_DETAIL", "club_detail/?TeamID=692"),
        ("ROSTER_DETAIL", "roster_detail/?PlayerID=51000531"),
        ("GAME_INFO", "game_detail/?ScheduleKey=505443"),
    ]
    for label, sub in pages:
        try:
            url, html = load_cache_by_url(sub)
        except ValueError as e:
            print(f"[{label}] {e}", file=sys.stderr)
            continue
        summarise(label, url, html)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

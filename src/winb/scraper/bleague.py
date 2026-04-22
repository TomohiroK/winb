"""HTML parsers for B.LEAGUE official site.

Each public function takes raw HTML (string) and returns structured
dataclasses. Parsers are pure — they don't hit the network.

Page types covered:
- /schedule/              → parse_schedule  → list[ScheduledGame]
- /club_detail/?TeamID=X  → parse_club_detail → ClubDetail
- /roster_detail/?PlayerID=X → parse_roster_detail → PlayerDetail
- /game_detail/?ScheduleKey=X&tab=1 → parse_game_info → GameInfo
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


# --- Dataclasses -----------------------------------------------------------


@dataclass
class ScheduledGame:
    """One row from the /schedule/ page.

    Date is NOT included because bleague.jp renders it in a sibling element;
    callers should attach the date separately.
    """

    schedule_key: str
    home_name: str
    away_name: str
    home_code: str | None  # 2-letter logo code, e.g. "lh" for 北海道
    away_code: str | None
    section: str | None  # e.g. "第28節"
    location: str | None  # e.g. "北海道 | よつ葉"
    tipoff: str | None  # e.g. "15:05"
    is_final: bool
    home_score: int | None
    away_score: int | None


@dataclass
class RosterEntry:
    """One row of the team roster table (season aggregate stats)."""

    player_id: int
    jersey_number: int | None
    name: str
    season: str  # e.g. "2025-26"
    game_type: str  # e.g. "B1"
    positions: list[str]  # ["PG", "SG"]
    games: int | None
    # Key stats (nullable because the table may contain "-" for rookies)
    ppg: float | None
    fg_pct: float | None
    three_fg_pct: float | None
    ft_pct: float | None
    rpg: float | None
    apg: float | None
    spg: float | None
    bpg: float | None
    topg: float | None
    eff: float | None


@dataclass
class TeamSeasonStat:
    """One row of team season stats table (one per season / competition)."""

    season: str
    game_type: str
    wins: int
    losses: int
    ppg: float | None
    opp_ppg: float | None
    fg_pct: float | None
    three_fg_pct: float | None
    ft_pct: float | None
    rpg: float | None
    apg: float | None
    topg: float | None
    spg: float | None
    bpg: float | None


@dataclass
class ClubDetail:
    """Parsed /club_detail/?TeamID=X."""

    team_id: int | None
    name_ja: str
    name_en: str | None
    wins: int | None
    losses: int | None
    rank_label: str | None  # e.g. "B1｜東地区 6位"
    arena: str | None
    address: str | None
    official_url: str | None
    roster: list[RosterEntry] = field(default_factory=list)
    season_stats: list[TeamSeasonStat] = field(default_factory=list)


@dataclass
class PlayerDetail:
    """Parsed /roster_detail/?PlayerID=X."""

    player_id: int | None
    name_ja: str
    name_en: str | None
    jersey_number: int | None
    positions: list[str]
    birth_date: date | None
    age: int | None
    height_cm: int | None
    weight_kg: int | None
    nationality: str | None
    hometown: str | None
    school: str | None
    team_id: int | None
    team_name: str | None


@dataclass
class GameInfo:
    """Parsed /game_detail/?ScheduleKey=X&tab=1 (pre-game info tab)."""

    schedule_key: str
    home_name: str
    away_name: str
    home_team_id: int | None
    away_team_id: int | None
    date: date | None
    tipoff: str | None
    competition: str | None  # e.g. "B1リーグ戦"
    season: str | None  # e.g. "2025-26"
    is_planned: bool  # True if game hasn't been played yet


# --- Helpers ---------------------------------------------------------------


_RE_DATE_JP = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_RE_DATE_SLASH = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
_RE_HEIGHT_WEIGHT = re.compile(r"(\d+)\s*cm\s*[／/]\s*(\d+)\s*kg")
_RE_AGE = re.compile(r"｜\s*(\d+)\s*歳")
_RE_TEAMID = re.compile(r"TeamID=(\d+)")
_RE_PLAYERID = re.compile(r"PlayerID=(\d+)")
_RE_SCHEDULEKEY = re.compile(r"ScheduleKey=(\d+)")
_RE_LOGO_CODE = re.compile(r"/logo/\d+/[smlxs]+/([a-z0-9]+)\.png", re.IGNORECASE)
_RE_WIN_LOSS_LABEL = re.compile(r"(\d+)\s*勝.*?(\d+)\s*敗", re.S)


def _text(tag: Tag | None) -> str:
    """Normalize whitespace in a tag's text content."""
    if tag is None:
        return ""
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True))


def _parse_int(s: str) -> int | None:
    s = s.strip().replace(",", "")
    if not s or s in ("-", "ー", "N/A"):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_float(s: str) -> float | None:
    s = s.strip().replace("%", "").replace(",", "")
    if not s or s in ("-", "ー", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _jp_date_to_date(text: str) -> date | None:
    m = _RE_DATE_JP.search(text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _RE_DATE_SLASH.search(text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _extract_code_from_logo(img_src: str) -> str | None:
    m = _RE_LOGO_CODE.search(img_src)
    return m.group(1).lower() if m else None


# --- parse_schedule --------------------------------------------------------


def parse_schedule(html: str) -> list[ScheduledGame]:
    """Parse the monthly schedule page into a list of games.

    Notes:
        - The game date is NOT included in each <li>; the caller is expected
          to correlate it with the date slider or URL params.
        - The schedule_key is stored in ``<li id="...">``.
    """
    soup = BeautifulSoup(html, "lxml")
    games: list[ScheduledGame] = []

    for li in soup.select("li.list-item"):
        schedule_key = li.get("id", "").strip()
        if not schedule_key or not schedule_key.isdigit():
            continue

        home = li.select_one(".team.home")
        away = li.select_one(".team.away")
        if home is None or away is None:
            logger.debug("Skipping li#%s: missing team spans", schedule_key)
            continue

        home_name = _text(home.select_one(".team-name"))
        away_name = _text(away.select_one(".team-name"))

        home_logo = home.select_one(".team-logo img")
        away_logo = away.select_one(".team-logo img")
        home_code = (
            _extract_code_from_logo(home_logo.get("src", "")) if home_logo else None
        )
        away_code = (
            _extract_code_from_logo(away_logo.get("src", "")) if away_logo else None
        )

        # Scores
        home_score_el = li.select_one(".point .home-score span")
        away_score_el = li.select_one(".point .away-score span")
        home_score = _parse_int(_text(home_score_el)) if home_score_el else None
        away_score = _parse_int(_text(away_score_el)) if away_score_el else None

        # Section / location / tipoff (three <span> inside .info-arena)
        section = location = tipoff = None
        info_spans = li.select(".info-arena span")
        if len(info_spans) >= 1:
            section = _text(info_spans[0]) or None
        if len(info_spans) >= 2:
            location = _text(info_spans[1]) or None
        if len(info_spans) >= 3:
            tipoff = _text(info_spans[2]) or None

        # State
        state = _text(li.select_one(".info-scorestate"))
        is_final = state == "FINAL"

        games.append(
            ScheduledGame(
                schedule_key=schedule_key,
                home_name=home_name,
                away_name=away_name,
                home_code=home_code,
                away_code=away_code,
                section=section,
                location=location,
                tipoff=tipoff,
                is_final=is_final,
                home_score=home_score,
                away_score=away_score,
            )
        )

    return games


# --- parse_club_detail -----------------------------------------------------


def _parse_team_stat_row(cells: list[Tag]) -> TeamSeasonStat | None:
    """Parse a data row of the first score-tab-table on the club page.

    Column order (observed 2026-04-22):
        [0]Season [1]Type [2]W [3]L [4]PPG [5]OPPPPG
        [6]FGMPG [7]FGAPG [8]FG% [9]2FGMPG [10]2FGAPG [11]2FG%
        [12]3FGMPG [13]3FGAPG [14]3FG% [15]FTMPG [16]FTAPG [17]FT%
        [18]ORPG [19]DRPG [20]RPG [21]APG [22]TOPG [23]STPG
        [24]BSPG [25]BSRPG [26]FPG [27]FDPG [28]MIN [29]EFF
    """
    if len(cells) < 24:
        return None
    t = [_text(c) for c in cells]
    wins = _parse_int(t[2])
    losses = _parse_int(t[3])
    if wins is None or losses is None:
        return None
    return TeamSeasonStat(
        season=t[0],
        game_type=t[1],
        wins=wins,
        losses=losses,
        ppg=_parse_float(t[4]),
        opp_ppg=_parse_float(t[5]),
        fg_pct=_parse_float(t[8]),
        three_fg_pct=_parse_float(t[14]),
        ft_pct=_parse_float(t[17]),
        rpg=_parse_float(t[20]),
        apg=_parse_float(t[21]),
        topg=_parse_float(t[22]),
        spg=_parse_float(t[23]),
        bpg=_parse_float(t[24]) if len(t) > 24 else None,
    )


def _parse_roster_row(cells: list[Tag]) -> RosterEntry | None:
    """Parse one roster row from table.table-player.

    Column order (observed):
        [0]# [1]player-link [2]Season [3]Type [4]Pos [5]G
        [6]MIN [7]MINPG [8]PPG
        [9]FGMPG [10]FGAPG [11]FG%
        [12]2FGMPG [13]2FGAPG [14]2FG%
        [15]3FGMPG [16]3FGAPG [17]3FG%
        [18]FTMPG [19]FTAPG [20]FT%
        [21]ORPG [22]DRPG [23]RPG
        [24]APG [25]TOPG [26]STPG
        [27]BSPG [28]BSRPG [29]FPG [30]FDPG [31]EFFPG [32]+/-
    """
    if len(cells) < 20:
        return None
    link = cells[1].find("a", href=True)
    player_id = None
    if link:
        m = _RE_PLAYERID.search(link["href"])
        player_id = int(m.group(1)) if m else None
    if player_id is None:
        return None

    name = _text(link)
    jersey = _parse_int(_text(cells[0]))
    positions = [p.strip() for p in _text(cells[4]).split("/") if p.strip()]
    t = [_text(c) for c in cells]
    return RosterEntry(
        player_id=player_id,
        jersey_number=jersey,
        name=name,
        season=t[2],
        game_type=t[3],
        positions=positions,
        games=_parse_int(t[5]),
        ppg=_parse_float(t[8]),
        fg_pct=_parse_float(t[11]),
        three_fg_pct=_parse_float(t[17]),
        ft_pct=_parse_float(t[20]),
        rpg=_parse_float(t[23]),
        apg=_parse_float(t[24]),
        topg=_parse_float(t[25]),
        spg=_parse_float(t[26]),
        bpg=_parse_float(t[27]),
        eff=_parse_float(t[31]) if len(t) > 31 else None,
    )


def parse_club_detail(html: str, team_id: int | None = None) -> ClubDetail:
    """Parse /club_detail/?TeamID=X."""
    soup = BeautifulSoup(html, "lxml")

    kv = soup.select_one(".clubDetail-kv")
    name_ja = ""
    name_en: str | None = None
    wins = losses = None
    rank_label: str | None = None
    if kv:
        # Name: the <h1> holds both EN + JA.
        name_h1 = kv.select_one(".clubDetail-kv-name")
        if name_h1:
            # EN is inside .clubDetail-kv-name-alphabet
            en_span = name_h1.select_one(".clubDetail-kv-name-alphabet")
            name_en = _text(en_span) or None
            # JA = full text minus EN
            full = _text(name_h1)
            name_ja = full.replace(name_en or "", "").strip()

        # Wins / losses numbers
        nums = kv.select(".clubDetail-kv-grades-num")
        if len(nums) >= 2:
            wins = _parse_int(_text(nums[0]))
            losses = _parse_int(_text(nums[1]))

        # Rank label like "B1｜東地区 6位"
        rank_el = kv.select_one(".clubDetail-kv-grades-rank-bold")
        rank_label = _text(rank_el) or None

    # Info block: arena, address, official URL
    arena = address = official_url = None
    for item in soup.select(".clubDetail-info-item dl"):
        dt = _text(item.select_one("dt"))
        dd = item.select_one("dd")
        if dd is None:
            continue
        if "公式サイト" in dt:
            a = dd.find("a", href=True)
            official_url = a["href"] if a else _text(dd)
        elif "アリーナ" in dt:
            arena = _text(dd)
        elif "住所" in dt:
            address = _text(dd)

    # Roster: first table.table-player
    roster: list[RosterEntry] = []
    roster_table = soup.select_one("table.table-player")
    if roster_table:
        for tr in roster_table.find_all("tr"):
            cells = tr.find_all(["td"])
            if not cells:
                continue  # header row
            entry = _parse_roster_row(cells)
            if entry:
                roster.append(entry)

    # Team season stats: first score-tab-table that isn't a roster table
    season_stats: list[TeamSeasonStat] = []
    for t in soup.select("table.score-tab-table"):
        classes = t.get("class", [])
        if "table-player" in classes:
            continue  # skip the roster
        for tr in t.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue
            s = _parse_team_stat_row(cells)
            if s:
                season_stats.append(s)
        break  # use only the first non-player score-tab-table

    return ClubDetail(
        team_id=team_id,
        name_ja=name_ja,
        name_en=name_en,
        wins=wins,
        losses=losses,
        rank_label=rank_label,
        arena=arena,
        address=address,
        official_url=official_url,
        roster=roster,
        season_stats=season_stats,
    )


# --- parse_roster_detail ---------------------------------------------------


def parse_roster_detail(html: str, player_id: int | None = None) -> PlayerDetail:
    """Parse /roster_detail/?PlayerID=X."""
    soup = BeautifulSoup(html, "lxml")

    kv = soup.select_one(".rosterDetail-kv")
    name_ja = ""
    name_en = None
    jersey = None
    team_id = None
    team_name = None

    if kv:
        name_ja_el = kv.select_one(".rosterDetail-kv-playerProfile-name")
        name_ja = _text(name_ja_el)

        first = kv.select_one(".js-player-first-name")
        last = kv.select_one(".js-player-last-name")
        name_en_parts = [_text(first), _text(last)]
        name_en = " ".join(p for p in name_en_parts if p) or None

        num_el = kv.select_one(".rosterDetail-kv-playerInfo-num")
        if num_el:
            # remove leading "#"
            num_text = _text(num_el).lstrip("#").strip()
            jersey = _parse_int(num_text)

        logo_a = kv.select_one(".rosterDetail-kv-logo a[href]")
        if logo_a:
            m = _RE_TEAMID.search(logo_a["href"])
            team_id = int(m.group(1)) if m else None

    # Profile list
    positions: list[str] = []
    birth_date = None
    age = None
    height_cm = weight_kg = None
    nationality = hometown = school = None

    for li in soup.select("li.rosterDetail-kv-playerProfile-list-item"):
        spans = li.find_all("span", recursive=False)
        if len(spans) < 2:
            continue
        label = _text(spans[0])
        value = _text(spans[1])
        if "ポジション" in label:
            positions = [p.strip() for p in value.split("/") if p.strip()]
        elif "生年月日" in label:
            birth_date = _jp_date_to_date(value)
            m_age = _RE_AGE.search(value)
            age = int(m_age.group(1)) if m_age else None
        elif "身長" in label or "体重" in label:
            m = _RE_HEIGHT_WEIGHT.search(value)
            if m:
                height_cm = int(m.group(1))
                weight_kg = int(m.group(2))
        elif "国籍" in label:
            nationality = value or None
        elif "出身地" in label:
            hometown = value or None
        elif "出身校" in label:
            school = value or None
        elif "クラブ所属履歴" in label:
            # latest (most recent) is typically at the top
            p = li.find("p")
            if p:
                text = _text(p)
                # e.g. "2025-26 仙台"
                parts = text.split()
                if len(parts) >= 2:
                    team_name = parts[1]

    return PlayerDetail(
        player_id=player_id,
        name_ja=name_ja,
        name_en=name_en,
        jersey_number=jersey,
        positions=positions,
        birth_date=birth_date,
        age=age,
        height_cm=height_cm,
        weight_kg=weight_kg,
        nationality=nationality,
        hometown=hometown,
        school=school,
        team_id=team_id,
        team_name=team_name,
    )


# --- parse_game_info -------------------------------------------------------


def parse_game_info(html: str, schedule_key: str | None = None) -> GameInfo:
    """Parse /game_detail/?ScheduleKey=X&tab=1 (top info tab).

    Extracts the breadcrumb title (which carries date + teams) and the top
    scoreboard match (for tipoff + team names + played/planned state).
    """
    soup = BeautifulSoup(html, "lxml")

    # Breadcrumb second item has the canonical title like:
    #   "りそなグループ B.LEAGUE 2025-26 B1リーグ戦 2026/04/22 仙台 VS 越谷"
    breadcrumb_title = ""
    for li in soup.select(".breadcrumb li"):
        name_span = li.select_one('[itemprop="name"]')
        txt = _text(name_span)
        if "VS" in txt or "vs" in txt:
            breadcrumb_title = txt
            break

    game_date = _jp_date_to_date(breadcrumb_title)

    # Competition (B1リーグ戦 / B1チャンピオンシップ ...) + season (2025-26)
    season = None
    competition = None
    m_season = re.search(r"(\d{4}-\d{2})", breadcrumb_title)
    if m_season:
        season = m_season.group(1)
    m_comp = re.search(r"(B[12]\S+?戦|B[12]チャンピオンシップ\S*)", breadcrumb_title)
    if m_comp:
        competition = m_comp.group(1)

    # First scoreboard__match is the focused game (tipoff/teams)
    home_name = away_name = ""
    tipoff = None
    is_planned = False
    match = soup.select_one(".scoreboard__match")
    if match:
        tipoff = _text(match.select_one(".scoreboard-match__title")) or None
        home_name = _text(match.select_one(".scoreboard-match__top-title"))
        away_name = _text(match.select_one(".scoreboard-match__bottom-title"))
        classes = match.get("class", [])
        is_planned = "scoreboard__match--planned" in classes

    # team IDs from club_detail links on the page
    home_team_id = away_team_id = None
    club_links = soup.select('a[href*="club_detail/?TeamID="]')
    team_ids: list[int] = []
    seen: set[int] = set()
    for a in club_links:
        m = _RE_TEAMID.search(a.get("href", ""))
        if m:
            tid = int(m.group(1))
            if tid not in seen:
                seen.add(tid)
                team_ids.append(tid)
    if len(team_ids) >= 2:
        home_team_id, away_team_id = team_ids[0], team_ids[1]

    # schedule_key: fall back to URL param inferred from href in breadcrumb area
    if schedule_key is None:
        for a in soup.select('a[href*="ScheduleKey="]'):
            m = _RE_SCHEDULEKEY.search(a["href"])
            if m:
                schedule_key = m.group(1)
                break

    return GameInfo(
        schedule_key=schedule_key or "",
        home_name=home_name,
        away_name=away_name,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        date=game_date,
        tipoff=tipoff,
        competition=competition,
        season=season,
        is_planned=is_planned,
    )

"""Scraper — B.LEAGUE 公式・チーム公式サイトからのデータ取得モジュール."""

from winb.scraper.bleague import (
    ClubDetail,
    GameInfo,
    PlayerDetail,
    RosterEntry,
    ScheduledGame,
    TeamSeasonStat,
    parse_club_detail,
    parse_game_info,
    parse_roster_detail,
    parse_schedule,
)
from winb.scraper.client import BleagueClient, FetchResult

__all__ = [
    # HTTP client
    "BleagueClient",
    "FetchResult",
    # Parsers
    "parse_schedule",
    "parse_club_detail",
    "parse_roster_detail",
    "parse_game_info",
    # Parser dataclasses
    "ScheduledGame",
    "RosterEntry",
    "TeamSeasonStat",
    "ClubDetail",
    "PlayerDetail",
    "GameInfo",
]

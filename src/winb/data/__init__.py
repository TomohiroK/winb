"""Data — DB モデル定義、ETL、データアクセス."""

from winb.data.adapters import (
    persist_club_detail,
    upsert_game_from_info,
    upsert_game_from_schedule,
    upsert_player,
    upsert_player_stub,
    upsert_player_team_history,
    upsert_roster_season_stat,
    upsert_team,
    upsert_team_season_stat,
    upsert_team_stub,
)
from winb.data.database import (
    get_database_url,
    get_engine,
    get_session_factory,
    reset_for_testing,
    session_scope,
)
from winb.data.models import (
    Base,
    Game,
    Player,
    PlayerBoxScore,
    PlayerTeamHistory,
    Prediction,
    RosterSeasonStat,
    Team,
    TeamBoxScore,
    TeamSeasonStat,
)

__all__ = [
    # Engine / session
    "get_database_url",
    "get_engine",
    "get_session_factory",
    "session_scope",
    "reset_for_testing",
    # ORM
    "Base",
    "Team",
    "Player",
    "PlayerTeamHistory",
    "Game",
    "TeamSeasonStat",
    "RosterSeasonStat",
    "TeamBoxScore",
    "PlayerBoxScore",
    "Prediction",
    # Adapters
    "upsert_team",
    "upsert_team_stub",
    "upsert_player",
    "upsert_player_stub",
    "upsert_player_team_history",
    "upsert_team_season_stat",
    "upsert_roster_season_stat",
    "upsert_game_from_info",
    "upsert_game_from_schedule",
    "persist_club_detail",
]

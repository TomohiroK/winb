"""SQLAlchemy ORM models for WinB.

Conventions:
- Primary keys that come from bleague.jp (team_id, player_id, schedule_key)
  are stored directly; auto-increment ids are only used where there is no
  natural key.
- Timestamps are stored as timezone-aware DateTime (UTC).
- Percentage stats (FG%, 3FG%, FT%) are stored as 0-100 floats (not 0-1).
- ``positions`` is serialized as a JSON array of strings ``["PG", "SG"]``.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base carrying shared metadata."""


# --- Mixins ---------------------------------------------------------------


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


# --- Master tables --------------------------------------------------------


class Team(Base, TimestampMixin):
    """Club / team master. Keyed by bleague.jp TeamID."""

    __tablename__ = "teams"

    team_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name_ja: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(100))
    code: Mapped[str | None] = mapped_column(
        String(8), index=True, doc="2-letter logo code, e.g. 'se'"
    )
    arena: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(500))
    official_url: Mapped[str | None] = mapped_column(String(500))

    # Reverse relationships
    home_games: Mapped[list[Game]] = relationship(
        back_populates="home_team", foreign_keys="Game.home_team_id"
    )
    away_games: Mapped[list[Game]] = relationship(
        back_populates="away_team", foreign_keys="Game.away_team_id"
    )

    def __repr__(self) -> str:
        return f"Team(team_id={self.team_id}, name_ja={self.name_ja!r})"


class Player(Base, TimestampMixin):
    """Player master. Keyed by bleague.jp PlayerID."""

    __tablename__ = "players"

    player_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name_ja: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(100))
    birth_date: Mapped[date | None] = mapped_column(Date, index=True)
    height_cm: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[int | None] = mapped_column(Integer)
    nationality: Mapped[str | None] = mapped_column(String(50), index=True)
    hometown: Mapped[str | None] = mapped_column(String(100))
    school: Mapped[str | None] = mapped_column(String(200))

    history: Mapped[list[PlayerTeamHistory]] = relationship(back_populates="player")

    def __repr__(self) -> str:
        return f"Player(player_id={self.player_id}, name_ja={self.name_ja!r})"


class PlayerTeamHistory(Base, TimestampMixin):
    """Per-season team assignment for a player.

    Modeled as one row per (player, season) so mid-season transfers are not
    tracked yet; we can extend with start_date / end_date columns later.
    """

    __tablename__ = "player_team_history"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_team_history_ps"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("players.player_id", ondelete="CASCADE"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.team_id", ondelete="CASCADE"), index=True
    )
    jersey_number: Mapped[int | None] = mapped_column(Integer)
    positions: Mapped[list[str] | None] = mapped_column(
        JSONB, doc='JSON array of strings, e.g. ["PG", "SG"]'
    )

    player: Mapped[Player] = relationship(back_populates="history")
    team: Mapped[Team] = relationship()


# --- Games & results ------------------------------------------------------


class Game(Base, TimestampMixin):
    """One scheduled B.LEAGUE game. Keyed by ScheduleKey."""

    __tablename__ = "games"

    schedule_key: Mapped[str] = mapped_column(String(12), primary_key=True)

    season: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    competition: Mapped[str | None] = mapped_column(String(80), index=True)
    section: Mapped[str | None] = mapped_column(String(40))
    is_cs: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    game_date: Mapped[date | None] = mapped_column(Date, index=True)
    tipoff: Mapped[str | None] = mapped_column(String(10), doc="HH:MM in JST")
    venue: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(
        String(200), doc='Raw location text from schedule, e.g. "北海道 | よつ葉"'
    )

    home_team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.team_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    away_team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.team_id", ondelete="RESTRICT"), nullable=False, index=True
    )

    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    home_team: Mapped[Team] = relationship(
        back_populates="home_games", foreign_keys=[home_team_id]
    )
    away_team: Mapped[Team] = relationship(
        back_populates="away_games", foreign_keys=[away_team_id]
    )

    __table_args__ = (
        CheckConstraint("home_team_id <> away_team_id", name="ck_games_distinct_teams"),
    )

    def __repr__(self) -> str:
        return (
            f"Game(schedule_key={self.schedule_key!r}, date={self.game_date}, "
            f"{self.home_team_id} vs {self.away_team_id})"
        )


# --- Stats tables ---------------------------------------------------------


class TeamSeasonStat(Base, TimestampMixin):
    """Season-level team stats, as shown on /club_detail/."""

    __tablename__ = "team_season_stats"
    __table_args__ = (
        UniqueConstraint("team_id", "season", "game_type", name="uq_team_season_stats"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.team_id", ondelete="CASCADE"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    game_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    wins: Mapped[int] = mapped_column(Integer, nullable=False)
    losses: Mapped[int] = mapped_column(Integer, nullable=False)
    ppg: Mapped[float | None] = mapped_column(Float)
    opp_ppg: Mapped[float | None] = mapped_column(Float)
    fg_pct: Mapped[float | None] = mapped_column(Float)
    three_fg_pct: Mapped[float | None] = mapped_column(Float)
    ft_pct: Mapped[float | None] = mapped_column(Float)
    rpg: Mapped[float | None] = mapped_column(Float)
    apg: Mapped[float | None] = mapped_column(Float)
    topg: Mapped[float | None] = mapped_column(Float)
    spg: Mapped[float | None] = mapped_column(Float)
    bpg: Mapped[float | None] = mapped_column(Float)


class RosterSeasonStat(Base, TimestampMixin):
    """Season-level per-player aggregate stats (from table.table-player)."""

    __tablename__ = "roster_season_stats"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "season", "game_type", name="uq_roster_season_stats"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("players.player_id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("teams.team_id", ondelete="SET NULL"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    game_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    games: Mapped[int | None] = mapped_column(Integer)
    ppg: Mapped[float | None] = mapped_column(Float)
    fg_pct: Mapped[float | None] = mapped_column(Float)
    three_fg_pct: Mapped[float | None] = mapped_column(Float)
    ft_pct: Mapped[float | None] = mapped_column(Float)
    rpg: Mapped[float | None] = mapped_column(Float)
    apg: Mapped[float | None] = mapped_column(Float)
    topg: Mapped[float | None] = mapped_column(Float)
    spg: Mapped[float | None] = mapped_column(Float)
    bpg: Mapped[float | None] = mapped_column(Float)
    eff: Mapped[float | None] = mapped_column(Float)


# --- Box scores (populated later from JS-rendered pages) ------------------


class TeamBoxScore(Base, TimestampMixin):
    """Per-game team stats. Filled later when we add a Playwright path for
    game_detail tab=4 box scores.
    """

    __tablename__ = "team_box_scores"
    __table_args__ = (
        UniqueConstraint("schedule_key", "team_id", name="uq_team_box_scores"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_key: Mapped[str] = mapped_column(
        String(12),
        ForeignKey("games.schedule_key", ondelete="CASCADE"),
        index=True,
    )
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.team_id", ondelete="CASCADE"), index=True
    )
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)

    pts: Mapped[int | None] = mapped_column(Integer)
    fga: Mapped[int | None] = mapped_column(Integer)
    fgm: Mapped[int | None] = mapped_column(Integer)
    fg_pct: Mapped[float | None] = mapped_column(Float)
    tpa: Mapped[int | None] = mapped_column(Integer)
    tpm: Mapped[int | None] = mapped_column(Integer)
    tp_pct: Mapped[float | None] = mapped_column(Float)
    fta: Mapped[int | None] = mapped_column(Integer)
    ftm: Mapped[int | None] = mapped_column(Integer)
    ft_pct: Mapped[float | None] = mapped_column(Float)
    oreb: Mapped[int | None] = mapped_column(Integer)
    dreb: Mapped[int | None] = mapped_column(Integer)
    reb: Mapped[int | None] = mapped_column(Integer)
    ast: Mapped[int | None] = mapped_column(Integer)
    tov: Mapped[int | None] = mapped_column(Integer)
    stl: Mapped[int | None] = mapped_column(Integer)
    blk: Mapped[int | None] = mapped_column(Integer)
    pf: Mapped[int | None] = mapped_column(Integer)
    # Quarter scores (OT combined for now)
    q1: Mapped[int | None] = mapped_column(Integer)
    q2: Mapped[int | None] = mapped_column(Integer)
    q3: Mapped[int | None] = mapped_column(Integer)
    q4: Mapped[int | None] = mapped_column(Integer)
    ot: Mapped[int | None] = mapped_column(Integer)


class PlayerBoxScore(Base, TimestampMixin):
    """Per-game per-player stats."""

    __tablename__ = "player_box_scores"
    __table_args__ = (
        UniqueConstraint("schedule_key", "player_id", name="uq_player_box_scores"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_key: Mapped[str] = mapped_column(
        String(12),
        ForeignKey("games.schedule_key", ondelete="CASCADE"),
        index=True,
    )
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("players.player_id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.team_id", ondelete="CASCADE"), index=True
    )
    is_starter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_played_sec: Mapped[int | None] = mapped_column(
        Integer, doc="Minutes played, in seconds (e.g. 1800 = 30:00)"
    )

    pts: Mapped[int | None] = mapped_column(Integer)
    fga: Mapped[int | None] = mapped_column(Integer)
    fgm: Mapped[int | None] = mapped_column(Integer)
    tpa: Mapped[int | None] = mapped_column(Integer)
    tpm: Mapped[int | None] = mapped_column(Integer)
    fta: Mapped[int | None] = mapped_column(Integer)
    ftm: Mapped[int | None] = mapped_column(Integer)
    oreb: Mapped[int | None] = mapped_column(Integer)
    dreb: Mapped[int | None] = mapped_column(Integer)
    ast: Mapped[int | None] = mapped_column(Integer)
    tov: Mapped[int | None] = mapped_column(Integer)
    stl: Mapped[int | None] = mapped_column(Integer)
    blk: Mapped[int | None] = mapped_column(Integer)
    pf: Mapped[int | None] = mapped_column(Integer)
    plus_minus: Mapped[int | None] = mapped_column(Integer)
    eff: Mapped[float | None] = mapped_column(Float)


# --- Predictions ---------------------------------------------------------


class Prediction(Base, TimestampMixin):
    """Every prediction the model produces, including post-hoc evaluation."""

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "schedule_key",
            "model_version",
            "predicted_at",
            name="uq_predictions",
        ),
        CheckConstraint(
            "home_win_prob >= 0 AND home_win_prob <= 1",
            name="ck_predictions_home_prob_range",
        ),
        CheckConstraint(
            "away_win_prob >= 0 AND away_win_prob <= 1",
            name="ck_predictions_away_prob_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_key: Mapped[str] = mapped_column(
        String(12),
        ForeignKey("games.schedule_key", ondelete="CASCADE"),
        index=True,
    )
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    home_win_prob: Mapped[float] = mapped_column(Float, nullable=False)
    away_win_prob: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_margin: Mapped[float | None] = mapped_column(
        Float, doc="Expected home point margin (home - away)."
    )

    actual_home_win: Mapped[bool | None] = mapped_column(
        Boolean, doc="Filled after the game. NULL until final."
    )
    notes: Mapped[dict | None] = mapped_column(
        JSONB, doc="Free-form JSON: features used, explanation, etc."
    )

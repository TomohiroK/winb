"""ORM tests against the live PostgreSQL container.

Each test runs inside a transaction that is rolled back afterwards so the
database state stays clean.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from winb.data import (
    Game,
    Player,
    PlayerTeamHistory,
    Prediction,
    RosterSeasonStat,
    Team,
    TeamSeasonStat,
    get_engine,
)


@pytest.fixture
def session() -> Session:
    """Per-test session inside a transaction that is rolled back after.

    IntegrityError on flush() auto-rolls the underlying transaction, so we
    only rollback if it is still active. Otherwise SQLAlchemy emits a
    "transaction already deassociated" warning.
    """
    engine = get_engine()
    connection = engine.connect()
    trans = connection.begin()
    Session_ = sessionmaker(bind=connection, future=True, expire_on_commit=False)
    s = Session_()
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        connection.close()


# --- Team / Player master -------------------------------------------------


class TestTeam:
    def test_insert_and_fetch(self, session):
        team = Team(
            team_id=692,
            name_ja="仙台89ERS",
            name_en="SENDAI 89ERS",
            code="se",
            arena="ゼビオアリーナ仙台",
            official_url="https://www.89ers.jp",
        )
        session.add(team)
        session.flush()

        got = session.scalar(select(Team).where(Team.team_id == 692))
        assert got is not None
        assert got.name_ja == "仙台89ERS"
        assert got.code == "se"

    def test_duplicate_team_id_fails(self, session):
        session.add(Team(team_id=999, name_ja="A"))
        session.flush()
        session.add(Team(team_id=999, name_ja="B"))
        with pytest.raises(IntegrityError):
            session.flush()


class TestPlayer:
    def test_insert_with_all_fields(self, session):
        p = Player(
            player_id=51000531,
            name_ja="ジャレット・カルバー",
            name_en="Jarrett Culver",
            birth_date=date(1999, 2, 20),
            height_cm=198,
            weight_kg=88,
            nationality="アメリカ合衆国",
            hometown="アメリカ合衆国",
            school="テキサス工科大学",
        )
        session.add(p)
        session.flush()

        got = session.scalar(select(Player).where(Player.player_id == 51000531))
        assert got.height_cm == 198
        assert got.birth_date == date(1999, 2, 20)


# --- PlayerTeamHistory ---------------------------------------------------


class TestPlayerTeamHistory:
    def test_history_entry(self, session):
        team = Team(team_id=692, name_ja="仙台89ERS")
        player = Player(player_id=51000531, name_ja="カルバー")
        session.add_all([team, player])
        session.flush()

        h = PlayerTeamHistory(
            player_id=51000531,
            season="2025-26",
            team_id=692,
            jersey_number=8,
            positions=["SG", "SF"],
        )
        session.add(h)
        session.flush()

        got = session.scalar(
            select(PlayerTeamHistory).where(
                PlayerTeamHistory.player_id == 51000531,
                PlayerTeamHistory.season == "2025-26",
            )
        )
        assert got.jersey_number == 8
        assert got.positions == ["SG", "SF"]

    def test_unique_player_season(self, session):
        team = Team(team_id=692, name_ja="仙台")
        player = Player(player_id=51000531, name_ja="カルバー")
        session.add_all([team, player])
        session.flush()

        session.add(PlayerTeamHistory(player_id=51000531, season="2025-26", team_id=692))
        session.flush()
        # Same player + same season should be rejected.
        session.add(PlayerTeamHistory(player_id=51000531, season="2025-26", team_id=692))
        with pytest.raises(IntegrityError):
            session.flush()


# --- Game ----------------------------------------------------------------


class TestGame:
    def test_game_with_relationships(self, session):
        home = Team(team_id=692, name_ja="仙台")
        away = Team(team_id=745, name_ja="越谷")
        session.add_all([home, away])
        session.flush()

        g = Game(
            schedule_key="505443",
            season="2025-26",
            competition="B1リーグ戦",
            section="第34節",
            game_date=date(2026, 4, 22),
            tipoff="19:05",
            venue="カメイアリーナ仙台",
            home_team_id=692,
            away_team_id=745,
            is_final=False,
        )
        session.add(g)
        session.flush()

        got = session.scalar(select(Game).where(Game.schedule_key == "505443"))
        assert got.home_team.name_ja == "仙台"
        assert got.away_team.name_ja == "越谷"
        assert got.is_cs is False

    def test_same_team_home_and_away_rejected(self, session):
        team = Team(team_id=692, name_ja="仙台")
        session.add(team)
        session.flush()

        g = Game(
            schedule_key="999999",
            season="2025-26",
            game_date=date(2026, 4, 22),
            home_team_id=692,
            away_team_id=692,
        )
        session.add(g)
        with pytest.raises(IntegrityError):
            session.flush()


# --- Stats ---------------------------------------------------------------


class TestSeasonStats:
    def test_team_season_stats(self, session):
        session.add(Team(team_id=692, name_ja="仙台"))
        session.flush()

        s = TeamSeasonStat(
            team_id=692,
            season="2025-26",
            game_type="B1",
            wins=33,
            losses=22,
            ppg=82.2,
            opp_ppg=79.3,
            fg_pct=44.5,
        )
        session.add(s)
        session.flush()

        got = session.scalar(
            select(TeamSeasonStat).where(
                TeamSeasonStat.team_id == 692,
                TeamSeasonStat.season == "2025-26",
                TeamSeasonStat.game_type == "B1",
            )
        )
        assert got.wins == 33 and got.losses == 22
        assert got.ppg == pytest.approx(82.2)

    def test_roster_season_stats_with_nullable_team(self, session):
        session.add(Player(player_id=51000531, name_ja="カルバー"))
        session.flush()

        s = RosterSeasonStat(
            player_id=51000531,
            team_id=None,  # nullable
            season="2025-26",
            game_type="B1",
            games=55,
            ppg=25.8,
            fg_pct=45.8,
            three_fg_pct=32.0,
            ft_pct=82.7,
            rpg=5.9,
            apg=3.1,
        )
        session.add(s)
        session.flush()

        got = session.scalar(
            select(RosterSeasonStat).where(RosterSeasonStat.player_id == 51000531)
        )
        assert got.games == 55
        assert got.ppg == pytest.approx(25.8)


# --- Predictions (check constraints) -------------------------------------


class TestPrediction:
    def _setup_minimal(self, session):
        session.add_all(
            [
                Team(team_id=692, name_ja="仙台"),
                Team(team_id=745, name_ja="越谷"),
            ]
        )
        session.flush()
        session.add(
            Game(
                schedule_key="505443",
                season="2025-26",
                game_date=date(2026, 4, 22),
                home_team_id=692,
                away_team_id=745,
            )
        )
        session.flush()

    def test_valid_probabilities(self, session):
        self._setup_minimal(session)
        p = Prediction(
            schedule_key="505443",
            model_version="v0.1-baseline",
            predicted_at=datetime.now(timezone.utc),
            home_win_prob=0.62,
            away_win_prob=0.38,
            predicted_margin=5.2,
            notes={"features": ["elo_diff", "rest_advantage"]},
        )
        session.add(p)
        session.flush()

        got = session.scalar(select(Prediction).where(Prediction.schedule_key == "505443"))
        assert got.notes == {"features": ["elo_diff", "rest_advantage"]}

    def test_probability_out_of_range_rejected(self, session):
        self._setup_minimal(session)
        p = Prediction(
            schedule_key="505443",
            model_version="v0.1",
            predicted_at=datetime.now(timezone.utc),
            home_win_prob=1.5,  # invalid: >1
            away_win_prob=0.5,
        )
        session.add(p)
        with pytest.raises(IntegrityError):
            session.flush()

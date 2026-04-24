"""Tests for winb.data.adapters — parser → ORM upserts."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from winb.data import (
    Game,
    Player,
    PlayerTeamHistory,
    RosterSeasonStat,
    Team,
    TeamSeasonStat,
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
from winb.scraper.bleague import (
    ClubDetail,
    GameInfo,
    PlayerDetail,
    RosterEntry,
    ScheduledGame,
)
from winb.scraper.bleague import TeamSeasonStat as ParsedTeamSeasonStat
from winb.scraper.bleague import (
    parse_club_detail,
    parse_game_info,
    parse_schedule,
    parse_roster_detail,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "bleague"


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


# --- Team ------------------------------------------------------------------


class TestUpsertTeam:
    def test_insert_new(self, session):
        cd = ClubDetail(
            team_id=692,
            name_ja="仙台89ERS",
            name_en="SENDAI 89ERS",
            wins=33,
            losses=22,
            rank_label=None,
            arena="ゼビオアリーナ仙台",
            address=None,
            official_url="https://www.89ers.jp",
        )
        team = upsert_team(session, cd)
        session.flush()

        got = session.get(Team, 692)
        assert got is not None
        assert got.name_ja == "仙台89ERS"
        assert got.name_en == "SENDAI 89ERS"
        assert got.arena == "ゼビオアリーナ仙台"
        assert got.official_url == "https://www.89ers.jp"

    def test_update_existing(self, session):
        session.add(Team(team_id=692, name_ja="Old Name"))
        session.flush()

        cd = ClubDetail(
            team_id=692,
            name_ja="仙台89ERS",
            name_en="SENDAI 89ERS",
            wins=None,
            losses=None,
            rank_label=None,
            arena="New Arena",
            address=None,
            official_url=None,
        )
        upsert_team(session, cd)
        session.flush()

        got = session.get(Team, 692)
        assert got.name_ja == "仙台89ERS"  # overwritten
        assert got.arena == "New Arena"

    def test_team_id_required(self, session):
        cd = ClubDetail(
            team_id=None,
            name_ja="X",
            name_en=None,
            wins=None,
            losses=None,
            rank_label=None,
            arena=None,
            address=None,
            official_url=None,
        )
        with pytest.raises(ValueError, match="team_id"):
            upsert_team(session, cd)


class TestUpsertTeamStub:
    def test_creates_when_missing(self, session):
        t = upsert_team_stub(session, 999, "仮")
        session.flush()
        assert session.get(Team, 999).name_ja == "仮"

    def test_returns_existing_without_overwriting(self, session):
        session.add(Team(team_id=999, name_ja="Real"))
        session.flush()
        t = upsert_team_stub(session, 999, "Stub Name")
        session.flush()
        assert t.name_ja == "Real"  # unchanged


# --- Player ----------------------------------------------------------------


class TestUpsertPlayer:
    def test_insert_and_update(self, session):
        pd = PlayerDetail(
            player_id=51000531,
            name_ja="ジャレット・カルバー",
            name_en="Jarrett Culver",
            jersey_number=8,  # not stored on Player
            positions=["SG", "SF"],  # not stored on Player
            birth_date=date(1999, 2, 20),
            age=27,
            height_cm=198,
            weight_kg=88,
            nationality="アメリカ合衆国",
            hometown="アメリカ合衆国",
            school="テキサス工科大学",
            team_id=692,
            team_name="仙台",
        )
        upsert_player(session, pd)
        session.flush()
        p = session.get(Player, 51000531)
        assert p.height_cm == 198
        assert p.birth_date == date(1999, 2, 20)
        assert p.nationality == "アメリカ合衆国"

        # Update: change height, ensure others retained
        pd2 = PlayerDetail(
            player_id=51000531,
            name_ja="ジャレット・カルバー",
            name_en="Jarrett Culver",
            jersey_number=8,
            positions=["SG"],
            birth_date=None,  # none-valued → not overwritten
            age=None,
            height_cm=199,
            weight_kg=None,
            nationality=None,
            hometown=None,
            school=None,
            team_id=692,
            team_name="仙台",
        )
        upsert_player(session, pd2)
        session.flush()
        p = session.get(Player, 51000531)
        assert p.height_cm == 199  # updated
        assert p.birth_date == date(1999, 2, 20)  # unchanged (None not applied)


class TestUpsertPlayerStub:
    def test_stub_creates_and_fills_blank_name(self, session):
        # Pre-existing player with empty name
        session.add(Player(player_id=42, name_ja=""))
        session.flush()

        upsert_player_stub(session, 42, "新しい名前")
        session.flush()
        assert session.get(Player, 42).name_ja == "新しい名前"

    def test_stub_does_not_overwrite_real_name(self, session):
        session.add(Player(player_id=42, name_ja="本名"))
        session.flush()
        upsert_player_stub(session, 42, "Stub Name")
        session.flush()
        assert session.get(Player, 42).name_ja == "本名"


# --- PlayerTeamHistory -----------------------------------------------------


class TestUpsertPlayerTeamHistory:
    def test_insert_and_update(self, session):
        session.add_all([Team(team_id=692, name_ja="仙台"), Player(player_id=51000531, name_ja="カルバー")])
        session.flush()

        h = upsert_player_team_history(
            session,
            player_id=51000531,
            team_id=692,
            season="2025-26",
            jersey_number=8,
            positions=["SG", "SF"],
        )
        session.flush()
        assert h.jersey_number == 8
        assert h.positions == ["SG", "SF"]

        # Update the same row
        h2 = upsert_player_team_history(
            session,
            player_id=51000531,
            team_id=692,
            season="2025-26",
            jersey_number=9,
            positions=["SF"],
        )
        session.flush()
        assert h2.id == h.id
        assert h2.jersey_number == 9
        assert h2.positions == ["SF"]


# --- TeamSeasonStat --------------------------------------------------------


def _sample_tss(season="2025-26", game_type="B1", wins=33, losses=22) -> ParsedTeamSeasonStat:
    return ParsedTeamSeasonStat(
        season=season,
        game_type=game_type,
        wins=wins,
        losses=losses,
        ppg=82.2,
        opp_ppg=79.3,
        fg_pct=44.5,
        three_fg_pct=34.5,
        ft_pct=72.9,
        rpg=37.6,
        apg=19.4,
        topg=11.8,
        spg=8.3,
        bpg=2.9,
    )


class TestUpsertTeamSeasonStat:
    def test_insert_and_update(self, session):
        session.add(Team(team_id=692, name_ja="仙台"))
        session.flush()

        stat = upsert_team_season_stat(session, 692, _sample_tss())
        session.flush()
        assert stat.wins == 33

        # Update
        updated = _sample_tss(wins=40, losses=20)
        upsert_team_season_stat(session, 692, updated)
        session.flush()
        got = session.scalar(
            select(TeamSeasonStat).where(
                TeamSeasonStat.team_id == 692,
                TeamSeasonStat.season == "2025-26",
                TeamSeasonStat.game_type == "B1",
            )
        )
        assert got.wins == 40
        assert got.losses == 20


# --- RosterSeasonStat ------------------------------------------------------


def _sample_roster_entry() -> RosterEntry:
    return RosterEntry(
        player_id=51000531,
        jersey_number=8,
        name="カルバー",
        season="2025-26",
        game_type="B1",
        positions=["SG", "SF"],
        games=55,
        ppg=25.8,
        fg_pct=45.8,
        three_fg_pct=32.0,
        ft_pct=82.7,
        rpg=5.9,
        apg=3.1,
        spg=1.0,
        bpg=0.3,
        topg=2.1,
        eff=24.1,
    )


class TestUpsertRosterSeasonStat:
    def test_insert(self, session):
        session.add_all(
            [Team(team_id=692, name_ja="仙台"), Player(player_id=51000531, name_ja="カルバー")]
        )
        session.flush()

        upsert_roster_season_stat(
            session, player_id=51000531, team_id=692, entry=_sample_roster_entry()
        )
        session.flush()

        got = session.scalar(
            select(RosterSeasonStat).where(RosterSeasonStat.player_id == 51000531)
        )
        assert got.games == 55
        assert got.ppg == pytest.approx(25.8)
        assert got.team_id == 692


# --- upsert_game_from_info -------------------------------------------------


class TestUpsertGameFromInfo:
    def _info(self) -> GameInfo:
        return GameInfo(
            schedule_key="505443",
            home_name="仙台",
            away_name="越谷",
            home_team_id=692,
            away_team_id=745,
            date=date(2026, 4, 22),
            tipoff="19:05",
            competition="B1リーグ戦",
            season="2025-26",
            is_planned=True,
        )

    def test_insert_new_creates_team_stubs(self, session):
        # Neither team exists; adapter should stub them.
        info = self._info()
        upsert_game_from_info(session, info)
        session.flush()

        g = session.get(Game, "505443")
        assert g.home_team_id == 692
        assert g.away_team_id == 745
        assert g.game_date == date(2026, 4, 22)
        assert g.is_final is False  # is_planned=True
        assert g.is_cs is False
        # team stubs
        assert session.get(Team, 692).name_ja == "仙台"
        assert session.get(Team, 745).name_ja == "越谷"

    def test_rejects_same_home_away(self, session):
        info = self._info()
        info.away_team_id = 692  # same as home
        with pytest.raises(ValueError, match="differ"):
            upsert_game_from_info(session, info)

    def test_cs_flag_from_competition(self, session):
        info = self._info()
        info.competition = "B1チャンピオンシップ ファイナル"
        upsert_game_from_info(session, info)
        session.flush()
        g = session.get(Game, "505443")
        assert g.is_cs is True


# --- upsert_game_from_schedule --------------------------------------------


class TestUpsertGameFromSchedule:
    def test_final_game_with_scores(self, session):
        sg = ScheduledGame(
            schedule_key="505326",
            home_name="北海道",
            away_name="茨城",
            home_code="lh",
            away_code="ir",
            section="第28節",
            location="北海道 | よつ葉",
            tipoff="15:05",
            is_final=True,
            home_score=88,
            away_score=85,
        )
        upsert_game_from_schedule(
            session,
            sg,
            season="2025-26",
            home_team_id=688,  # arbitrary
            away_team_id=685,
            game_date=date(2026, 4, 19),
            competition="B1リーグ戦",
        )
        session.flush()

        g = session.get(Game, "505326")
        assert g.home_score == 88
        assert g.away_score == 85
        assert g.is_final is True
        assert g.season == "2025-26"
        assert g.section == "第28節"


# --- persist_club_detail end-to-end ---------------------------------------


class TestPersistClubDetail:
    def test_full_sendai_page(self, session):
        html = _fixture("club_detail_692.html")
        club = parse_club_detail(html, team_id=692)

        persist_club_detail(session, club)
        session.flush()

        # Team
        team = session.get(Team, 692)
        assert team is not None
        assert team.name_ja == "仙台89ERS"
        assert team.name_en == "SENDAI 89ERS"

        # Season stats (15 rows observed in smoke test)
        n_stats = session.scalar(
            select(func.count()).select_from(TeamSeasonStat).where(TeamSeasonStat.team_id == 692)
        )
        assert n_stats >= 5

        # Roster: 13 PlayerTeamHistory rows for 2025-26
        n_history = session.scalar(
            select(func.count()).select_from(PlayerTeamHistory).where(
                PlayerTeamHistory.team_id == 692,
                PlayerTeamHistory.season == "2025-26",
            )
        )
        assert n_history == 13

        # Player stubs created for all 13
        n_players = session.scalar(
            select(func.count()).select_from(Player).where(
                Player.player_id.in_([r.player_id for r in club.roster])
            )
        )
        assert n_players == 13

        # Roster season stats
        n_roster_stats = session.scalar(
            select(func.count()).select_from(RosterSeasonStat).where(
                RosterSeasonStat.team_id == 692,
                RosterSeasonStat.season == "2025-26",
            )
        )
        assert n_roster_stats == 13

    def test_idempotent_persist(self, session):
        html = _fixture("club_detail_692.html")
        club = parse_club_detail(html, team_id=692)

        persist_club_detail(session, club)
        session.flush()
        persist_club_detail(session, club)  # 2nd run should not duplicate
        session.flush()

        n_history = session.scalar(
            select(func.count()).select_from(PlayerTeamHistory).where(
                PlayerTeamHistory.team_id == 692,
                PlayerTeamHistory.season == "2025-26",
            )
        )
        assert n_history == 13  # still 13, not 26


# --- Integration: parse → adapter with GameInfo fixture -------------------


class TestGameInfoFixture:
    def test_sendai_vs_koshigaya(self, session):
        html = _fixture("game_detail_505443.html")
        info = parse_game_info(html, schedule_key="505443")

        upsert_game_from_info(session, info)
        session.flush()

        g = session.get(Game, "505443")
        assert g.home_team_id == 692
        assert g.away_team_id == 745
        assert g.game_date == date(2026, 4, 22)
        assert g.tipoff == "19:05"
        assert g.season == "2025-26"
        assert g.is_final is False  # future game in the fixture
        assert g.is_cs is False

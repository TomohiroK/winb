"""Tests for winb.scraper.bleague parsers.

Uses cached real HTML fixtures under tests/fixtures/bleague/ so the
tests do not hit the network.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from winb.scraper.bleague import (
    ClubDetail,
    GameInfo,
    PlayerDetail,
    ScheduledGame,
    TeamSeasonStat,
    parse_club_detail,
    parse_game_info,
    parse_roster_detail,
    parse_schedule,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "bleague"


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


# --- parse_schedule --------------------------------------------------------


@pytest.fixture(scope="module")
def schedule_games() -> list[ScheduledGame]:
    return parse_schedule(_fixture("schedule_2026_04.html"))


class TestParseSchedule:
    def test_finds_13_games(self, schedule_games):
        assert len(schedule_games) == 13

    def test_first_game(self, schedule_games):
        g = schedule_games[0]
        assert g.schedule_key == "505326"
        assert g.home_name == "北海道"
        assert g.away_name == "茨城"
        assert g.home_score == 88
        assert g.away_score == 85
        assert g.is_final is True

    def test_logo_codes_extracted(self, schedule_games):
        g = schedule_games[0]
        assert g.home_code == "lh"  # Levanga Hokkaido
        assert g.away_code == "ir"  # Ibaraki Robots

    def test_section_location_tipoff(self, schedule_games):
        g = schedule_games[0]
        assert g.section == "第28節"
        # location like "北海道 | よつ葉"
        assert g.location and "北海道" in g.location
        assert g.tipoff == "15:05"

    def test_sendai_game(self, schedule_games):
        # Second game in fixture: 仙台 vs A東京
        g = schedule_games[1]
        assert g.schedule_key == "505327"
        assert g.home_name == "仙台"
        assert g.home_code == "se"
        assert g.away_name == "A東京"
        assert g.away_code == "at"
        assert g.is_final is True

    def test_all_keys_are_digit_strings(self, schedule_games):
        for g in schedule_games:
            assert g.schedule_key.isdigit()
            assert len(g.schedule_key) == 6


# --- parse_club_detail -----------------------------------------------------


@pytest.fixture(scope="module")
def club() -> ClubDetail:
    return parse_club_detail(_fixture("club_detail_692.html"), team_id=692)


class TestParseClubDetail:
    def test_team_names(self, club):
        assert club.name_en == "SENDAI 89ERS"
        assert club.name_ja == "仙台89ERS"

    def test_record(self, club):
        assert club.wins == 33
        assert club.losses == 22

    def test_rank_label(self, club):
        assert club.rank_label and "東地区" in club.rank_label
        assert "6位" in club.rank_label

    def test_arena(self, club):
        assert club.arena == "ゼビオアリーナ仙台"

    def test_official_url(self, club):
        assert club.official_url == "https://www.89ers.jp"

    def test_roster_size(self, club):
        assert len(club.roster) == 13  # 13 players in the roster table

    def test_roster_player_details(self, club):
        # Every roster entry must have a positive player_id
        for r in club.roster:
            assert r.player_id and r.player_id > 0
            assert r.name
            assert r.positions  # at least one position

    def test_roster_contains_culver(self, club):
        names = [r.name for r in club.roster]
        assert any("カルバー" in n for n in names)

    def test_season_stats_count(self, club):
        # Team stat table has 18 rows incl. headers (16 header rows? empirically
        # at least a handful of data rows). Just assert we got plural data.
        assert len(club.season_stats) >= 5

    def test_2025_26_stats(self, club):
        current = next(
            (s for s in club.season_stats if s.season == "2025-26" and s.game_type == "B1"),
            None,
        )
        assert current is not None
        assert current.wins == 33
        assert current.losses == 22
        assert current.ppg == pytest.approx(82.2, abs=0.05)


# --- parse_roster_detail ---------------------------------------------------


@pytest.fixture(scope="module")
def player() -> PlayerDetail:
    return parse_roster_detail(
        _fixture("roster_detail_51000531.html"), player_id=51000531
    )


class TestParseRosterDetail:
    def test_names(self, player):
        assert "カルバー" in player.name_ja
        assert player.name_en == "Jarrett Culver"

    def test_jersey(self, player):
        assert player.jersey_number == 8

    def test_positions(self, player):
        assert player.positions == ["SG", "SF"]

    def test_birth_date(self, player):
        assert player.birth_date == date(1999, 2, 20)
        assert player.age == 27

    def test_height_weight(self, player):
        assert player.height_cm == 198
        assert player.weight_kg == 88

    def test_nationality(self, player):
        assert player.nationality == "アメリカ合衆国"

    def test_team_link(self, player):
        assert player.team_id == 692
        assert player.team_name == "仙台"

    def test_school(self, player):
        assert player.school and "テキサス" in player.school


# --- parse_game_info -------------------------------------------------------


@pytest.fixture(scope="module")
def gi() -> GameInfo:
    return parse_game_info(_fixture("game_detail_505443.html"), schedule_key="505443")


class TestParseGameInfo:
    def test_schedule_key(self, gi):
        assert gi.schedule_key == "505443"

    def test_teams(self, gi):
        assert gi.home_name == "仙台"
        assert gi.away_name == "越谷"

    def test_date(self, gi):
        assert gi.date == date(2026, 4, 22)

    def test_tipoff(self, gi):
        assert gi.tipoff == "19:05"

    def test_planned(self, gi):
        assert gi.is_planned is True  # Future game at fixture time

    def test_team_ids(self, gi):
        assert gi.home_team_id == 692  # 仙台
        assert gi.away_team_id == 745  # 越谷

    def test_season_competition(self, gi):
        assert gi.season == "2025-26"
        assert gi.competition and "B1" in gi.competition


# --- parser-level sanity: dataclass shapes --------------------------------


def test_team_season_stat_dataclass():
    s = TeamSeasonStat(
        season="2025-26",
        game_type="B1",
        wins=33,
        losses=22,
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
    assert s.wins == 33

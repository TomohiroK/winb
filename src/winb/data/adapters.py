"""Adapters from scraper dataclasses to ORM models.

These functions take parsed dataclasses from :mod:`winb.scraper.bleague`
and upsert them into the database. "Upsert" here means:

- If a row with the natural key already exists, selected fields are updated.
- Otherwise a new row is inserted.

Callers are responsible for providing the SQLAlchemy session and for
committing the transaction. Adapters always ``session.flush()`` to surface
integrity errors early, but they never commit.

None-valued fields on the incoming dataclass usually leave existing DB
values untouched (so a partial re-parse does not wipe data).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from winb.data.models import (
    Game,
    Player,
    PlayerTeamHistory,
    RosterSeasonStat,
    Team,
    TeamSeasonStat,
)
from winb.scraper.bleague import (
    ClubDetail,
    GameInfo,
    PlayerDetail,
    RosterEntry,
    ScheduledGame,
)
from winb.scraper.bleague import TeamSeasonStat as ParsedTeamSeasonStat


# --- Team ------------------------------------------------------------------


def upsert_team(session: Session, club: ClubDetail) -> Team:
    """Insert or update the team master row from a ClubDetail."""
    if club.team_id is None:
        raise ValueError("ClubDetail.team_id is required to upsert a team")

    team = session.get(Team, club.team_id)
    if team is None:
        team = Team(team_id=club.team_id, name_ja=club.name_ja or "")
        session.add(team)

    # Overwrite with whatever non-empty values we have
    if club.name_ja:
        team.name_ja = club.name_ja
    if club.name_en is not None:
        team.name_en = club.name_en
    if club.arena is not None:
        team.arena = club.arena
    if club.address is not None:
        team.address = club.address
    if club.official_url is not None:
        team.official_url = club.official_url
    return team


def upsert_team_stub(session: Session, team_id: int, name_ja: str) -> Team:
    """Create or fetch a Team row with only id+name (used when a full
    ClubDetail is not yet available, e.g. when inserting a Game from
    a GameInfo that references team_ids we haven't scraped yet)."""
    team = session.get(Team, team_id)
    if team is None:
        team = Team(team_id=team_id, name_ja=name_ja)
        session.add(team)
    return team


# --- Player ----------------------------------------------------------------


def upsert_player(session: Session, detail: PlayerDetail) -> Player:
    """Insert or update the player master row from a PlayerDetail."""
    if detail.player_id is None:
        raise ValueError("PlayerDetail.player_id is required")

    player = session.get(Player, detail.player_id)
    if player is None:
        player = Player(player_id=detail.player_id, name_ja=detail.name_ja or "")
        session.add(player)

    if detail.name_ja:
        player.name_ja = detail.name_ja
    if detail.name_en is not None:
        player.name_en = detail.name_en
    if detail.birth_date is not None:
        player.birth_date = detail.birth_date
    if detail.height_cm is not None:
        player.height_cm = detail.height_cm
    if detail.weight_kg is not None:
        player.weight_kg = detail.weight_kg
    if detail.nationality is not None:
        player.nationality = detail.nationality
    if detail.hometown is not None:
        player.hometown = detail.hometown
    if detail.school is not None:
        player.school = detail.school
    return player


def upsert_player_stub(session: Session, player_id: int, name_ja: str) -> Player:
    """Minimum-info player row (name only). Later enriched by upsert_player
    once a full /roster_detail/ page is fetched."""
    player = session.get(Player, player_id)
    if player is None:
        player = Player(player_id=player_id, name_ja=name_ja)
        session.add(player)
    elif not player.name_ja and name_ja:
        player.name_ja = name_ja
    return player


# --- PlayerTeamHistory -----------------------------------------------------


def upsert_player_team_history(
    session: Session,
    player_id: int,
    team_id: int,
    season: str,
    jersey_number: int | None,
    positions: list[str] | None,
) -> PlayerTeamHistory:
    stmt = select(PlayerTeamHistory).where(
        PlayerTeamHistory.player_id == player_id,
        PlayerTeamHistory.season == season,
    )
    existing = session.scalar(stmt)
    if existing is None:
        existing = PlayerTeamHistory(
            player_id=player_id,
            season=season,
            team_id=team_id,
            jersey_number=jersey_number,
            positions=positions or [],
        )
        session.add(existing)
    else:
        existing.team_id = team_id
        if jersey_number is not None:
            existing.jersey_number = jersey_number
        if positions is not None:
            existing.positions = positions
    return existing


# --- TeamSeasonStat --------------------------------------------------------


def upsert_team_season_stat(
    session: Session, team_id: int, parsed: ParsedTeamSeasonStat
) -> TeamSeasonStat:
    stmt = select(TeamSeasonStat).where(
        TeamSeasonStat.team_id == team_id,
        TeamSeasonStat.season == parsed.season,
        TeamSeasonStat.game_type == parsed.game_type,
    )
    existing = session.scalar(stmt)
    fields = dict(
        wins=parsed.wins,
        losses=parsed.losses,
        ppg=parsed.ppg,
        opp_ppg=parsed.opp_ppg,
        fg_pct=parsed.fg_pct,
        three_fg_pct=parsed.three_fg_pct,
        ft_pct=parsed.ft_pct,
        rpg=parsed.rpg,
        apg=parsed.apg,
        topg=parsed.topg,
        spg=parsed.spg,
        bpg=parsed.bpg,
    )
    if existing is None:
        existing = TeamSeasonStat(
            team_id=team_id,
            season=parsed.season,
            game_type=parsed.game_type,
            **fields,
        )
        session.add(existing)
    else:
        for k, v in fields.items():
            setattr(existing, k, v)
    return existing


# --- RosterSeasonStat ------------------------------------------------------


def upsert_roster_season_stat(
    session: Session,
    player_id: int,
    team_id: int | None,
    entry: RosterEntry,
) -> RosterSeasonStat:
    stmt = select(RosterSeasonStat).where(
        RosterSeasonStat.player_id == player_id,
        RosterSeasonStat.season == entry.season,
        RosterSeasonStat.game_type == entry.game_type,
    )
    existing = session.scalar(stmt)
    fields = dict(
        team_id=team_id,
        games=entry.games,
        ppg=entry.ppg,
        fg_pct=entry.fg_pct,
        three_fg_pct=entry.three_fg_pct,
        ft_pct=entry.ft_pct,
        rpg=entry.rpg,
        apg=entry.apg,
        topg=entry.topg,
        spg=entry.spg,
        bpg=entry.bpg,
        eff=entry.eff,
    )
    if existing is None:
        existing = RosterSeasonStat(
            player_id=player_id,
            season=entry.season,
            game_type=entry.game_type,
            **fields,
        )
        session.add(existing)
    else:
        for k, v in fields.items():
            setattr(existing, k, v)
    return existing


# --- Game (from GameInfo) --------------------------------------------------


def _is_cs_competition(competition: str | None) -> bool:
    if not competition:
        return False
    return "チャンピオンシップ" in competition or "CS" in competition.upper()


def upsert_game_from_info(session: Session, info: GameInfo) -> Game:
    """Upsert a Game row using the richer GameInfo (team IDs are present)."""
    if not info.schedule_key:
        raise ValueError("GameInfo.schedule_key is required")
    if info.home_team_id is None or info.away_team_id is None:
        raise ValueError("GameInfo must carry both home_team_id and away_team_id")
    if info.home_team_id == info.away_team_id:
        raise ValueError("home_team_id and away_team_id must differ")

    is_cs = _is_cs_competition(info.competition)

    # Ensure referenced teams exist (stubs are fine at this stage).
    upsert_team_stub(session, info.home_team_id, info.home_name or "")
    upsert_team_stub(session, info.away_team_id, info.away_name or "")

    game = session.get(Game, info.schedule_key)
    if game is None:
        game = Game(
            schedule_key=info.schedule_key,
            season=info.season or "",
            competition=info.competition,
            game_date=info.date,
            tipoff=info.tipoff,
            home_team_id=info.home_team_id,
            away_team_id=info.away_team_id,
            is_cs=is_cs,
            is_final=not info.is_planned,
        )
        session.add(game)
    else:
        if info.season:
            game.season = info.season
        if info.competition is not None:
            game.competition = info.competition
        if info.date is not None:
            game.game_date = info.date
        if info.tipoff is not None:
            game.tipoff = info.tipoff
        game.home_team_id = info.home_team_id
        game.away_team_id = info.away_team_id
        game.is_cs = is_cs
        game.is_final = not info.is_planned
    return game


# --- Game (from ScheduledGame) --------------------------------------------


def upsert_game_from_schedule(
    session: Session,
    sg: ScheduledGame,
    *,
    season: str,
    home_team_id: int,
    away_team_id: int,
    game_date,
    competition: str | None = None,
) -> Game:
    """Upsert a Game row from a ScheduledGame.

    ScheduledGame lacks team IDs (the schedule page only uses 2-letter codes
    and display names), so the caller must resolve them upstream and pass
    ``home_team_id`` / ``away_team_id`` / ``game_date`` explicitly.
    """
    if not sg.schedule_key:
        raise ValueError("ScheduledGame.schedule_key is required")
    if home_team_id == away_team_id:
        raise ValueError("home_team_id and away_team_id must differ")

    is_cs = _is_cs_competition(competition)

    # Stub referenced teams in case they aren't in the DB yet.
    upsert_team_stub(session, home_team_id, sg.home_name)
    upsert_team_stub(session, away_team_id, sg.away_name)

    game = session.get(Game, sg.schedule_key)
    if game is None:
        game = Game(
            schedule_key=sg.schedule_key,
            season=season,
            competition=competition,
            section=sg.section,
            game_date=game_date,
            tipoff=sg.tipoff,
            venue=None,
            location=sg.location,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_score=sg.home_score,
            away_score=sg.away_score,
            is_cs=is_cs,
            is_final=sg.is_final,
        )
        session.add(game)
    else:
        game.season = season
        if competition is not None:
            game.competition = competition
        if sg.section is not None:
            game.section = sg.section
        if game_date is not None:
            game.game_date = game_date
        if sg.tipoff is not None:
            game.tipoff = sg.tipoff
        if sg.location is not None:
            game.location = sg.location
        game.home_team_id = home_team_id
        game.away_team_id = away_team_id
        game.home_score = sg.home_score
        game.away_score = sg.away_score
        game.is_cs = is_cs
        game.is_final = sg.is_final
    return game


# --- Composite: persist an entire ClubDetail -------------------------------


def persist_club_detail(session: Session, club: ClubDetail) -> Team:
    """Persist a whole ClubDetail page into the DB.

    Inserts/updates:
      - Team master
      - TeamSeasonStat rows (one per (season, game_type))
      - Player stubs (name only — enrich later via upsert_player)
      - PlayerTeamHistory rows (one per (player_id, season))
      - RosterSeasonStat rows
    """
    team = upsert_team(session, club)
    session.flush()
    assert club.team_id is not None, "team_id is None after upsert_team"

    for parsed in club.season_stats:
        upsert_team_season_stat(session, club.team_id, parsed)

    for entry in club.roster:
        upsert_player_stub(session, entry.player_id, entry.name)
        upsert_player_team_history(
            session,
            player_id=entry.player_id,
            team_id=club.team_id,
            season=entry.season,
            jersey_number=entry.jersey_number,
            positions=entry.positions,
        )
        upsert_roster_season_stat(
            session,
            player_id=entry.player_id,
            team_id=club.team_id,
            entry=entry,
        )

    session.flush()
    return team

"""Capa de servicio: de la API de la FPV a una lista de partidos de Alianza."""

from __future__ import annotations

from datetime import datetime, timedelta

from . import config, fpv, match as match_mod


def load_matches(now: datetime | None = None) -> list[tuple]:
    """Devuelve (partidos_futuros, partidos_terminados) de Alianza Lima.

    Los terminados se devuelven aparte porque no queremos crear avisos para
    partidos que ya pasaron, pero sí nos sirven para detectar cambios.
    """
    reference = now or datetime.now(config.PERU_TZ)
    after = (reference - timedelta(days=config.LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")

    teams = fpv.fetch_teams()
    venues = fpv.fetch_venues()
    leagues = fpv.fetch_leagues()
    events = fpv.fetch_events(after=after)

    horizon = reference + timedelta(days=config.LOOKAHEAD_DAYS)
    pending: list = []
    finished: list = []

    for event in events:
        # Filtro por ID de equipo, no por nombre. Ver match.involves_followed_team.
        if not match_mod.involves_followed_team(event):
            continue
        parsed = match_mod.match_from_event(event, teams, venues, leagues)
        if parsed is None:
            continue
        if parsed.start > horizon:
            continue
        if parsed.is_finished or parsed.end < reference:
            finished.append(parsed)
        else:
            pending.append(parsed)

    pending.sort(key=lambda m: m.start)
    finished.sort(key=lambda m: m.start)
    return pending, finished


def lookup_team_name(team_id: int) -> str | None:
    """Nombre oficial del equipo según la FPV (para verificar el ID)."""
    return fpv.fetch_teams().get(team_id)

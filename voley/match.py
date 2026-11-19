"""Modelo de un partido, y la lógica de "¿este partido es de Alianza?"."""

from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import config


@dataclass(frozen=True)
class Match:
    """Un partido ya normalizado y listo para meter al calendario."""

    fpv_id: int
    start: datetime            # con zona horaria (UTC-5 Perú)
    duration_min: int
    home: str
    away: str
    venue: str
    competition: str
    url: str
    is_finished: bool
    home_is_followed: bool = True   # True si Alianza es el equipo local

    # --- Datos derivados ---------------------------------------------------
    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.duration_min)

    @property
    def is_home(self) -> bool:
        """True si Alianza juega de local (aparece primero en la API)."""
        return self.home_is_followed

    @property
    def opponent(self) -> str:
        return self.away if self.is_home else self.home

    @property
    def summary(self) -> str:
        """Título del evento en el calendario."""
        return f"🏐 {self.home} vs {self.away} · {self.competition}"

    @property
    def description(self) -> str:
        lines = [
            f"{self.home} vs {self.away}",
            f"Competencia: {self.competition}",
            f"Sede: {self.venue or 'por confirmar'}",
            f"Inicio: {self.start.strftime('%d/%m/%Y %H:%M')} (hora Perú)",
        ]
        if self.is_finished:
            lines.append("Estado en la FPV: resultado publicado.")
        lines += [
            "",
            f"Ficha oficial: {self.url}",
            "",
            f"Generado automáticamente por {config.EVENT_SOURCE_TAG}",
        ]
        return "\n".join(lines)

    @property
    def fingerprint(self) -> str:
        """Huella del partido: cambia si la FPV reprograma fecha, hora o sede."""
        raw = f"{self.fpv_id}|{self.start.isoformat()}|{self.duration_min}|{self.home}|{self.away}|{self.venue}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @property
    def calendar_key(self) -> str:
        """ID estable para reconocer el evento dentro de Google Calendar."""
        return f"fpv-{self.fpv_id}"


def _clean(text: str) -> str:
    """La API devuelve entidades HTML (&#8211;, &amp;...). Las decodificamos."""
    return html.unescape(text).strip()


def display_name(raw: str) -> str:
    """Nombre corto y legible para el calendario."""
    name = _clean(raw)
    if name in config.NAME_ALIASES:
        return config.NAME_ALIASES[name]
    for prefix in config.STRIP_PREFIXES:
        if name.startswith(prefix) and len(name) > len(prefix) + 2:
            return name[len(prefix):]
    return name


def _parse_local(value: str) -> datetime:
    """Convierte '2026-11-22T18:30:46' en un datetime con zona de Perú.

    Le quitamos los segundos: en la FPV son basura de carga (18:30:46 para un
    partido de las 18:30), y arrastrarlos ensucia el calendario y los avisos.
    """
    clean = value.strip().replace(" ", "T")
    if clean.endswith("Z"):
        clean = clean[:-1]
    # Recortamos a minutos (YYYY-MM-DDTHH:MM)
    if len(clean) >= 16:
        clean = clean[:16]
    naive = datetime.strptime(clean, "%Y-%m-%dT%H:%M")
    return naive.replace(tzinfo=config.PERU_TZ)


def _duration(raw: object) -> int:
    """La FPV manda `minutes` como texto ('150'). Si viene raro, usamos default."""
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return config.DEFAULT_DURATION_MIN
    # Menos de 30 o más de 5 horas = dato raro, no confiamos.
    if not 30 <= value <= 300:
        return config.DEFAULT_DURATION_MIN
    return value


def match_from_event(
    event: dict,
    teams: dict[int, str],
    venues: dict[int, str],
    leagues: dict[int, str],
) -> Match | None:
    """Convierte un evento crudo de la FPV en un `Match`. None si no se puede."""
    team_ids = event.get("teams") or []
    if len(team_ids) < 2:
        return None
    home_id, away_id = int(team_ids[0]), int(team_ids[1])

    raw_date = event.get("date")
    if not raw_date:
        return None

    venue_ids = event.get("venues") or []
    league_ids = event.get("leagues") or []
    venue = venues.get(int(venue_ids[0]), "") if venue_ids else ""
    competition = leagues.get(int(league_ids[0]), "LNSV") if league_ids else "LNSV"

    return Match(
        fpv_id=int(event["id"]),
        start=_parse_local(raw_date),
        duration_min=_duration(event.get("minutes")),
        home=display_name(teams.get(home_id, f"Equipo {home_id}")),
        away=display_name(teams.get(away_id, f"Equipo {away_id}")),
        venue=venue,
        competition=competition,
        url=event.get("link", ""),
        is_finished=event.get("status") != "future",
        home_is_followed=home_id == config.TEAM_ID,
    )


def involves_followed_team(event: dict, team_id: int = config.TEAM_ID) -> bool:
    """¿El evento es de Club Alianza Lima?

    Comparamos el **ID** (138), no el nombre. Un filtro por texto como
    `"alianza" in nombre` también atraparía a "Deportivo Alianza" (1774),
    que es otro equipo y no lo quieres en tu calendario.
    """
    team_ids = event.get("teams") or []
    return any(int(tid) == team_id for tid in team_ids)


def upcoming(matches: list[Match], now: datetime | None = None) -> list[Match]:
    """Partidos que todavía no terminaron, ordenados por fecha."""
    reference = now or datetime.now(config.PERU_TZ)
    keep = [m for m in matches if m.end >= reference - timedelta(days=config.LOOKBACK_DAYS)]
    return sorted(keep, key=lambda m: m.start)

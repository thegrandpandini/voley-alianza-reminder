"""Cliente para la API pública de la FPV (WordPress + SportsPress).

Cosas que descubrimos probando la API en vivo (y que hay que respetar):

1. Los eventos viven en `/wp-json/sportspress/v2/events`.
2. El parámetro `?teams=` **se ignora en silencio**: pedir `?teams=138`
   devuelve TODOS los partidos (388 en la temporada 26/27). Por eso el
   filtro por equipo lo hacemos de nuestro lado.
3. `?leagues=` y `?after=` SÍ funcionan del lado del servidor.
4. `date` viene en hora local de Perú, sin zona horaria, y con segundos
   "basura" (ej. "2026-11-22T18:30:46" para un partido que empieza 18:30).
   Los segundos son un artefacto de cómo se carga el partido en el panel.
"""

from __future__ import annotations

import html
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

USER_AGENT = "voley-alianza-reminder/1.0 (+https://fpv.org.pe)"
MAX_RETRIES = 4


class FpvError(RuntimeError):
    """La FPV no respondió, o respondió algo que no entendemos."""


def _request_json(path: str, params: dict | None = None) -> tuple[list | dict, dict]:
    url = f"{config.FPV_BASE}/{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8")), dict(response.headers)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt == MAX_RETRIES:
                break
            time.sleep(2 ** (attempt - 1))  # 1s, 2s, 4s...

    raise FpvError(f"No se pudo leer {url}: {last_error}") from last_error


def _clean(text: str) -> str:
    """La API devuelve entidades HTML (&#8211;, &amp;...). Las decodificamos."""
    return html.unescape(text).strip()


def fetch_teams() -> dict[int, str]:
    """Mapa {id_equipo: nombre}, ej. {138: 'Club Alianza Lima'}."""
    teams: dict[int, str] = {}
    page = 1
    while True:
        batch, headers = _request_json("teams", {"per_page": 100, "page": page})
        if not isinstance(batch, list):
            raise FpvError(f"Respuesta inesperada de /teams en la página {page}")
        for team in batch:
            teams[int(team["id"])] = _clean(team["title"]["rendered"])

        if page >= int(headers.get("X-WP-TotalPages") or 1) or not batch:
            break
        page += 1
    return teams


def fetch_taxonomy(name: str) -> dict[int, str]:
    """Mapa {id: nombre} para 'venues', 'leagues' o 'seasons'."""
    items, _ = _request_json(name, {"per_page": 100})
    if not isinstance(items, list):
        raise FpvError(f"Respuesta inesperada de /{name}")
    return {
        int(item["id"]): _clean(item.get("name") or item["title"]["rendered"])
        for item in items
    }


def fetch_venues() -> dict[int, str]:
    """Mapa {id_sede: nombre}, ej. {13: 'Polideportivo Luisa Fuentes'}."""
    return fetch_taxonomy("venues")


def fetch_leagues() -> dict[int, str]:
    """Mapa {id_liga: nombre}, ej. {10: 'LNSV'}."""
    return fetch_taxonomy("leagues")


def fetch_events(after: str | None = None) -> list[dict]:
    """Trae los eventos crudos, paginando.

    `after` es un ISO en hora de Perú, ej. "2026-11-19T00:00:00".
    Ese filtro sí lo aplica el servidor.
    """
    events: list[dict] = []
    page = 1
    while True:
        params: dict[str, object] = {
            "per_page": 100,
            "page": page,
            "orderby": "date",
            "order": "asc",
        }
        if config.LEAGUE_ID:
            params["leagues"] = config.LEAGUE_ID
        if after:
            params["after"] = after

        batch, headers = _request_json("events", params)
        if not isinstance(batch, list):
            raise FpvError(f"Respuesta inesperada de /events en la página {page}")
        events.extend(batch)

        if page >= int(headers.get("X-WP-TotalPages") or 1) or not batch:
            break
        page += 1

    return events

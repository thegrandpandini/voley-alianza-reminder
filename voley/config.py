"""Configuración del recordatorio de partidos de Alianza Lima Vóley.

Todo se puede sobreescribir con variables de entorno, así el mismo código
funciona en tu PC y en GitHub Actions sin tocarlo.

Las variables vacías ("" o solo espacios) se tratan como "no definida". Eso
importa en GitHub Actions: si mapeas una *Variable* del repo que no existe,
llega como cadena vacía y `int("")` reventaría.
"""

from __future__ import annotations

import os
from datetime import timedelta, timezone


def _text(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _number(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        # Valor inválido: no rompemos el robot por una variable mal escrita.
        return default


def _minutes_list(name: str, default: str) -> list[int]:
    raw = _text(name, default)
    values: list[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            values.append(int(piece))
        except ValueError:
            continue
    return values or [1440, 60]


# --- Qué equipo seguimos -----------------------------------------------------
# OJO: usamos el ID del equipo en la FPV, NO el nombre.
#   "Club Alianza Lima" = 138   <- el nuestro
#   "Deportivo Alianza" = 1774  <- equipo DISTINTO, no confundir
# Filtrar por nombre ("alianza" in ...) metería partidos del equipo equivocado.
TEAM_ID = _number("VOLEY_TEAM_ID", 138)
TEAM_NAME = _text("VOLEY_TEAM_NAME", "Alianza Lima")

# --- Fuente de datos ---------------------------------------------------------
FPV_BASE = _text("VOLEY_FPV_BASE", "https://fpv.org.pe/wp-json/sportspress/v2")
FPV_SITE = "https://fpv.org.pe"

# Liga a seguir. 0 = TODAS las competiciones del equipo
# (LNSV + Sudamericano de Clubes + amistosos). 10 = sólo LNSV.
LEAGUE_ID = _number("VOLEY_LEAGUE_ID", 0)

# --- Zona horaria ------------------------------------------------------------
# Perú es UTC-5 todo el año (sin horario de verano desde 1994).
# Definimos el offset a mano para no depender del paquete `tzdata` en Windows.
TIMEZONE_NAME = "America/Lima"
PERU_TZ = timezone(timedelta(hours=-5), TIMEZONE_NAME)

# Zona horaria en la que se ESCRIBEN las horas legibles del evento (y del
# comando `check`). No afecta al momento del partido: los eventos se guardan en
# UTC, así que cada dispositivo los muestra en su propia hora.
#   "America/New_York" -> hora del Este de EE. UU. (con horario de verano)
#   "America/Lima"     -> hora de Perú
#   "UTC"              -> UTC
DISPLAY_TZ = _text("VOLEY_DISPLAY_TZ", "America/New_York")

# --- Calendario --------------------------------------------------------------
CALENDAR_ID = _text("VOLEY_CALENDAR_ID", "primary")

# Minutos antes del partido en que quieres que suene el aviso.
# 1440 = 1 día antes, 120 = 2 horas antes, 60 = 1 hora antes, 30 = media hora.
REMINDER_MINUTES = _minutes_list("VOLEY_REMINDERS", "1440,60")

# Duración por defecto si la FPV no la informa.
DEFAULT_DURATION_MIN = _number("VOLEY_DEFAULT_DURATION", 150)

# Cuántos días hacia atrás y hacia adelante mirar.
LOOKAHEAD_DAYS = _number("VOLEY_LOOKAHEAD_DAYS", 400)
LOOKBACK_DAYS = _number("VOLEY_LOOKBACK_DAYS", 0)

# Los partidos que ocupa el bloque en tu calendario (transparent = no bloquea).
EVENT_TRANSPARENCY = _text("VOLEY_TRANSPARENCY", "transparent")

# --- Archivos ----------------------------------------------------------------
CLIENT_SECRET_FILE = _text("VOLEY_CLIENT_SECRET", "client_secret.json")
TOKEN_FILE = _text("VOLEY_TOKEN_FILE", "token.json")
ICS_OUTPUT = _text("VOLEY_ICS_OUTPUT", "docs/alianza-lima.ics")

# Marca que ponemos en cada evento para reconocer los nuestros.
EVENT_SOURCE_TAG = "voley-alianza-reminder"

# Nombres cortos para que los títulos del calendario no queden kilométricos.
# La FPV usa "Club Alianza Lima"; en tu calendario se ve mejor "Alianza Lima".
NAME_ALIASES = {
    "Club Alianza Lima": "Alianza Lima",
    "WANKA Club Deportivo de Voleibol": "WANKA",
}
# Prefijos que se quitan si el equipo no está en NAME_ALIASES.
STRIP_PREFIXES = ("Club Deportivo ", "Club ", "Deportivo ")

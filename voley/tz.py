"""Zona horaria de *presentación* para los textos del calendario.

Contexto importante: los eventos NO se guardan en hora peruana ni en hora del
Este. Se guardan en UTC (una hora absoluta), así que cada dispositivo los
muestra en SU zona horaria. Esto sólo decide cómo se escribe la hora legible
dentro de la descripción del evento.

Windows no trae base de datos de zonas horarias, así que `zoneinfo` falla con
`ZoneInfoNotFoundError` en un Python limpio. Por eso:
  - si `zoneinfo` funciona (Linux, o Windows con el paquete tzdata), lo usamos;
  - si no, aplicamos las reglas de horario de verano de EE. UU. a mano.

Reglas de EE. UU. desde 2007 (las que rigen hoy):
  - el horario de verano empieza el 2.º domingo de marzo a las 02:00 EST
    (= 07:00 UTC),
  - termina el 1.er domingo de noviembre a las 02:00 EDT (= 06:00 UTC).
Perú no tiene horario de verano desde 1994: siempre UTC-5.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import config

LIMA = timezone(timedelta(hours=-5), "America/Lima")
EST = timezone(timedelta(hours=-5), "EST")
EDT = timezone(timedelta(hours=-4), "EDT")

_LABELS = {
    "America/Lima": "hora de Perú",
    "America/New_York": "hora del Este",
    "UTC": "UTC",
}


def _label(name: str) -> str:
    return _LABELS.get(name, f"hora de {name}")


def display_label() -> str:
    return _label(config.DISPLAY_TZ)


def _try_zoneinfo(name: str):
    """ZoneInfo si el sistema tiene tzdata; None si no."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        return None


def _nth_sunday(year: int, month: int, n: int) -> int:
    """Día del mes del n-ésimo domingo."""
    first = datetime(year, month, 1)
    # weekday(): lunes=0 ... domingo=6
    first_sunday = 1 + (6 - first.weekday()) % 7
    return first_sunday + 7 * (n - 1)


def _eastern_is_dst(moment_utc: datetime) -> bool:
    """¿Ese instante UTC cae en horario de verano del Este?"""
    year = moment_utc.year
    starts = datetime(year, 3, _nth_sunday(year, 3, 2), 7, 0, tzinfo=timezone.utc)
    ends = datetime(year, 11, _nth_sunday(year, 11, 1), 6, 0, tzinfo=timezone.utc)
    return starts <= moment_utc < ends


def to_eastern(moment: datetime) -> datetime:
    """Convierte a hora del Este (EST/EDT según la fecha)."""
    utc = moment.astimezone(timezone.utc)
    zone = _try_zoneinfo("America/New_York")
    if zone is not None:
        return utc.astimezone(zone)
    return utc.astimezone(EDT if _eastern_is_dst(utc) else EST)


def to_lima(moment: datetime) -> datetime:
    return moment.astimezone(LIMA)


def to_display(moment: datetime) -> datetime:
    """Hora en la zona configurada en VOLEY_DISPLAY_TZ."""
    name = config.DISPLAY_TZ
    if name == "UTC":
        return moment.astimezone(timezone.utc)
    if name == "America/Lima":
        return to_lima(moment)
    if name == "America/New_York":
        return to_eastern(moment)

    zone = _try_zoneinfo(name)
    if zone is not None:
        return moment.astimezone(zone)
    # Zona desconocida y sin tzdata: no inventamos, caemos a Lima.
    return to_lima(moment)


def describe_start(moment: datetime) -> str:
    """Texto legible: hora local del usuario y, si difiere, la de Lima."""
    shown = to_display(moment)
    text = f"{shown:%d/%m/%Y %H:%M} ({display_label()})"
    lima = to_lima(moment)
    if shown.utcoffset() != lima.utcoffset():
        text += f" · {lima:%H:%M} en Lima"
    return text


def describe_short(moment: datetime) -> str:
    """Versión corta para la terminal."""
    shown = to_display(moment)
    text = f"{shown:%a %d/%m/%Y %H:%M}"
    lima = to_lima(moment)
    if shown.utcoffset() != lima.utcoffset():
        text += f" ({lima:%H:%M} Lima)"
    return text

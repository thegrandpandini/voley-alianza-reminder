"""Genera un archivo .ics (iCalendar, RFC 5545) con los partidos de Alianza.

Este archivo sirve para:
  * abrirlo con Apple Calendar / Outlook -> avisos reales (VALARM),
  * importarlo a Google Calendar puntualmente,
  * publicarlo en GitHub Pages y suscribirte desde el teléfono,
  * revisar a mano qué se va a agendar (modo `preview`).

Usamos horas en UTC. Es más aburrido que TZID + VTIMEZONE, pero es
imposible que quede mal interpretado en otro país.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import config
from .match import Match

PRODID = "-//Voley Alianza Lima//Recordatorio FPV//ES"


def _utc(value: datetime) -> str:
    """datetime -> '20261122T233046Z'."""
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    """Escapa texto para un valor de iCalendar."""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return text


def _fold(line: str) -> str:
    """Parte líneas largas en trozos de 75 octetos (RFC 5545 §3.1).

    Se corta por caracteres, no por bytes, para no romper tildes ni emojis;
    por eso el límite real en bytes puede ser un poco mayor.
    """
    if len(line.encode("utf-8")) <= 75:
        return line
    chunks: list[str] = []
    current = ""
    for char in line:
        candidate = current + char
        if len(candidate.encode("utf-8")) > 72:
            chunks.append(current)
            current = " " + char          # la continuación empieza con un espacio
        else:
            current = candidate
    if current:
        chunks.append(current)
    return "\r\n".join(chunks)


def _alarms() -> list[str]:
    lines: list[str] = []
    for minutes in config.REMINDER_MINUTES:
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:Partido de {config.TEAM_NAME}",
            f"TRIGGER:-PT{minutes}M",
            "END:VALARM",
        ]
    return lines


def build_calendar(matches: list[Match], calendar_name: str = "Alianza Lima Vóley") -> str:
    """Devuelve el contenido completo del .ics."""
    stamp = _utc(datetime.now(timezone.utc))

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(calendar_name)}",
        "X-WR-TIMEZONE:America/Lima",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]

    for item in matches:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{item.calendar_key}@fpv.org.pe",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_utc(item.start)}",
            f"DTEND:{_utc(item.end)}",
            f"SUMMARY:{_escape(item.summary)}",
            f"DESCRIPTION:{_escape(item.description)}",
        ]
        if item.venue:
            lines.append(f"LOCATION:{_escape(item.venue)}")
        if item.url:
            lines.append(f"URL:{item.url}")
        lines += [
            "TRANSP:TRANSPARENT",
            "STATUS:CONFIRMED",
            "SEQUENCE:0",
            *_alarms(),
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def write_calendar(matches: list[Match], path: str | None = None) -> str:
    """Escribe el .ics y devuelve la ruta."""
    target = path or config.ICS_OUTPUT
    content = build_calendar(matches)
    from pathlib import Path

    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8", newline="")
    return str(destination)

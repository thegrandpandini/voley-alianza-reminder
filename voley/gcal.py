"""Cliente mínimo de Google Calendar (REST v3) usando solo la librería estándar.

Por qué no usamos `google-api-python-client`:
  - nos ahorramos `pip install` en tu PC y en GitHub Actions,
  - menos cosas que puedan romperse en el futuro,
  - para crear/actualizar eventos alcanza y sobra.

Los eventos se marcan con `extendedProperties.private`:
    source      = "voley-alianza-reminder"   -> reconoce nuestros eventos
    fpv_event_id = "11174"                   -> evita duplicados
    fingerprint  = "0bb580..."               -> detecta reprogramaciones

Así no dependemos de comparar títulos: si la FPV cambia la hora de un partido,
lo actualizamos en vez de crear un duplicado.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import auth, config
from .match import Match

API = "https://www.googleapis.com/calendar/v3"
MAX_RETRIES = 3


class CalendarError(RuntimeError):
    """Google Calendar devolvió un error que no pudimos resolver."""


def _payload(item: Match) -> dict:
    """Cuerpo JSON del evento para la API."""
    return {
        "summary": item.summary,
        "description": item.description,
        "location": item.venue or None,
        "start": {
            "dateTime": item.start.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": config.TIMEZONE_NAME,
        },
        "end": {
            "dateTime": item.end.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": config.TIMEZONE_NAME,
        },
        "transparency": config.EVENT_TRANSPARENCY,
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": minutes}
                for minutes in config.REMINDER_MINUTES
            ],
        },
        "source": {"title": "FPV - LNSV", "url": item.url or config.FPV_SITE},
        "extendedProperties": {
            "private": {
                "source": config.EVENT_SOURCE_TAG,
                "fpv_event_id": str(item.fpv_id),
                "fingerprint": item.fingerprint,
            }
        },
    }


class CalendarClient:
    def __init__(self, calendar_id: str | None = None) -> None:
        self.calendar_id = calendar_id or config.CALENDAR_ID

    # --- transporte --------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        url = f"{API}/calendars/{urllib.parse.quote(self.calendar_id, safe='')}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        data = json.dumps(body).encode("utf-8") if body is not None else None
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            request = urllib.request.Request(
                url,
                data=data,
                method=method,
                headers={
                    "Authorization": f"Bearer {auth.access_token()}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", "replace")
                # 429/5xx: vale la pena reintentar. 4xx: no.
                if error.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                    last_error = error
                    time.sleep(2 ** attempt)
                    continue
                raise CalendarError(
                    f"Google Calendar {method} {path} -> {error.code}: {detail}"
                ) from error
            except (urllib.error.URLError, TimeoutError) as error:
                last_error = error
                if attempt == MAX_RETRIES:
                    break
                time.sleep(2 ** attempt)

        raise CalendarError(f"Sin respuesta de Google Calendar: {last_error}") from last_error

    # --- operaciones -------------------------------------------------------
    def list_managed(self, time_min: str, time_max: str) -> dict[str, dict]:
        """Eventos creados por nosotros: {fpv_event_id: evento}."""
        events: dict[str, dict] = {}
        page_token: str | None = None

        while True:
            params = {
                "privateExtendedProperty": f"source={config.EVENT_SOURCE_TAG}",
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": 2500,
                "singleEvents": "false",
                "showDeleted": "false",
            }
            if page_token:
                params["pageToken"] = page_token

            response = self._request("GET", "/events", params=params)
            for event in response.get("items", []):
                private = (event.get("extendedProperties") or {}).get("private") or {}
                key = private.get("fpv_event_id")
                if key:
                    events[key] = event

            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return events

    def insert(self, item: Match) -> dict:
        return self._request("POST", "/events", body=_payload(item))

    def patch(self, event_id: str, item: Match) -> dict:
        return self._request("PATCH", f"/events/{event_id}", body=_payload(item))

    def delete(self, event_id: str) -> None:
        self._request("DELETE", f"/events/{event_id}")

    def calendar_summary(self) -> str:
        info = self._request("GET", "")
        return info.get("summary", info.get("id", "?"))


def sync(
    matches: list[Match],
    dry_run: bool = False,
    prune: bool = False,
    time_min: str | None = None,
    time_max: str | None = None,
) -> dict:
    """Crea/actualiza los partidos en el calendario. Devuelve un resumen."""
    client = CalendarClient()
    report: dict = {
        "created": [],
        "updated": [],
        "unchanged": [],
        "pruned": [],
        "errors": [],
        "calendar": "?",
    }

    if dry_run:
        report["calendar"] = f"{config.CALENDAR_ID} (simulación)"
        report["created"] = [m.summary for m in matches]
        return report

    report["calendar"] = client.calendar_summary()
    existing = client.list_managed(
        time_min or "2000-01-01T00:00:00Z",
        time_max or "2100-01-01T00:00:00Z",
    )

    wanted: set[str] = set()
    for item in matches:
        key = str(item.fpv_id)
        wanted.add(key)
        try:
            current = existing.get(key)
            if current is None:
                client.insert(item)
                report["created"].append(item.summary)
                continue

            stored = (current.get("extendedProperties") or {}).get("private") or {}
            if stored.get("fingerprint") != item.fingerprint:
                client.patch(current["id"], item)
                report["updated"].append(item.summary)
            else:
                report["unchanged"].append(item.summary)
        except CalendarError as error:
            report["errors"].append(f"{item.summary}: {error}")

    if prune:
        for key, event in existing.items():
            if key in wanted:
                continue
            try:
                client.delete(event["id"])
                report["pruned"].append(event.get("summary", key))
            except CalendarError as error:
                report["errors"].append(f"borrar {key}: {error}")

    return report

"""Guarda respuestas reales de la API como fixture para los tests.

Se corre a mano cuando queremos refrescar el fixture:
    python tests/capture_fixture.py
"""

import json
import urllib.request
from pathlib import Path

BASE = "https://fpv.org.pe/wp-json/sportspress/v2"
HEADERS = {"User-Agent": "voley-alianza-reminder/1.0"}
OUT = Path(__file__).parent / "fixtures"


def get(path, params):
    import urllib.parse

    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def slim_event(event: dict) -> dict:
    """Deja solo los campos que usamos (la respuesta real trae 25 KB de Yoast)."""
    return {
        "id": event["id"],
        "date": event["date"],
        "slug": event.get("slug"),
        "status": event.get("status"),
        "link": event.get("link"),
        "title": {"rendered": event["title"]["rendered"]},
        "teams": event.get("teams"),
        "venues": event.get("venues"),
        "leagues": event.get("leagues"),
        "seasons": event.get("seasons"),
        "minutes": event.get("minutes"),
    }


def slim_term(term: dict) -> dict:
    return {
        "id": term["id"],
        "name": term.get("name") or term["title"]["rendered"],
        "slug": term.get("slug"),
        "abbreviation": term.get("abbreviation"),
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)

    # Todos los eventos de la liga; nos quedamos con algunos de Alianza y otros.
    events = get("events", {"per_page": 100, "orderby": "date", "order": "desc"})
    keep = [slim_event(e) for e in events if 138 in (e.get("teams") or [])][-4:]
    others = [slim_event(e) for e in events if 138 not in (e.get("teams") or [])][-2:]
    (OUT / "events.json").write_text(
        json.dumps(keep + others, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    for name in ("teams", "venues", "leagues"):
        terms = get(name, {"per_page": 100})
        (OUT / f"{name}.json").write_text(
            json.dumps([slim_term(t) for t in terms], indent=1, ensure_ascii=False),
            encoding="utf-8",
        )

    print(f"Fixture guardado en {OUT}: {len(keep)} eventos de Alianza + {len(others)} otros")


if __name__ == "__main__":
    main()

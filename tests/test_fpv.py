"""Tests del cliente HTTP: que no repitamos el error de confiar en `?teams=`."""

import io
import json
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

from voley import fpv

FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"


def fake_response(payload, headers=None):
    raw = json.dumps(payload).encode("utf-8")
    response = mock.MagicMock()
    response.read.return_value = raw
    response.headers = headers or {}
    response.__enter__ = lambda self: self
    response.__exit__ = lambda *args: False
    return response


class TestEventQuery(unittest.TestCase):
    def _captured_url(self) -> str:
        with mock.patch("voley.fpv.urllib.request.urlopen") as opener:
            opener.return_value = fake_response([], {"X-WP-TotalPages": "1"})
            fpv.fetch_events(after="2026-11-19T00:00:00")
            return opener.call_args[0][0].full_url

    def test_does_not_ask_server_to_filter_by_team(self):
        """`?teams=` se ignora del lado del servidor: pedirlo daría falsa confianza."""
        query = parse_qs(urlparse(self._captured_url()).query)
        self.assertNotIn("teams", query)

    def test_sends_working_filters(self):
        query = parse_qs(urlparse(self._captured_url()).query)
        self.assertEqual(query["after"], ["2026-11-19T00:00:00"])
        self.assertEqual(query["per_page"], ["100"])
        self.assertEqual(query["orderby"], ["date"])

    def test_paginates_until_last_page(self):
        pages = [
            fake_response([{"id": 1}], {"X-WP-TotalPages": "2"}),
            fake_response([{"id": 2}], {"X-WP-TotalPages": "2"}),
        ]
        with mock.patch("voley.fpv.urllib.request.urlopen", side_effect=pages) as opener:
            events = fpv.fetch_events()
        self.assertEqual([e["id"] for e in events], [1, 2])
        self.assertEqual(opener.call_count, 2)


class TestTeams(unittest.TestCase):
    def test_returns_id_to_name_map(self):
        payload = [
            {"id": 138, "title": {"rendered": "Club Alianza Lima"}},
            {"id": 1774, "title": {"rendered": "Deportivo Alianza"}},
        ]
        with mock.patch("voley.fpv.urllib.request.urlopen") as opener:
            opener.return_value = fake_response(payload, {"X-WP-TotalPages": "1"})
            teams = fpv.fetch_teams()
        self.assertEqual(teams[138], "Club Alianza Lima")
        self.assertEqual(teams[1774], "Deportivo Alianza")
        self.assertEqual(len(teams), 2)

    def test_decodes_html_entities(self):
        payload = [{"id": 1, "title": {"rendered": "Rebaza Acosta &#8211; Olva"}}]
        with mock.patch("voley.fpv.urllib.request.urlopen") as opener:
            opener.return_value = fake_response(payload, {"X-WP-TotalPages": "1"})
            teams = fpv.fetch_teams()
        self.assertEqual(teams[1], "Rebaza Acosta – Olva")


class TestErrors(unittest.TestCase):
    def test_gives_up_after_retries(self):
        with mock.patch("voley.fpv.urllib.request.urlopen",
                        side_effect=TimeoutError("boom")) as opener:
            with mock.patch("voley.fpv.time.sleep"):  # no esperar de verdad
                with self.assertRaises(fpv.FpvError):
                    fpv.fetch_events()
        self.assertEqual(opener.call_count, fpv.MAX_RETRIES)


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from datetime import timezone
from pathlib import Path

from voley import config, match as M

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class TestParsing(unittest.TestCase):
    def test_seconds_are_discarded(self):
        """La FPV manda '18:30:46' para un partido de las 18:30."""
        parsed = M._parse_local("2026-11-22T18:30:46")
        self.assertEqual((parsed.hour, parsed.minute, parsed.second), (18, 30, 0))

    def test_local_time_uses_peru_offset(self):
        parsed = M._parse_local("2026-11-22T18:30:00")
        self.assertEqual(parsed.utcoffset().total_seconds(), -5 * 3600)
        self.assertEqual(parsed.tzname(), "America/Lima")

    def test_duration_falls_back_on_junk(self):
        self.assertEqual(M._duration("150"), 150)
        self.assertEqual(M._duration("67"), 67)
        self.assertEqual(M._duration("0"), config.DEFAULT_DURATION_MIN)
        self.assertEqual(M._duration(None), config.DEFAULT_DURATION_MIN)
        self.assertEqual(M._duration("9999"), config.DEFAULT_DURATION_MIN)

    def test_display_name(self):
        self.assertEqual(M.display_name("Club Alianza Lima"), "Alianza Lima")
        self.assertEqual(M.display_name("WANKA Club Deportivo de Voleibol"), "WANKA")
        self.assertEqual(M.display_name("Club Atlético Atenea"), "Atlético Atenea")
        self.assertEqual(M.display_name("Perú U-19"), "Perú U-19")


class TestTeamFilter(unittest.TestCase):
    """El bug que este proyecto evita: 'alianza' también matchea Deportivo Alianza."""

    def test_real_team_is_included(self):
        self.assertTrue(M.involves_followed_team({"teams": [138, 1620]}))

    def test_deportivo_alianza_is_not_the_same_team(self):
        # ID 1774 = "Deportivo Alianza", un equipo distinto.
        self.assertFalse(M.involves_followed_team({"teams": [1774, 1620]}))

    def test_name_based_filter_would_have_been_wrong(self):
        """Documenta por qué NO filtramos por nombre."""
        event = {"teams": [1774, 1625]}
        teams = {1774: "Deportivo Alianza", 1625: "Regatas Lima"}
        text = " ".join(teams[i] for i in event["teams"]).lower()
        self.assertIn("alianza", text)                       # el filtro ingenuo lo acepta
        self.assertFalse(M.involves_followed_team(event))     # el correcto lo rechaza

    def test_missing_teams_key(self):
        self.assertFalse(M.involves_followed_team({}))


class TestMatchFromEvent(unittest.TestCase):
    def setUp(self):
        self.teams = {t["id"]: t["name"] for t in load("teams.json")}
        self.venues = {v["id"]: v["name"] for v in load("venues.json")}
        self.leagues = {l["id"]: l["name"] for l in load("leagues.json")}
        self.events = load("events.json")
        self.alianza = [e for e in self.events if 138 in e["teams"]][0]

    def test_builds_match(self):
        item = M.match_from_event(self.alianza, self.teams, self.venues, self.leagues)
        self.assertIsNotNone(item)
        self.assertEqual(item.fpv_id, self.alianza["id"])
        self.assertTrue(item.is_home)
        self.assertIn("Alianza Lima", item.summary)
        self.assertEqual(item.end - item.start, __import__("datetime").timedelta(minutes=150))

    def test_title_is_readable(self):
        item = M.match_from_event(self.alianza, self.teams, self.venues, self.leagues)
        self.assertIn("🏐", item.summary)
        self.assertIn("Alianza Lima", item.summary)
        self.assertNotIn("&#8211;", item.summary)

    def test_event_without_two_teams_is_skipped(self):
        self.assertIsNone(M.match_from_event({"id": 1, "teams": [138]},
                                             self.teams, self.venues, self.leagues))

    def test_fingerprint_is_stable_and_sensitive(self):
        first = M.match_from_event(self.alianza, self.teams, self.venues, self.leagues)
        again = M.match_from_event(self.alianza, self.teams, self.venues, self.leagues)
        self.assertEqual(first.fingerprint, again.fingerprint)

        moved = dict(self.alianza)
        moved["date"] = "2026-11-23T19:00:00"
        changed = M.match_from_event(moved, self.teams, self.venues, self.leagues)
        self.assertNotEqual(first.fingerprint, changed.fingerprint)

    def test_description_has_official_link(self):
        item = M.match_from_event(self.alianza, self.teams, self.venues, self.leagues)
        self.assertIn(self.alianza["link"], item.description)


class TestUpcoming(unittest.TestCase):
    def test_filters_finished_matches(self):
        from datetime import datetime, timedelta

        reference = datetime(2026, 11, 19, 12, 0, tzinfo=timezone(timedelta(hours=-5)))
        past = M.Match(1, reference - timedelta(days=5), 150, "Alianza Lima", "X",
                       "", "LNSV", "", is_finished=True)
        future = M.Match(2, reference + timedelta(days=3), 150, "Alianza Lima", "Y",
                         "", "LNSV", "", is_finished=False)
        result = M.upcoming([past, future], now=reference)
        self.assertEqual([m.fpv_id for m in result], [2])


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timedelta

from voley import config, ics
from voley.match import Match

PERU = config.PERU_TZ


def sample(**overrides) -> Match:
    base = dict(
        fpv_id=11174,
        start=datetime(2026, 11, 22, 18, 30, tzinfo=PERU),
        duration_min=150,
        home="Alianza Lima",
        away="Atlético Atenea",
        venue="Polideportivo Luisa Fuentes",
        competition="LNSV",
        url="https://fpv.org.pe/event/x/",
        is_finished=False,
    )
    base.update(overrides)
    return Match(**base)


def unfold(text: str) -> list[str]:
    """Deshace el plegado de líneas del RFC 5545."""
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


class TestIcs(unittest.TestCase):
    def setUp(self):
        self.matches = [sample()]
        self.text = ics.build_calendar(self.matches)
        self.lines = unfold(self.text)

    def test_envelope(self):
        self.assertTrue(self.text.startswith("BEGIN:VCALENDAR"))
        self.assertTrue(self.text.rstrip().endswith("END:VCALENDAR"))
        self.assertIn("VERSION:2.0", self.lines)
        self.assertIn("PRODID:-//Voley Alianza Lima//Recordatorio FPV//ES", self.lines)

    def test_uses_crlf(self):
        self.assertIn("\r\n", self.text)

    def test_times_are_utc(self):
        """18:30 en Lima (UTC-5) tiene que ser 23:30Z."""
        self.assertIn("DTSTART:20261122T233000Z", self.lines)
        self.assertIn("DTEND:20261123T020000Z", self.lines)

    def test_one_alarm_per_configured_reminder(self):
        alarms = [line for line in self.lines if line.startswith("TRIGGER:")]
        self.assertEqual(len(alarms), len(config.REMINDER_MINUTES))
        for minutes in config.REMINDER_MINUTES:
            self.assertIn(f"TRIGGER:-PT{minutes}M", alarms)

    def test_uid_is_deterministic(self):
        self.assertIn("UID:fpv-11174@fpv.org.pe", self.lines)

    def test_escaping(self):
        tricky = sample(venue="Coliseo A, B; C")
        lines = unfold(ics.build_calendar([tricky]))
        location = [line for line in lines if line.startswith("LOCATION:")][0]
        self.assertIn("\\,", location)
        self.assertIn("\\;", location)

    def test_lines_respect_75_octets(self):
        for line in self.text.split("\r\n"):
            if line:
                self.assertLessEqual(
                    len(line.encode("utf-8")), 75,
                    msg=f"línea demasiado larga: {line[:40]!r}",
                )

    def test_newlines_inside_description_are_escaped(self):
        self.assertIn("\\n", self.text)
        # No debe haber saltos de línea crudos dentro de un valor
        desc = [line for line in self.lines if line.startswith("DESCRIPTION:")][0]
        self.assertNotIn("\n", desc)

    def test_multiple_matches(self):
        second = sample(fpv_id=2, start=datetime(2026, 11, 28, 17, 0, tzinfo=PERU))
        text = ics.build_calendar([sample(), second])
        self.assertEqual(text.count("BEGIN:VEVENT"), 2)
        self.assertEqual(text.count("END:VEVENT"), 2)

    def test_empty_calendar_is_valid(self):
        text = ics.build_calendar([])
        self.assertIn("BEGIN:VCALENDAR", text)
        self.assertIn("END:VCALENDAR", text)
        self.assertNotIn("BEGIN:VEVENT", text)


if __name__ == "__main__":
    unittest.main()

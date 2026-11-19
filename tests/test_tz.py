"""Tests de la zona horaria de presentación (hora del Este con horario de verano).

Windows no trae tzdata, así que estas reglas las aplicamos a mano. Aquí se
verifica contra casos conocidos, incluidos los dos cambios de hora, que es
donde es fácil equivocarse por una hora.
"""

import unittest
from datetime import datetime, timedelta, timezone

from voley import config, tz


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


class TestEasternOffset(unittest.TestCase):
    def test_winter_is_utc_minus_5(self):
        # 22 nov 2026: EN INVIERNO Lima y Nueva York coinciden (ambas UTC-5).
        moment = utc(2026, 11, 22, 23, 30)
        self.assertEqual(tz.to_eastern(moment).utcoffset(), timedelta(hours=-5))

    def test_summer_is_utc_minus_4(self):
        # Julio: Nueva York está en horario de verano (UTC-4), Lima sigue en -5.
        moment = utc(2026, 7, 15, 23, 30)
        self.assertEqual(tz.to_eastern(moment).utcoffset(), timedelta(hours=-4))

    def test_one_hour_gap_in_summer(self):
        moment = utc(2026, 7, 15, 23, 30)          # 18:30 en Lima
        self.assertEqual(tz.to_lima(moment).hour, 18)
        self.assertEqual(tz.to_eastern(moment).hour, 19)   # 19:30 del Este

    def test_no_gap_in_november(self):
        moment = utc(2026, 11, 22, 23, 30)
        self.assertEqual(tz.to_lima(moment).hour, 18)
        self.assertEqual(tz.to_eastern(moment).hour, 18)

    def test_lima_never_changes(self):
        for month in range(1, 13):
            moment = utc(2027, month, 15, 12, 0)
            self.assertEqual(tz.to_lima(moment).utcoffset(), timedelta(hours=-5))


class TestDaylightSavingTransitions(unittest.TestCase):
    """2027: empieza el 14 de marzo, termina el 7 de noviembre."""

    def test_just_before_spring_forward(self):
        # 14 mar 2027, 06:59 UTC = 01:59 EST -> todavía horario estándar.
        self.assertFalse(tz._eastern_is_dst(utc(2027, 3, 14, 6, 59)))

    def test_at_spring_forward(self):
        # 07:00 UTC = 02:00 EST -> salta a las 03:00 EDT.
        self.assertTrue(tz._eastern_is_dst(utc(2027, 3, 14, 7, 0)))

    def test_just_before_fall_back(self):
        # 7 nov 2027, 05:59 UTC = 01:59 EDT -> todavía horario de verano.
        self.assertTrue(tz._eastern_is_dst(utc(2027, 11, 7, 5, 59)))

    def test_at_fall_back(self):
        # 06:00 UTC = 02:00 EDT -> vuelve a las 01:00 EST.
        self.assertFalse(tz._eastern_is_dst(utc(2027, 11, 7, 6, 0)))

    def test_2026_dates(self):
        # 2026: empieza el 8 de marzo, termina el 1 de noviembre.
        self.assertTrue(tz._eastern_is_dst(utc(2026, 3, 8, 7, 0)))
        self.assertFalse(tz._eastern_is_dst(utc(2026, 3, 8, 6, 59)))
        self.assertTrue(tz._eastern_is_dst(utc(2026, 11, 1, 5, 59)))
        self.assertFalse(tz._eastern_is_dst(utc(2026, 11, 1, 6, 0)))

    def test_nth_sunday(self):
        self.assertEqual(tz._nth_sunday(2026, 3, 2), 8)
        self.assertEqual(tz._nth_sunday(2026, 11, 1), 1)
        self.assertEqual(tz._nth_sunday(2027, 3, 2), 14)
        self.assertEqual(tz._nth_sunday(2027, 11, 1), 7)


class TestDescriptions(unittest.TestCase):
    def tearDown(self):
        config.DISPLAY_TZ = "America/New_York"

    def test_summer_mentions_both(self):
        config.DISPLAY_TZ = "America/New_York"
        text = tz.describe_start(utc(2026, 7, 15, 23, 30))
        self.assertIn("hora del Este", text)
        self.assertIn("19:30", text)
        self.assertIn("18:30 en Lima", text)

    def test_november_does_not_repeat_the_same_hour(self):
        config.DISPLAY_TZ = "America/New_York"
        text = tz.describe_start(utc(2026, 11, 22, 23, 30))
        self.assertIn("hora del Este", text)
        self.assertIn("18:30", text)
        self.assertNotIn("en Lima", text)   # coinciden: no vale la pena repetir

    def test_switch_to_lima(self):
        config.DISPLAY_TZ = "America/Lima"
        text = tz.describe_start(utc(2026, 11, 22, 23, 30))
        self.assertIn("hora de Perú", text)

    def test_switch_to_utc(self):
        config.DISPLAY_TZ = "UTC"
        text = tz.describe_start(utc(2026, 11, 22, 23, 30))
        self.assertIn("23:30", text)


class TestMatchDescriptionUsesDisplayZone(unittest.TestCase):
    def tearDown(self):
        config.DISPLAY_TZ = "America/New_York"

    def test_description_reports_eastern(self):
        from voley.match import Match

        config.DISPLAY_TZ = "America/New_York"
        item = Match(
            fpv_id=1,
            start=datetime(2026, 7, 15, 18, 30, tzinfo=config.PERU_TZ),
            duration_min=150,
            home="Alianza Lima",
            away="Regatas",
            venue="Coliseo",
            competition="LNSV",
            url="https://fpv.org.pe/event/x/",
            is_finished=False,
        )
        self.assertIn("19:30", item.description)
        self.assertIn("hora del Este", item.description)


if __name__ == "__main__":
    unittest.main()

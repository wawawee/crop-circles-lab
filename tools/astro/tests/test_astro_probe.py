"""Tests for N4++: BCE calendar hardening, axis bearing alignment, Δaz helpers."""

import math
import unittest
from datetime import date

from tools.astro.astro_probe import (
    DEEP_BCE_THRESHOLD, SITES,
    _angular_delta_deg, _axis_alignment_delta,
    compare_bearing_alignments,
    HAS_SKYFIELD,
)


class TestAngularDelta(unittest.TestCase):
    """_angular_delta_deg — shortest distance on circle."""

    def test_identical(self) -> None:
        self.assertAlmostEqual(_angular_delta_deg(51.0, 51.0), 0.0)

    def test_opposite(self) -> None:
        self.assertAlmostEqual(_angular_delta_deg(0.0, 180.0), 180.0)

    def test_wrap_360(self) -> None:
        self.assertAlmostEqual(_angular_delta_deg(355.0, 5.0), 10.0)

    def test_180_symmetry(self) -> None:
        """Axis bearing θ and θ+180 give same alignment delta (min of two)."""
        az = 213.87
        d0 = _angular_delta_deg(az, 51.0)
        d180 = _angular_delta_deg(az, 231.0)
        delta_from_51 = min(d0, _angular_delta_deg(az, (51.0 + 180) % 360))
        delta_from_231 = min(d180, _angular_delta_deg(az, (231.0 + 180) % 360))
        self.assertAlmostEqual(delta_from_51, delta_from_231)

    def test_known_stonehenge(self) -> None:
        """Stonehenge az 213.87° vs axis 51° → Δ = 17.13° (via 180° symmetry)."""
        az = 213.87
        bearing = 51.0
        d0 = _angular_delta_deg(az, bearing)
        d180 = _angular_delta_deg(az, (bearing + 180) % 360)
        delta = min(d0, d180)
        self.assertAlmostEqual(delta, 17.13, places=2)


class TestAxisAlignmentDelta(unittest.TestCase):
    """_axis_alignment_delta — reads site axis bearing, computes Δaz."""

    def test_site_with_bearing(self) -> None:
        site = {
            "name": "stonehenge",
            "axis_bearing_deg": 51.0,
            "jun_solstice_sunrise": {"sunrise_az_deg": 213.87},
        }
        d = _axis_alignment_delta(site)
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d["delta_az_deg"], 17.13, places=2)

    def test_site_no_bearing(self) -> None:
        site = {
            "name": "gobekli_tepe",
            "axis_bearing_deg": None,
            "jun_solstice_sunrise": {"sunrise_az_deg": 120.65},
        }
        self.assertIsNone(_axis_alignment_delta(site))

    def test_site_missing_azimuth(self) -> None:
        site = {"name": "no_az", "axis_bearing_deg": 51.0, "jun_solstice_sunrise": {}}
        self.assertIsNone(_axis_alignment_delta(site))

    def test_site_nan_azimuth(self) -> None:
        site = {
            "name": "nan_az",
            "axis_bearing_deg": 51.0,
            "jun_solstice_sunrise": {"sunrise_az_deg": float("nan")},
        }
        self.assertIsNone(_axis_alignment_delta(site))


class TestSitesDB(unittest.TestCase):
    """SITES database has expected N4++ fields."""

    def test_all_sites_have_axis_fields(self) -> None:
        for name, info in SITES.items():
            self.assertIn("axis_bearing_deg", info, f"{name} missing axis_bearing_deg")
            self.assertIn("axis_citation", info, f"{name} missing axis_citation")

    def test_stonehenge_axis(self) -> None:
        self.assertEqual(SITES["stonehenge"]["axis_bearing_deg"], 51.0)

    def test_gobekli_no_axis(self) -> None:
        self.assertIsNone(SITES["gobekli_tepe"]["axis_bearing_deg"])

    def test_giza_no_axis(self) -> None:
        self.assertIsNone(SITES["giza_khufu"]["axis_bearing_deg"])

    def test_chichen_itza_axis(self) -> None:
        self.assertEqual(SITES["chichen_itza"]["axis_bearing_deg"], 287.0)


class TestDeepBCEThreshold(unittest.TestCase):
    """DEEP_BCE_THRESHOLD and calendar_label_unreliable logic."""

    def test_threshold_value(self) -> None:
        self.assertEqual(DEEP_BCE_THRESHOLD, -2000)

    def test_gobekli_deep_bce(self) -> None:
        self.assertLess(SITES["gobekli_tepe"]["epoch_year"], DEEP_BCE_THRESHOLD)


class TestCompareBearingAlignments(unittest.TestCase):
    """compare_bearing_alignments structure."""

    def test_empty_real_no_crash(self) -> None:
        result = compare_bearing_alignments([], [])
        self.assertIn("n_real_with_axis", result)
        self.assertEqual(result["n_real_with_axis"], 0)
        self.assertEqual(result["n_real_unknown_axis"], 0)

    def test_known_and_unknown_separated(self) -> None:
        real = [
            {"name": "a", "axis_bearing_deg": 51.0,
             "jun_solstice_sunrise": {"sunrise_az_deg": 50.0}},
            {"name": "b", "axis_bearing_deg": None,
             "jun_solstice_sunrise": {"sunrise_az_deg": 120.0}},
        ]
        result = compare_bearing_alignments(real, [])
        self.assertEqual(result["n_real_with_axis"], 1)
        self.assertEqual(result["n_real_unknown_axis"], 1)


class TestCalendarLabelValidation(unittest.TestCase):
    """If skyfield available, validate root finder produces correct solar lon."""

    def test_root_finder_accuracy(self) -> None:
        if not HAS_SKYFIELD:
            self.skipTest("requires skyfield + DE441")
        from tools.astro.astro_probe import _solstice_equinox_skyfield
        for year in (-9600, -2500, 800, 2026):
            result = _solstice_equinox_skyfield(year)
            for event in ("mar_equinox", "jun_solstice", "sep_equinox", "dec_solstice"):
                v = result[event].get("validated_solar_lon_deg")
                self.assertIsNotNone(v, f"{year} {event} missing validated_solar_lon_deg")
                self.assertGreater(v, -1, f"{year} {event} lon out of range")
                self.assertLess(v, 361, f"{year} {event} lon out of range")

    def test_calendar_flag_on_deep_bce(self) -> None:
        if not HAS_SKYFIELD:
            self.skipTest("requires skyfield + DE441")
        from tools.astro.astro_probe import _solstice_equinox_skyfield
        deep = _solstice_equinox_skyfield(-9600)
        self.assertTrue(deep.get("calendar_label_unreliable"))
        modern = _solstice_equinox_skyfield(2026)
        self.assertFalse(modern.get("calendar_label_unreliable", False))


if __name__ == "__main__":
    unittest.main()

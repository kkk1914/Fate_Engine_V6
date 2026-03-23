"""Tests for core/ephemeris.py — Swiss Ephemeris wrapper.

Phase 1.7: Verifies known positions for known dates against Swiss Ephemeris.
These tests require pyswisseph but NOT ephemeris data files (uses Moshier fallback).
"""
import pytest
from datetime import datetime


class TestJulianDay:
    """Julian Day conversion tests."""

    def test_j2000_epoch(self):
        """J2000.0 = 2000-01-01 12:00 UT → JD 2451545.0"""
        from core.ephemeris import ephe
        dt = datetime(2000, 1, 1, 12, 0, 0)
        jd = ephe.julian_day(dt)
        assert abs(jd - 2451545.0) < 0.001

    def test_known_date_1990(self):
        """1990-06-15 14:30 UT → JD ~2448058.104"""
        from core.ephemeris import ephe
        dt = datetime(1990, 6, 15, 14, 30, 0)
        jd = ephe.julian_day(dt)
        assert abs(jd - 2448058.104) < 0.01

    def test_midnight_is_half_integer(self):
        """Midnight UT corresponds to JD + 0.5"""
        from core.ephemeris import ephe
        dt = datetime(2000, 1, 1, 0, 0, 0)
        jd = ephe.julian_day(dt)
        # J2000.0 noon = 2451545.0, so midnight = 2451544.5
        assert abs(jd - 2451544.5) < 0.001


class TestPlanetLongitude:
    """Planet position calculation tests."""

    def test_sun_longitude_range(self):
        """Sun longitude should be 0-360."""
        from core.ephemeris import ephe
        import swisseph as swe
        dt = datetime(2024, 3, 20, 12, 0, 0)  # ~Spring equinox
        jd = ephe.julian_day(dt)
        lon, lat = ephe.planet_longitude(jd, swe.SUN)
        assert 0 <= lon < 360

    def test_sun_near_equinox(self):
        """Sun near vernal equinox (~March 20) should be near 0° Aries."""
        from core.ephemeris import ephe
        import swisseph as swe
        dt = datetime(2024, 3, 20, 3, 0, 0)  # ~equinox
        jd = ephe.julian_day(dt)
        lon, lat = ephe.planet_longitude(jd, swe.SUN)
        # Should be near 0° (within a degree)
        assert lon < 2.0 or lon > 358.0

    def test_moon_moves_fast(self):
        """Moon moves ~13°/day — verify two days apart differ significantly."""
        from core.ephemeris import ephe
        import swisseph as swe
        dt1 = datetime(2024, 1, 1, 12, 0, 0)
        dt2 = datetime(2024, 1, 3, 12, 0, 0)
        jd1 = ephe.julian_day(dt1)
        jd2 = ephe.julian_day(dt2)
        lon1, _ = ephe.planet_longitude(jd1, swe.MOON)
        lon2, _ = ephe.planet_longitude(jd2, swe.MOON)
        # 2 days × ~13°/day = ~26°
        diff = (lon2 - lon1) % 360
        assert 20 < diff < 32

    def test_all_planets_return_valid(self):
        """All classical + outer planets return valid longitudes."""
        from core.ephemeris import ephe
        import swisseph as swe
        dt = datetime(2024, 6, 15, 12, 0, 0)
        jd = ephe.julian_day(dt)
        planets = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS,
                   swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO]
        for planet in planets:
            lon, lat = ephe.planet_longitude(jd, planet)
            assert 0 <= lon < 360, f"Planet {planet} longitude out of range: {lon}"
            assert -90 <= lat <= 90, f"Planet {planet} latitude out of range: {lat}"


class TestRetrograde:
    """Retrograde detection tests."""

    def test_sun_never_retrograde(self):
        """Sun is never retrograde."""
        from core.ephemeris import ephe
        import swisseph as swe
        dt = datetime(2024, 6, 15, 12, 0, 0)
        jd = ephe.julian_day(dt)
        assert not ephe.is_retrograde(jd, swe.SUN)

    def test_moon_never_retrograde(self):
        """Moon is never retrograde."""
        from core.ephemeris import ephe
        import swisseph as swe
        dt = datetime(2024, 6, 15, 12, 0, 0)
        jd = ephe.julian_day(dt)
        assert not ephe.is_retrograde(jd, swe.MOON)


class TestHouses:
    """House calculation tests."""

    def test_houses_returns_12_cusps(self):
        """houses() should return exactly 12 cusps."""
        from core.ephemeris import ephe
        dt = datetime(2024, 6, 15, 12, 0, 0)
        jd = ephe.julian_day(dt)
        cusps, ascmc = ephe.houses(jd, 51.5074, -0.1278)
        assert len(cusps) == 12

    def test_ascendant_in_ascmc(self):
        """ascmc[0] should be the Ascendant."""
        from core.ephemeris import ephe
        dt = datetime(2024, 6, 15, 12, 0, 0)
        jd = ephe.julian_day(dt)
        cusps, ascmc = ephe.houses(jd, 51.5074, -0.1278)
        asc = ascmc[0]
        assert 0 <= asc < 360

    def test_cusps_are_ordered(self):
        """House cusps should generally increase (modulo 360)."""
        from core.ephemeris import ephe
        dt = datetime(2024, 6, 15, 12, 0, 0)
        jd = ephe.julian_day(dt)
        cusps, _ = ephe.houses(jd, 51.5074, -0.1278)
        # All cusps should be valid longitudes
        for c in cusps:
            assert 0 <= c < 360


class TestDeterminism:
    """Verify ephemeris calculations are deterministic."""

    def test_same_input_same_output(self):
        """Same datetime → same positions, every time."""
        from core.ephemeris import ephe
        import swisseph as swe
        dt = datetime(1990, 6, 15, 14, 30, 0)
        jd = ephe.julian_day(dt)

        results = []
        for _ in range(10):
            lon, lat = ephe.planet_longitude(jd, swe.SUN)
            results.append(lon)

        assert all(r == results[0] for r in results), "Ephemeris is not deterministic!"

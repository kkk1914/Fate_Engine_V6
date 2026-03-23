"""Tests for core/models.py — Pydantic data contracts.

Phase 1.7: Validates that the Pydantic models accept the chart_data structure
and correctly enforce constraints.
"""
import pytest
from core.models import (
    ChartData, ChartMeta, WesternNatal, VedicNatal, BaziNatal,
    WesternPlacement, VedicPlacement, HouseCusp, Aspect,
)


class TestChartMeta:
    """ChartMeta validation tests."""

    def test_valid_meta(self):
        meta = ChartMeta(
            jd=2448088.104, lat=51.5074, lon=-0.1278,
            birth_year=1990, birth_datetime="1990-06-15T14:30:00",
            time_known=True,
        )
        assert meta.lat == 51.5074

    def test_lat_out_of_range(self):
        with pytest.raises(Exception):
            ChartMeta(
                jd=2448088.104, lat=100.0, lon=-0.1278,
                birth_year=1990, birth_datetime="1990-06-15T14:30:00",
                time_known=True,
            )

    def test_lon_out_of_range(self):
        with pytest.raises(Exception):
            ChartMeta(
                jd=2448088.104, lat=51.5, lon=200.0,
                birth_year=1990, birth_datetime="1990-06-15T14:30:00",
                time_known=True,
            )

    def test_extra_fields_allowed(self):
        """Extra fields should be allowed (backward compatibility)."""
        meta = ChartMeta(
            jd=2448088.104, lat=51.5, lon=-0.1278,
            birth_year=1990, birth_datetime="test",
            time_known=True,
            some_future_field="value",  # Should not raise
        )
        assert meta.some_future_field == "value"


class TestWesternPlacement:
    def test_valid_placement(self):
        p = WesternPlacement(longitude=84.23, sign="Gemini", degree=24.23)
        assert p.sign == "Gemini"

    def test_optional_fields_default_none(self):
        p = WesternPlacement(longitude=0.0, sign="Aries", degree=0.0)
        assert p.retrograde is None
        assert p.declination is None


class TestVedicPlacement:
    def test_valid_placement(self):
        p = VedicPlacement(lon=60.23, sign="Taurus", deg_in_sign=0.23)
        assert p.sign == "Taurus"

    def test_with_nakshatra(self):
        p = VedicPlacement(
            lon=60.23, sign="Taurus", deg_in_sign=0.23,
            nakshatra="Mrigashira", pada=3,
        )
        assert p.nakshatra == "Mrigashira"


class TestChartDataValidation:
    """Full ChartData validation tests."""

    def test_validates_frozen_chart_data(self, frozen_chart_data):
        """The frozen fixture should pass validation."""
        cd = ChartData.validate_chart(frozen_chart_data)
        assert cd.meta.lat == 51.5074
        assert cd.degradation_flags == {}

    def test_missing_meta_raises(self):
        """Missing meta should raise validation error."""
        with pytest.raises(Exception):
            ChartData.validate_chart({"western": {}, "vedic": {}})

    def test_degradation_flags_preserved(self, frozen_chart_data):
        """Degradation flags should pass through."""
        frozen_chart_data["degradation_flags"] = {"Vedic": "calculation_failed"}
        cd = ChartData.validate_chart(frozen_chart_data)
        assert cd.degradation_flags["Vedic"] == "calculation_failed"

    def test_extra_top_level_keys_allowed(self, frozen_chart_data):
        """Unknown top-level keys should be allowed (extra='allow')."""
        frozen_chart_data["_house_lord_reference_block"] = "some text"
        frozen_chart_data["predictive_event_count"] = 42
        cd = ChartData.validate_chart(frozen_chart_data)
        assert cd.predictive_event_count == 42

    def test_none_systems_allowed(self, frozen_chart_data):
        """Systems can be None if they failed."""
        frozen_chart_data["vedic"] = None
        cd = ChartData.validate_chart(frozen_chart_data)
        assert cd.vedic is None

    def test_empty_dict_systems_allowed(self, frozen_chart_data):
        """Systems can be empty dicts if they returned no data."""
        frozen_chart_data["hellenistic"] = {}
        cd = ChartData.validate_chart(frozen_chart_data)
        assert cd.hellenistic == {}


class TestAspect:
    def test_valid_aspect(self):
        a = Aspect(planet1="Sun", planet2="Moon", aspect="trine", orb=1.78)
        assert a.aspect == "trine"

    def test_minimal_aspect(self):
        a = Aspect(planet1="Mars", planet2="Saturn", aspect="square")
        assert a.orb is None

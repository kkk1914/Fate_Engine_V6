"""Tests for core/geocoder.py — geocoding service with LRU cache.

Phase 1.7: Tests cache behavior, normalization, and error handling.
Uses mocked Nominatim to avoid network calls.
"""
import pytest
from unittest.mock import patch, MagicMock
from core.geocoder import GeocoderService


class TestNormalization:
    """Location key normalization."""

    def test_lowercase(self):
        assert GeocoderService._normalize_location("London, UK") == "london, uk"

    def test_strip_whitespace(self):
        assert GeocoderService._normalize_location("  London, UK  ") == "london, uk"

    def test_already_normalized(self):
        assert GeocoderService._normalize_location("london, uk") == "london, uk"


class TestGeocodingWithMock:
    """Geocoding with mocked Nominatim."""

    @patch("core.geocoder.GeocoderService._geocode_nominatim")
    def test_successful_geocode(self, mock_nominatim):
        mock_nominatim.return_value = (51.5074, -0.1278)
        gs = GeocoderService.__new__(GeocoderService)
        from functools import lru_cache
        gs._cached_geocode = lru_cache(maxsize=256)(mock_nominatim)

        lat, lon = gs.geocode("London, UK")
        assert abs(lat - 51.5074) < 0.01
        assert abs(lon - (-0.1278)) < 0.01

    @patch("core.geocoder.GeocoderService._geocode_nominatim")
    def test_not_found_raises(self, mock_nominatim):
        mock_nominatim.return_value = (None, None)
        gs = GeocoderService.__new__(GeocoderService)
        from functools import lru_cache
        gs._cached_geocode = lru_cache(maxsize=256)(mock_nominatim)

        with pytest.raises(ValueError, match="not found"):
            gs.geocode("Nonexistent Place XYZ")

    @patch("core.geocoder.GeocoderService._geocode_nominatim")
    def test_cache_hit(self, mock_nominatim):
        """Second call with same location should hit cache."""
        mock_nominatim.return_value = (51.5074, -0.1278)
        gs = GeocoderService.__new__(GeocoderService)
        from functools import lru_cache
        gs._cached_geocode = lru_cache(maxsize=256)(mock_nominatim)

        gs.geocode("London, UK")
        gs.geocode("London, UK")
        gs.geocode("LONDON, UK")  # normalized to same key

        # Should only call Nominatim once (all three normalize to same key)
        assert mock_nominatim.call_count == 1

    @patch("core.geocoder.GeocoderService._geocode_nominatim")
    def test_different_locations_separate_cache(self, mock_nominatim):
        """Different locations should each call Nominatim."""
        def side_effect(loc):
            return {"london, uk": (51.5, -0.1), "new york, us": (40.7, -74.0)}[loc]

        mock_nominatim.side_effect = side_effect
        gs = GeocoderService.__new__(GeocoderService)
        from functools import lru_cache
        gs._cached_geocode = lru_cache(maxsize=256)(mock_nominatim)

        gs.geocode("London, UK")
        gs.geocode("New York, US")

        assert mock_nominatim.call_count == 2

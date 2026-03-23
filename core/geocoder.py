"""Geocoding service with LRU cache.

Phase 1.1: Centralized geocoding with two-tier caching.
- Tier 1: In-memory LRU cache (process-local, fast)
- Tier 2: Redis cache (future — shared across instances, survives restarts)

Replaces inline geocoding in orchestrator.py and chart_engine.py.

Usage:
    from core.geocoder import geocoder

    lat, lon = geocoder.geocode("London, UK")
"""
import logging
from functools import lru_cache
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class GeocoderService:
    """Geocoding with LRU cache and graceful fallback."""

    def __init__(self, cache_size: int = 256):
        """Initialize with configurable LRU cache size."""
        # Wrap the actual geocoding call with lru_cache
        # We use a module-level function to make it cacheable
        self._cache_size = cache_size
        self._cached_geocode = lru_cache(maxsize=cache_size)(self._geocode_nominatim)

    @staticmethod
    def _normalize_location(location: str) -> str:
        """Normalize location string for cache key consistency."""
        return location.lower().strip()

    @staticmethod
    def _geocode_nominatim(location_key: str) -> Tuple[Optional[float], Optional[float]]:
        """Actual Nominatim API call (uncached — wrapper adds caching)."""
        try:
            from geopy.geocoders import Nominatim
            from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

            geolocator = Nominatim(user_agent="fates_engine_v2/2.0")
            result = geolocator.geocode(location_key, timeout=10)
            if result:
                lat, lon = float(result.latitude), float(result.longitude)
                logger.info(f"Geocoded '{location_key}' → {lat:.4f}, {lon:.4f}")
                return lat, lon
            else:
                logger.warning(f"Geocoding returned no result for: '{location_key}'")
                return None, None

        except ImportError:
            raise ImportError("geopy required. Install: pip install geopy")
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.error(f"Geocoding service error for '{location_key}': {e}")
            raise ConnectionError(f"Geocoding error: {e}")

    def geocode(self, location: str) -> Tuple[float, float]:
        """Geocode a location string. Returns (lat, lon).

        Raises:
            ValueError: If location cannot be found.
            ImportError: If geopy is not installed.
            ConnectionError: If geocoding service is unavailable.
        """
        key = self._normalize_location(location)
        lat, lon = self._cached_geocode(key)

        if lat is None or lon is None:
            raise ValueError(f"Location not found: '{location}'")

        return lat, lon

    @property
    def cache_info(self):
        """Return cache statistics."""
        return self._cached_geocode.cache_info()

    def clear_cache(self):
        """Clear the geocoding cache."""
        self._cached_geocode.cache_clear()


# Global instance
geocoder = GeocoderService()

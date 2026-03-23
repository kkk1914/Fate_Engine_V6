"""Shared test fixtures for Fate Engine V6.

Phase 1.7: Provides frozen chart_data, mock gateway, and mock swisseph
for deterministic, fast tests that don't require API keys or ephemeris files.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


# ── Frozen Chart Data Fixture ──────────────────────────────────────────────
# Minimal but structurally complete chart_data for a known birth chart:
# 1990-06-15 14:30 UTC, London UK (51.5074, -0.1278)
@pytest.fixture
def frozen_chart_data():
    """Deterministic chart_data dict for unit tests."""
    return {
        "western": {
            "natal": {
                "placements": {
                    "Sun": {"longitude": 84.23, "sign": "Gemini", "degree": 24.23,
                            "latitude": 0.0, "retrograde": False},
                    "Moon": {"longitude": 312.45, "sign": "Aquarius", "degree": 12.45,
                             "latitude": -3.2, "retrograde": False},
                    "Mercury": {"longitude": 103.67, "sign": "Cancer", "degree": 13.67,
                                "latitude": 1.5, "retrograde": False},
                    "Venus": {"longitude": 55.89, "sign": "Taurus", "degree": 25.89,
                              "latitude": -0.8, "retrograde": False},
                    "Mars": {"longitude": 17.34, "sign": "Aries", "degree": 17.34,
                             "latitude": 0.3, "retrograde": False},
                    "Jupiter": {"longitude": 96.12, "sign": "Cancer", "degree": 6.12,
                                "latitude": 0.5, "retrograde": False},
                    "Saturn": {"longitude": 290.78, "sign": "Capricorn", "degree": 20.78,
                               "latitude": -1.1, "retrograde": True},
                    "North Node": {"longitude": 310.0, "sign": "Aquarius", "degree": 10.0,
                                   "latitude": 0.0, "retrograde": True},
                },
                "houses": {
                    f"House_{i}": {"longitude": (i - 1) * 30.0, "sign": "Aries", "degree": 0.0}
                    for i in range(1, 13)
                },
                "angles": {
                    "Ascendant": {"longitude": 215.5, "sign": "Scorpio", "degree": 5.5},
                    "Midheaven": {"longitude": 130.2, "sign": "Leo", "degree": 10.2},
                },
                "aspects": [
                    {"planet1": "Sun", "planet2": "Moon", "aspect": "trine", "orb": 1.78},
                    {"planet1": "Mars", "planet2": "Saturn", "aspect": "square", "orb": 3.44},
                ],
                "patterns": {},
                "dignities": {},
                "receptions": {},
            },
            "predictive": {
                "primary_directions": {},
                "solar_returns": [],
                "lunar_returns": [],
            },
        },
        "vedic": {
            "natal": {
                "placements": {
                    "Sun": {"lon": 60.23, "sign": "Taurus", "deg_in_sign": 0.23,
                            "nakshatra": "Mrigashira", "pada": 3},
                    "Moon": {"lon": 288.45, "sign": "Capricorn", "deg_in_sign": 18.45,
                             "nakshatra": "Shravana", "pada": 2},
                },
                "houses": {
                    f"Bhava_{i}": {"cusp_lon": (i - 1) * 30.0, "sign": "Aries", "lord": "Mars"}
                    for i in range(1, 13)
                },
            },
            "strength": {
                "shadbala": {
                    "planet_scores": {
                        "Sun": {"tier": "Strong", "total_rupas": 380.5},
                        "Moon": {"tier": "Average", "total_rupas": 320.1},
                    },
                },
                "ashtakavarga_full": {},
            },
            "predictive": {
                "vimshottari": {
                    "maha_lord": "Jupiter",
                    "antar_lord": "Saturn",
                },
            },
        },
        "bazi": {
            "natal": {
                "pillars": {
                    "Year": {"stem": "Geng", "branch": "Wu", "element": "Metal"},
                    "Month": {"stem": "Ren", "branch": "Wu", "element": "Water"},
                    "Day": {"stem": "Jia", "branch": "Xu", "element": "Wood"},
                    "Hour": {"stem": "Xin", "branch": "Wei", "element": "Metal"},
                },
            },
            "predictive": {
                "da_yun": {"pillars": []},
            },
        },
        "hellenistic": {
            "lots": {"Fortune": {"longitude": 140.5, "sign": "Leo"}},
            "zodiacal_releasing": {},
            "annual_profections": {},
            "firdaria": {},
        },
        "meta": {
            "jd": 2448058.104,
            "lat": 51.5074,
            "lon": -0.1278,
            "birth_year": 1990,
            "birth_datetime": "1990-06-15T14:30:00",
            "time_known": True,
        },
        "degradation_flags": {},
        "lord_validations": {},
        "predictive": {
            "western": {},
            "vedic": {},
            "saju": {},
            "hellenistic": {},
        },
        "house_lords": {
            "western_lords": {str(i): "Mars" for i in range(1, 13)},
            "vedic_lords": {str(i): "Mars" for i in range(1, 13)},
            "bazi_elements": {
                "day_master_element": "Wood",
                "Output": "Fire",
                "Wealth": "Earth",
                "Power": "Metal",
                "Resource": "Water",
                "Companion": "Wood",
            },
        },
    }


@pytest.fixture
def mock_gateway():
    """Mock LLM gateway that returns canned responses."""
    gw = MagicMock()
    gw.generate.return_value = {
        "success": True,
        "content": "Mock LLM response for testing.",
        "model": "mock-model",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }
    gw.structured_generate.return_value = {
        "success": True,
        "data": {"summary": "Mock structured response"},
        "model": "mock-model",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }
    return gw


@pytest.fixture
def mock_swe():
    """Mock swisseph for tests that don't need real ephemeris."""
    with patch("swisseph.calc_ut") as mock_calc, \
         patch("swisseph.houses") as mock_houses, \
         patch("swisseph.julday") as mock_jd:
        # Sun at 84.23° Gemini
        mock_calc.return_value = (84.23, 0.0, 1.0, 0.5, 0.0, 0.0)
        mock_houses.return_value = (
            [0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0, 330.0],
            [215.5, 130.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        mock_jd.return_value = 2448088.104
        yield {
            "calc_ut": mock_calc,
            "houses": mock_houses,
            "julday": mock_jd,
        }

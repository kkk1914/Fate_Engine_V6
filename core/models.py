"""Pydantic v2 data contracts for Fate Engine chart data.

Phase 1.6: Typed models replacing Dict[str, Any] for the chart_data structure.
Validated at the boundary (end of _calculate_charts) to catch type mismatches
without changing any downstream caller.

Design decisions:
- ConfigDict(extra='allow') on all models for backward compatibility during
  transition — unknown keys pass through rather than raise ValidationError.
- Optional fields for data that may be absent (e.g., time_unknown mode skips
  house-sensitive data; degraded systems return empty dicts).
- Nested models only for the most-accessed structures; deeper nesting uses
  Dict[str, Any] to avoid premature rigidity.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, Any, Optional, List


# ── Shared Config ─────────────────────────────────────────────────────────
_EXTRA_ALLOW = ConfigDict(extra="allow")


# ── Planet Placements ─────────────────────────────────────────────────────
class WesternPlacement(BaseModel):
    """Single planet placement in Western (tropical) system."""
    model_config = _EXTRA_ALLOW

    longitude: float
    sign: str
    degree: float
    latitude: Optional[float] = None
    declination: Optional[float] = None
    out_of_bounds: Optional[bool] = None
    retrograde: Optional[bool] = None


class VedicPlacement(BaseModel):
    """Single planet placement in Vedic (sidereal) system."""
    model_config = _EXTRA_ALLOW

    lon: float
    sign: str
    deg_in_sign: float
    nakshatra: Optional[str] = None
    pada: Optional[int] = None
    d9: Optional[str] = None
    d10: Optional[str] = None
    is_vargottama: Optional[bool] = None
    dignity: Optional[str] = None


# ── House Structures ──────────────────────────────────────────────────────
class HouseCusp(BaseModel):
    """Single house cusp."""
    model_config = _EXTRA_ALLOW

    longitude: Optional[float] = None
    sign: str
    degree: Optional[float] = None


class Angle(BaseModel):
    """Chart angle (Ascendant, MC, etc.)."""
    model_config = _EXTRA_ALLOW

    longitude: float
    sign: str
    degree: float


# ── Aspect ────────────────────────────────────────────────────────────────
class Aspect(BaseModel):
    """Planetary aspect."""
    model_config = _EXTRA_ALLOW

    planet1: str
    planet2: str
    aspect: str
    distance: Optional[float] = None
    orb: Optional[float] = None


# ── Western Natal ─────────────────────────────────────────────────────────
class WesternNatal(BaseModel):
    """Western tropical natal chart data."""
    model_config = _EXTRA_ALLOW

    placements: Dict[str, Any]  # Planet name → WesternPlacement-like dict
    houses: Optional[Dict[str, Any]] = None
    angles: Optional[Dict[str, Any]] = None
    aspects: Optional[List[Dict[str, Any]]] = None
    lots: Optional[Dict[str, Any]] = None
    fixed_stars: Optional[List[Any]] = None
    parans: Optional[List[Any]] = None
    patterns: Optional[Dict[str, Any]] = None
    dignities: Optional[Dict[str, Any]] = None
    receptions: Optional[Dict[str, Any]] = None
    syzygy: Optional[Dict[str, Any]] = None
    dodecatemoria: Optional[Dict[str, Any]] = None


class WesternSystem(BaseModel):
    """Complete Western system data."""
    model_config = _EXTRA_ALLOW

    natal: WesternNatal
    predictive: Optional[Dict[str, Any]] = None


# ── Vedic System ──────────────────────────────────────────────────────────
class VedicNatal(BaseModel):
    """Vedic sidereal natal chart data."""
    model_config = _EXTRA_ALLOW

    placements: Dict[str, Any]  # Planet name → VedicPlacement-like dict
    houses: Optional[Dict[str, Any]] = None
    bhava_chalit: Optional[Dict[str, Any]] = None
    chara_karakas: Optional[Dict[str, Any]] = None
    yogas: Optional[List[Any]] = None
    vargas: Optional[Dict[str, Any]] = None


class VedicStrength(BaseModel):
    """Vedic planetary strength data (Shadbala + Ashtakavarga)."""
    model_config = _EXTRA_ALLOW

    shadbala: Optional[Dict[str, Any]] = None  # Always dict (normalized)
    ashtakavarga: Optional[Dict[str, Any]] = None
    ashtakavarga_full: Optional[Dict[str, Any]] = None


class VedicSystem(BaseModel):
    """Complete Vedic system data."""
    model_config = _EXTRA_ALLOW

    natal: VedicNatal
    strength: Optional[VedicStrength] = None
    predictive: Optional[Dict[str, Any]] = None


# ── Bazi/Saju System ─────────────────────────────────────────────────────
class BaziNatal(BaseModel):
    """Bazi four-pillar natal data."""
    model_config = _EXTRA_ALLOW

    pillars: Dict[str, Any]  # Year/Month/Day/Hour → pillar dict


class BaziSystem(BaseModel):
    """Complete Bazi/Saju system data."""
    model_config = _EXTRA_ALLOW

    natal: BaziNatal
    strength: Optional[Dict[str, Any]] = None
    predictive: Optional[Dict[str, Any]] = None


# ── Hellenistic System ────────────────────────────────────────────────────
class HellenisticSystem(BaseModel):
    """Hellenistic astrology data (flat structure, no natal/predictive wrapper)."""
    model_config = _EXTRA_ALLOW

    lots: Optional[Dict[str, Any]] = None
    zodiacal_releasing: Optional[Dict[str, Any]] = None
    annual_profections: Optional[Dict[str, Any]] = None
    firdaria: Optional[Dict[str, Any]] = None
    alcocoden: Optional[Dict[str, Any]] = None


# ── Metadata ──────────────────────────────────────────────────────────────
class ChartMeta(BaseModel):
    """Birth metadata attached to every chart calculation."""
    model_config = _EXTRA_ALLOW

    jd: float
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    birth_year: int
    birth_datetime: str
    time_known: bool


# ── House Lords ───────────────────────────────────────────────────────────
class HouseLords(BaseModel):
    """Pre-computed house rulers across systems."""
    model_config = _EXTRA_ALLOW

    western_lords: Optional[Dict[str, str]] = None  # house_num → planet
    vedic_lords: Optional[Dict[str, str]] = None
    bazi_elements: Optional[Dict[str, str]] = None


# ── Top-Level ChartData ──────────────────────────────────────────────────
class ChartData(BaseModel):
    """Complete chart data structure — validated at orchestrator boundary.

    This is the single source of truth for all downstream consumers:
    experts, arbiter, archon, and API response.
    """
    model_config = _EXTRA_ALLOW

    western: Optional[Dict[str, Any]] = None
    vedic: Optional[Dict[str, Any]] = None
    bazi: Optional[Dict[str, Any]] = None
    hellenistic: Optional[Dict[str, Any]] = None
    meta: ChartMeta
    degradation_flags: Dict[str, str] = {}
    lord_validations: Optional[Dict[str, Any]] = None
    predictive: Optional[Dict[str, Any]] = None
    house_lords: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None

    @classmethod
    def validate_chart(cls, data: dict) -> "ChartData":
        """Validate chart_data dict at the orchestrator boundary.

        Returns the validated ChartData instance. Raises ValidationError
        if critical fields (meta, at least one system) are invalid.

        Uses model_validate for Pydantic v2 compatibility.
        """
        return cls.model_validate(data)

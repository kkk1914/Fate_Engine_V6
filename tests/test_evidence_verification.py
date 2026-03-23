"""Tests for Phase 3.5 — evidence-key verification in qa_pipeline.py.

Validates _verify_source_map and _resolve_dot_path against actual
chart data structures.
"""
import pytest
from synthesis.qa_pipeline import _verify_source_map, _resolve_dot_path


class TestResolveDotPath:
    """Test dot-path resolution against chart data structures."""

    def test_house_lords_western(self):
        ref = {}
        house_lords = {"western_lords": {7: "Mars", 10: "Jupiter"}}
        assert _resolve_dot_path("house_lords.western_lords.7", ref, house_lords) == "Mars"

    def test_house_lords_vedic(self):
        ref = {}
        house_lords = {"vedic_lords": {10: "Saturn"}}
        assert _resolve_dot_path("house_lords.vedic_lords.10", ref, house_lords) == "Saturn"

    def test_house_lords_missing(self):
        ref = {}
        house_lords = {"western_lords": {7: "Mars"}}
        assert _resolve_dot_path("house_lords.western_lords.3", ref, house_lords) is None

    def test_planet_sign(self):
        ref = {"Sun": {"sign": "Gemini", "degree": 23.5}}
        house_lords = {}
        assert _resolve_dot_path("western.natal.Sun.sign", ref, house_lords) == "Gemini"

    def test_planet_missing(self):
        ref = {"Sun": {"sign": "Gemini"}}
        house_lords = {}
        assert _resolve_dot_path("western.natal.Pluto.sign", ref, house_lords) is None

    def test_generic_nested(self):
        ref = {"natal": {"Sun": {"sign": "Aries"}}}
        house_lords = {}
        # Generic resolution through ref
        result = _resolve_dot_path("natal.Sun.sign", ref, house_lords)
        assert result == "Aries"


class TestVerifySourceMap:
    """Test full source_map verification."""

    def test_correct_claims_pass(self):
        source_map = [
            {"claim": "Mars rules 7th house", "evidence_key": "house_lords.western_lords.7", "value": "Mars"},
            {"claim": "Sun in Gemini", "evidence_key": "western.natal.Sun.sign", "value": "Gemini"},
        ]
        ref = {"Sun": {"sign": "Gemini"}}
        house_lords = {"western_lords": {7: "Mars"}}
        errors = _verify_source_map(source_map, ref, house_lords)
        assert len(errors) == 0

    def test_wrong_house_lord_detected(self):
        source_map = [
            {"claim": "Venus rules 7th house", "evidence_key": "house_lords.western_lords.7", "value": "Venus"},
        ]
        ref = {}
        house_lords = {"western_lords": {7: "Mars"}}
        errors = _verify_source_map(source_map, ref, house_lords)
        assert len(errors) == 1
        assert errors[0]["claimed"] == "Venus"
        assert errors[0]["actual"] == "Mars"

    def test_wrong_sign_detected(self):
        source_map = [
            {"claim": "Sun in Cancer", "evidence_key": "western.natal.Sun.sign", "value": "Cancer"},
        ]
        ref = {"Sun": {"sign": "Gemini"}}
        house_lords = {}
        errors = _verify_source_map(source_map, ref, house_lords)
        assert len(errors) == 1
        assert errors[0]["claimed"] == "Cancer"
        assert errors[0]["actual"] == "Gemini"

    def test_case_insensitive_match(self):
        source_map = [
            {"claim": "mars rules 7th", "evidence_key": "house_lords.western_lords.7", "value": "mars"},
        ]
        ref = {}
        house_lords = {"western_lords": {7: "Mars"}}
        errors = _verify_source_map(source_map, ref, house_lords)
        assert len(errors) == 0  # case-insensitive match

    def test_empty_source_map(self):
        errors = _verify_source_map([], {}, {})
        assert errors == []

    def test_missing_key_ignored(self):
        """Claims with unresolvable keys are skipped, not flagged."""
        source_map = [
            {"claim": "Dasha says...", "evidence_key": "vedic.predictive.vimshottari.current", "value": "Jupiter"},
        ]
        ref = {}
        house_lords = {}
        errors = _verify_source_map(source_map, ref, house_lords)
        assert len(errors) == 0  # unresolvable → skip, not error

    def test_partial_match_passes(self):
        """Partial string containment is acceptable."""
        source_map = [
            {"claim": "Sun in Gemini", "evidence_key": "western.natal.Sun.sign", "value": "Gem"},
        ]
        ref = {"Sun": {"sign": "Gemini"}}
        errors = _verify_source_map(source_map, ref, {})
        assert len(errors) == 0  # "Gem" is contained in "Gemini"

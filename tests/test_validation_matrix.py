"""Unit tests for synthesis.validation_matrix — convergence detection."""
import pytest
from datetime import datetime, timezone, timedelta
from synthesis.validation_matrix import PredictionEvent, ValidationMatrix


def _make_event(system, technique, start, end, theme, house, planets,
                confidence=1.0):
    """Helper to build PredictionEvent with UTC-aware dates."""
    return PredictionEvent(
        system=system,
        technique=technique,
        date_range=(
            datetime.fromisoformat(start).replace(tzinfo=timezone.utc),
            datetime.fromisoformat(end).replace(tzinfo=timezone.utc),
        ),
        theme=theme,
        confidence=confidence,
        description=f"Test: {technique} {theme}",
        house_involved=house,
        planets_involved=planets,
    )


# ─────────────────────────────────────────────────────────────────────────────
# NEGATIVE: same month, different themes → no convergence
# ─────────────────────────────────────────────────────────────────────────────

class TestDifferentThemesNoConvergence:
    """Western + Vedic events in the same month but with completely different
    themes, houses, and planets must NOT produce a convergence."""

    def test_career_vs_romance_no_convergence(self):
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Transit", "2027-03-01", "2027-03-15",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Vimshottari Dasha", "2027-03-05", "2027-03-20",
            "Romance", 5, ["Venus"],
        ))
        convergences = vm.find_convergences()
        assert convergences == [], (
            f"Expected no convergence for different themes/houses/planets, "
            f"got {len(convergences)}"
        )

    def test_health_vs_spirituality_no_convergence(self):
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Solar Arc", "2027-05-01", "2027-05-20",
            "Health", 6, ["Mars"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Tajaka", "2027-05-05", "2027-05-25",
            "Spirituality", 12, ["Ketu"],
        ))
        convergences = vm.find_convergences()
        assert convergences == [], (
            "Houses 6 and 12 are not in same domain group and themes differ"
        )


# ─────────────────────────────────────────────────────────────────────────────
# NEGATIVE: same theme, beyond tolerance → no convergence
# ─────────────────────────────────────────────────────────────────────────────

class TestBeyondToleranceNoConvergence:
    """Events with matching themes but 40 days apart (beyond the default
    30-day tolerance) must NOT converge."""

    def test_40_day_gap_no_convergence(self):
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Solar Return", "2027-06-01", "2027-06-10",
            "Career", 10, ["Jupiter"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Tajaka", "2027-07-20", "2027-07-30",
            "Career", 10, ["Jupiter"],
        ))
        convergences = vm.find_convergences()
        assert convergences == [], (
            f"Expected no convergence for 40-day gap with 30-day tolerance, "
            f"got {len(convergences)}"
        )

    def test_custom_tolerance_captures_40_day_gap(self):
        """With tolerance_days=50, the same 40-day gap should converge."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Solar Return", "2027-06-01", "2027-06-10",
            "Career", 10, ["Jupiter"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Tajaka", "2027-07-20", "2027-07-30",
            "Career", 10, ["Jupiter"],
        ))
        convergences = vm.find_convergences(tolerance_days=50)
        assert len(convergences) >= 1, (
            "50-day tolerance should capture 40-day gap"
        )


# ─────────────────────────────────────────────────────────────────────────────
# POSITIVE: matching events converge
# ─────────────────────────────────────────────────────────────────────────────

class TestPositiveConvergence:
    """Events with same theme, overlapping dates, from different systems
    must produce convergence."""

    def test_overlapping_career_events_converge(self):
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Transit", "2027-03-01", "2027-03-20",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Vimshottari Dasha", "2027-03-10", "2027-04-01",
            "Career", 10, ["Saturn"],
        ))
        convergences = vm.find_convergences()
        assert len(convergences) >= 1
        assert set(convergences[0]["systems"]) == {"Western", "Vedic"}

    def test_domain_group_match_converges(self):
        """Houses 2 and 10 share the Career domain group — different theme
        strings but matching domain should converge."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Transit", "2027-03-01", "2027-03-20",
            "Finances", 2, ["Jupiter"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Vimshottari Dasha", "2027-03-05", "2027-03-25",
            "Profession", 10, ["Mars"],
        ))
        convergences = vm.find_convergences()
        assert len(convergences) >= 1, (
            "Houses 2 and 10 share the Career domain group"
        )

    def test_shared_planets_trigger_convergence(self):
        """Different themes and non-overlapping houses, but shared planet
        involvement should trigger thematic match."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Transit", "2027-04-01", "2027-04-15",
            "Career", 10, ["Jupiter"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Tajaka", "2027-04-05", "2027-04-20",
            "Spirituality", 12, ["Jupiter"],
        ))
        convergences = vm.find_convergences()
        assert len(convergences) >= 1, (
            "Shared Jupiter involvement should trigger thematic match"
        )


# ─────────────────────────────────────────────────────────────────────────────
# NEGATIVE: same system → no cross-system convergence
# ─────────────────────────────────────────────────────────────────────────────

class TestSameSystemNoConvergence:
    """Two events from the SAME system must not count as cross-system
    convergence, even with perfect theme/date overlap."""

    def test_western_western_no_convergence(self):
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Transit", "2027-03-01", "2027-03-20",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Western", "Solar Return", "2027-03-05", "2027-03-25",
            "Career", 10, ["Saturn"],
        ))
        convergences = vm.find_convergences()
        assert convergences == [], (
            "Same-system events should not produce cross-system convergence"
        )


# ─────────────────────────────────────────────────────────────────────────────
# EDGE: mixed timezone-naive and timezone-aware datetimes
# ─────────────────────────────────────────────────────────────────────────────

class TestTimezoneHandling:
    """Events with one naive and one tz-aware datetime should converge
    without error, thanks to _ensure_aware()."""

    def test_naive_and_aware_dates_mix(self):
        vm = ValidationMatrix()
        e1 = PredictionEvent(
            system="Western", technique="Transit",
            date_range=(datetime(2027, 3, 1), datetime(2027, 3, 20)),
            theme="Career", confidence=1.0,
            description="test", house_involved=10,
            planets_involved=["Saturn"],
        )
        e2 = PredictionEvent(
            system="Vedic", technique="Tajaka",
            date_range=(
                datetime(2027, 3, 5, tzinfo=timezone.utc),
                datetime(2027, 3, 25, tzinfo=timezone.utc),
            ),
            theme="Career", confidence=1.0,
            description="test", house_involved=10,
            planets_involved=["Saturn"],
        )
        vm.add_prediction(e1)
        vm.add_prediction(e2)
        convergences = vm.find_convergences()
        assert len(convergences) >= 1, (
            "Mixed naive/aware datetimes should be handled by _ensure_aware"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Probabilistic combined_confidence: 1 - ∏(1 - P(event_i))
# ─────────────────────────────────────────────────────────────────────────────

class TestProbabilisticConfidence:
    """Verify that combined_confidence uses the probabilistic formula
    P(at least one correct) = 1 - product(1 - P_i) instead of simple average."""

    def test_two_high_techniques(self):
        """Primary Direction (0.95) + Vimshottari Dasha (0.92) should produce
        1 - (0.05 × 0.08) = 0.996, NOT avg * bonus = ~0.82."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Primary Direction", "2027-03-01", "2027-03-20",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Vimshottari Dasha", "2027-03-05", "2027-03-25",
            "Career", 10, ["Saturn"],
        ))
        convergences = vm.find_convergences()
        assert len(convergences) >= 1
        conf = convergences[0]["combined_confidence"]
        # 1 - (1-0.95)(1-0.92) = 1 - 0.05*0.08 = 0.996
        assert abs(conf - 0.996) < 0.001, (
            f"Expected ~0.996, got {conf}"
        )

    def test_three_system_boost(self):
        """Three systems should produce higher confidence than two."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Primary Direction", "2027-04-01", "2027-04-20",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Vimshottari Dasha", "2027-04-05", "2027-04-25",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Hellenistic", "Profection", "2027-04-03", "2027-04-22",
            "Career", 10, ["Saturn"],
        ))
        convergences = vm.find_convergences()
        assert len(convergences) >= 1
        conf = convergences[0]["combined_confidence"]
        # 1 - (1-0.95)(1-0.92)(1-0.78) = 1 - 0.05*0.08*0.22 = 1 - 0.00088 = 0.9991
        assert conf > 0.996, (
            f"3-system confidence ({conf}) should exceed 2-system (~0.996)"
        )

    def test_weak_techniques_stay_moderate(self):
        """Two weak techniques (0.5 weight each) → 1 - 0.5*0.5 = 0.75."""
        vm = ValidationMatrix()
        # Use techniques not in TECHNIQUE_WEIGHTS → default 0.5
        vm.add_prediction(_make_event(
            "Western", "UnknownTech", "2027-05-01", "2027-05-20",
            "Health", 6, ["Mars"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "UnknownTech2", "2027-05-05", "2027-05-25",
            "Health", 6, ["Mars"],
        ))
        convergences = vm.find_convergences()
        assert len(convergences) >= 1
        conf = convergences[0]["combined_confidence"]
        # Tier ceiling: two 0.5-weight (< 0.75) techniques cap at 0.74
        assert abs(conf - 0.74) < 0.001, (
            f"Expected ~0.74 (tier ceiling) for two 0.5-weight techniques, got {conf}"
        )

    def test_monotonic_increase(self):
        """Adding a convergent event must never decrease combined_confidence."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Transit", "2027-06-01", "2027-06-20",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Transit", "2027-06-05", "2027-06-25",
            "Career", 10, ["Saturn"],
        ))
        c2 = vm.find_convergences()
        assert len(c2) >= 1
        conf_2 = c2[0]["combined_confidence"]

        vm.add_prediction(_make_event(
            "Saju", "Da Yun", "2027-06-03", "2027-06-22",
            "Career", 10, ["Saturn"],
        ))
        c3 = vm.find_convergences()
        assert len(c3) >= 1
        conf_3 = c3[0]["combined_confidence"]
        assert conf_3 >= conf_2, (
            f"Adding 3rd event decreased confidence: {conf_3} < {conf_2}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# query_temporal_clusters: domain-filtered, scored convergence windows
# ─────────────────────────────────────────────────────────────────────────────

class TestQueryTemporalClusters:
    """Verify that query_temporal_clusters filters events by domain keywords,
    scores them probabilistically, and returns only the top N."""

    def test_filters_by_domain(self):
        """Career events should converge; Romance events should be excluded."""
        vm = ValidationMatrix()
        # Career convergence (Western + Vedic)
        vm.add_prediction(_make_event(
            "Western", "Transit", "2027-03-01", "2027-03-20",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Vimshottari Dasha", "2027-03-05", "2027-03-25",
            "Career", 10, ["Saturn"],
        ))
        # Romance convergence (Western + Vedic) — should NOT appear
        vm.add_prediction(_make_event(
            "Western", "Solar Return", "2027-04-01", "2027-04-20",
            "Romance", 5, ["Venus"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Tajaka", "2027-04-05", "2027-04-25",
            "Romance", 5, ["Venus"],
        ))
        results = vm.query_temporal_clusters(["Career", "Status", "Authority"])
        assert len(results) >= 1, "Should find career convergence"
        for r in results:
            assert r["theme_consensus"] != "Romance", (
                "Romance convergences should be excluded by career keywords"
            )

    def test_returns_top_n(self):
        """With top_n=2, only the 2 highest-confidence clusters are returned."""
        vm = ValidationMatrix()
        # Create 3 separate convergences with different techniques/confidences
        for i, (tech_w, tech_v) in enumerate([
            ("Primary Direction", "Vimshottari Dasha"),   # strongest
            ("Transit", "Tajaka"),                         # medium
            ("Solar Arc", "Shadbala"),                      # weakest
        ]):
            month = f"2027-0{3+i}-01"
            month_end = f"2027-0{3+i}-20"
            month_mid = f"2027-0{3+i}-05"
            month_end2 = f"2027-0{3+i}-25"
            vm.add_prediction(_make_event(
                "Western", tech_w, month, month_end,
                "Career", 10, ["Saturn"],
            ))
            vm.add_prediction(_make_event(
                "Vedic", tech_v, month_mid, month_end2,
                "Career", 10, ["Saturn"],
            ))
        results = vm.query_temporal_clusters(["Career"], top_n=2)
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        # Should be sorted by confidence descending
        assert results[0]["combined_confidence"] >= results[1]["combined_confidence"]

    def test_empty_keywords_returns_empty(self):
        """Non-matching keywords should return no clusters."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Transit", "2027-03-01", "2027-03-20",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Vimshottari Dasha", "2027-03-05", "2027-03-25",
            "Career", 10, ["Saturn"],
        ))
        results = vm.query_temporal_clusters(["Zygomorphic"])
        assert results == [], f"Non-matching keywords should return empty, got {len(results)}"

    def test_uses_probabilistic_confidence(self):
        """Returned combined_confidence should use the probabilistic formula
        with domain-specific bonuses applied."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Primary Direction", "2027-03-01", "2027-03-20",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Vimshottari Dasha", "2027-03-05", "2027-03-25",
            "Career", 10, ["Saturn"],
        ))
        results = vm.query_temporal_clusters(["Career"])
        assert len(results) >= 1
        conf = results[0]["combined_confidence"]
        # With Career bonus: PD=0.95 (no Career bonus), Dasha=0.92+0.10=1.0 (capped)
        # → 1 - (0.05 * 0.0) = 1.0
        assert abs(conf - 1.0) < 0.001, (
            f"Expected ~1.0 with Career domain bonus on Dasha, got {conf}"
        )


class TestTierCeiling:
    """Verify tier ceiling caps weak techniques at 0.74."""

    def test_tier_ceiling_caps_weak_techniques(self):
        """Three 0.65-weight events (Transit) should cap at 0.74."""
        events = [
            _make_event("Western", "Transit", "2027-03-01", "2027-03-20",
                        "Career", 10, ["Saturn"]),
            _make_event("Vedic", "Transit", "2027-03-05", "2027-03-25",
                        "Career", 10, ["Saturn"]),
            _make_event("Saju", "Transit", "2027-03-08", "2027-03-28",
                        "Career", 10, ["Saturn"]),
        ]
        # Apply weights
        vm = ValidationMatrix()
        for e in events:
            vm.add_prediction(e)
        # Raw: 1 - (0.35)^3 = 0.957... but ceiling caps at 0.74
        conf = ValidationMatrix._probabilistic_confidence(vm.events)
        assert conf == 0.74, f"Expected 0.74 (tier ceiling), got {conf}"

    def test_tier_ceiling_allows_strong_technique(self):
        """Events including one >= 0.75 weight should NOT be capped."""
        events = [
            _make_event("Western", "Transit", "2027-03-01", "2027-03-20",
                        "Career", 10, ["Saturn"]),
            _make_event("Vedic", "Primary Direction", "2027-03-05", "2027-03-25",
                        "Career", 10, ["Saturn"]),
        ]
        vm = ValidationMatrix()
        for e in events:
            vm.add_prediction(e)
        conf = ValidationMatrix._probabilistic_confidence(vm.events)
        # Transit=0.65, PD=0.95 → 1-(0.35*0.05) = 0.9825, should NOT be capped
        assert conf > 0.74, f"Should not be capped with a strong technique, got {conf}"
        assert abs(conf - 0.9825) < 0.001, f"Expected ~0.9825, got {conf}"

    def test_tier_ceiling_edge_case(self):
        """Two 0.74-weight events cap; adding one 0.75 event uncaps."""
        # Create events with known weights — use Shadbala (0.72) and SYZYGY (0.72)
        events_weak = [
            _make_event("Western", "Shadbala", "2027-03-01", "2027-03-20",
                        "Career", 10, ["Saturn"]),
            _make_event("Vedic", "SYZYGY", "2027-03-05", "2027-03-25",
                        "Career", 10, ["Saturn"]),
        ]
        vm = ValidationMatrix()
        for e in events_weak:
            vm.add_prediction(e)
        conf_capped = ValidationMatrix._probabilistic_confidence(vm.events)
        assert conf_capped == 0.74, f"Should be capped at 0.74, got {conf_capped}"

        # Add a strong technique (Solar Arc = 0.75)
        vm.add_prediction(_make_event(
            "Saju", "Solar Arc", "2027-03-08", "2027-03-28",
            "Career", 10, ["Saturn"],
        ))
        conf_uncapped = ValidationMatrix._probabilistic_confidence(vm.events)
        assert conf_uncapped > 0.74, f"Should be uncapped with Solar Arc, got {conf_uncapped}"


# ─────────────────────────────────────────────────────────────────────────────
# Content-based deduplication
# ─────────────────────────────────────────────────────────────────────────────

class TestContentDeduplication:
    """Verify deduplication uses content equality, not object identity."""

    def test_identical_events_as_separate_objects(self):
        """Two PredictionEvent objects with identical fields should deduplicate."""
        vm = ValidationMatrix()
        # Create two separate objects with identical content
        for _ in range(2):
            vm.add_prediction(_make_event(
                "Western", "Transit", "2027-06-01", "2027-06-20",
                "Career", 10, ["Saturn"],
            ))
        # Add a cross-system event to form a convergence
        vm.add_prediction(_make_event(
            "Vedic", "Vimshottari Dasha", "2027-06-05", "2027-06-25",
            "Career", 10, ["Saturn"],
        ))
        convergences = vm.find_convergences()
        # Should not produce duplicate convergences
        assert len(convergences) == 1, (
            f"Expected 1 convergence after dedup, got {len(convergences)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Domain-specific technique bonuses
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainBonuses:
    """Verify that query_temporal_clusters applies domain-specific weight
    bonuses to tradition-appropriate techniques."""

    def test_vedic_career_bonus_raises_confidence(self):
        """Vimshottari Dasha (base 0.92) + Career bonus (0.10) = 1.0 (capped).
        Combined with Transit (0.65, no bonus) should give higher confidence
        than without bonus."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Vedic", "Vimshottari Dasha", "2027-03-05", "2027-03-25",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Western", "Transit", "2027-03-01", "2027-03-20",
            "Career", 10, ["Saturn"],
        ))
        # Via find_convergences (no domain bonus)
        base = vm.find_convergences()
        assert len(base) >= 1
        base_conf = base[0]["combined_confidence"]

        # Via query_temporal_clusters (with Career domain bonus)
        results = vm.query_temporal_clusters(["Career"])
        assert len(results) >= 1
        domain_conf = results[0]["combined_confidence"]
        assert domain_conf > base_conf, (
            f"Career domain bonus should increase confidence: {domain_conf} vs {base_conf}"
        )

    def test_no_bonus_for_irrelevant_technique(self):
        """Transit has no Career bonus — confidence should equal base."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Transit", "2027-03-01", "2027-03-20",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Saju", "Da Yun", "2027-03-05", "2027-03-25",
            "Career", 10, ["Saturn"],
        ))
        # Da Yun has no Career bonus, Transit has no Career bonus
        base = vm.find_convergences()
        results = vm.query_temporal_clusters(["Career"])
        assert len(base) >= 1 and len(results) >= 1
        # Da Yun has no Career bonus → same as base
        assert base[0]["combined_confidence"] == results[0]["combined_confidence"], (
            "Techniques without Career bonuses should have identical confidence"
        )

    def test_tier_ceiling_with_domain_bonus(self):
        """Shadbala (base 0.72) + Career bonus (0.10) = 0.82, which clears
        the 0.75 tier ceiling threshold."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Vedic", "Shadbala", "2027-05-01", "2027-05-20",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Western", "Transit", "2027-05-05", "2027-05-25",
            "Career", 10, ["Saturn"],
        ))
        # Base: Shadbala=0.72, Transit=0.65 → both < 0.75, capped at 0.74
        base = vm.find_convergences()
        assert len(base) >= 1
        assert base[0]["combined_confidence"] == 0.74, (
            f"Without bonus, should be capped at 0.74, got {base[0]['combined_confidence']}"
        )

        # Career query: Shadbala 0.72+0.10=0.82 (>= 0.75), Transit stays 0.65
        results = vm.query_temporal_clusters(["Career"])
        assert len(results) >= 1
        assert results[0]["combined_confidence"] > 0.74, (
            f"Domain bonus should uncap Shadbala past tier ceiling, got {results[0]['combined_confidence']}"
        )

    def test_original_events_not_mutated(self):
        """query_temporal_clusters must not modify original event confidences."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Vedic", "Vimshottari Dasha", "2027-03-05", "2027-03-25",
            "Career", 10, ["Saturn"],
        ))
        vm.add_prediction(_make_event(
            "Western", "Primary Direction", "2027-03-01", "2027-03-20",
            "Career", 10, ["Saturn"],
        ))
        # Record original confidences
        orig_confidences = [e.confidence for e in vm.events]

        # Run domain query (applies bonuses internally)
        vm.query_temporal_clusters(["Career"])

        # Verify originals unchanged
        for i, e in enumerate(vm.events):
            assert e.confidence == orig_confidences[i], (
                f"Event {i} confidence mutated: {e.confidence} vs {orig_confidences[i]}"
            )

    def test_identity_domain_bonus(self):
        """Primary Direction should get bonus for Identity domain."""
        vm = ValidationMatrix()
        vm.add_prediction(_make_event(
            "Western", "Primary Direction", "2027-03-01", "2027-03-20",
            "Identity", 1, ["Sun"],
        ))
        vm.add_prediction(_make_event(
            "Vedic", "Transit", "2027-03-05", "2027-03-25",
            "Identity", 1, ["Sun"],
        ))
        base = vm.find_convergences()
        results = vm.query_temporal_clusters(["Identity", "Self", "Personality"])
        assert len(base) >= 1 and len(results) >= 1
        assert results[0]["combined_confidence"] >= base[0]["combined_confidence"], (
            "Primary Direction should get Identity domain bonus"
        )

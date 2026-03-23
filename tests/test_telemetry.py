"""Tests for core/telemetry.py — cost tracking.

Phase 1.7: Validates cost calculation, ContextVar isolation, and summary output.
"""
import pytest
from core.telemetry import (
    CostTracker, init_cost_tracker, get_cost_tracker, _estimate_cost,
)


class TestCostEstimation:
    """Verify cost calculation against known pricing."""

    def test_gemini_pro_cost(self):
        """gemini-2.5-pro: $1.25/1M input, $10.00/1M output."""
        cost = _estimate_cost("gemini-2.5-pro", 1_000_000, 1_000_000)
        assert abs(cost - 11.25) < 0.01

    def test_gemini_flash_cost(self):
        """gemini-2.5-flash: $0.15/1M input, $0.60/1M output."""
        cost = _estimate_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
        assert abs(cost - 0.75) < 0.01

    def test_zero_tokens(self):
        cost = _estimate_cost("gemini-2.5-pro", 0, 0)
        assert cost == 0.0

    def test_unknown_model_uses_default(self):
        """Unknown models should use default pricing."""
        cost = _estimate_cost("unknown-model", 1_000_000, 1_000_000)
        # Default: $1.00 input + $5.00 output = $6.00
        assert abs(cost - 6.0) < 0.01

    def test_small_call_cost(self):
        """Typical expert call: ~2000 input, ~500 output with flash."""
        cost = _estimate_cost("gemini-2.5-flash", 2000, 500)
        expected = (2000 * 0.15 + 500 * 0.60) / 1_000_000
        assert abs(cost - expected) < 0.0001


class TestCostTracker:
    """CostTracker recording and summary."""

    def test_record_and_summary(self):
        tracker = CostTracker(request_id="test-1")
        tracker.record("gemini-2.5-flash", 1000, 500, phase="expert")
        tracker.record("gemini-2.5-pro", 2000, 1000, phase="archon")

        summary = tracker.summary()
        assert summary["total_calls"] == 2
        assert summary["total_input_tokens"] == 3000
        assert summary["total_output_tokens"] == 1500
        assert summary["total_tokens"] == 4500
        assert summary["total_cost_usd"] > 0
        assert "expert" in summary["by_phase"]
        assert "archon" in summary["by_phase"]

    def test_empty_tracker(self):
        tracker = CostTracker()
        summary = tracker.summary()
        assert summary["total_calls"] == 0
        assert summary["total_cost_usd"] == 0

    def test_phase_aggregation(self):
        tracker = CostTracker()
        tracker.record("gemini-2.5-flash", 1000, 500, phase="expert")
        tracker.record("gemini-2.5-flash", 1000, 500, phase="expert")
        tracker.record("gemini-2.5-pro", 2000, 1000, phase="archon")

        summary = tracker.summary()
        assert summary["by_phase"]["expert"]["calls"] == 2
        assert summary["by_phase"]["archon"]["calls"] == 1

    def test_model_aggregation(self):
        tracker = CostTracker()
        tracker.record("gemini-2.5-flash", 1000, 500, phase="expert")
        tracker.record("gemini-2.5-pro", 2000, 1000, phase="archon")

        summary = tracker.summary()
        assert "gemini-2.5-flash" in summary["by_model"]
        assert "gemini-2.5-pro" in summary["by_model"]


class TestContextVarIsolation:
    """Verify per-request isolation via ContextVar."""

    def test_init_sets_tracker(self):
        tracker = init_cost_tracker(request_id="ctx-1")
        retrieved = get_cost_tracker()
        assert retrieved is tracker
        assert retrieved.request_id == "ctx-1"

    def test_new_init_replaces_old(self):
        t1 = init_cost_tracker(request_id="old")
        t2 = init_cost_tracker(request_id="new")
        assert get_cost_tracker() is t2
        assert get_cost_tracker().request_id == "new"

    def test_recording_goes_to_current_tracker(self):
        t1 = init_cost_tracker(request_id="user-a")
        t1.record("gemini-2.5-flash", 100, 50, phase="expert")

        t2 = init_cost_tracker(request_id="user-b")
        t2.record("gemini-2.5-pro", 200, 100, phase="archon")

        # t1 should still have its own records
        assert len(t1.calls) == 1
        assert t1.calls[0].phase == "expert"

        # t2 should have its own records
        assert len(t2.calls) == 1
        assert t2.calls[0].phase == "archon"

        # Current context should point to t2
        assert get_cost_tracker() is t2

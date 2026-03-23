"""LLM cost telemetry with per-request isolation.

Phase 1.3: Tracks token usage and cost across all LLM calls in a report.

Uses ContextVar for async-safe, per-request isolation:
- Each request handler creates a fresh CostTracker and stores it in the contextvar.
- All downstream gateway calls read from the contextvar.
- asyncio automatically copies contextvars per-task, preventing cost bleed
  between concurrent users on the same event loop.

Usage:
    from core.telemetry import CostTracker, init_cost_tracker, get_cost_tracker

    # At request start:
    tracker = init_cost_tracker(request_id="abc-123")

    # In gateway after each call:
    tracker = get_cost_tracker()
    tracker.record(model="gemini-2.5-pro", input_tokens=1000, output_tokens=500, phase="expert")

    # At request end:
    summary = tracker.summary()
"""
import time
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Pricing table (USD per 1M tokens) ──────────────────────────────────────
# Updated 2026-03. Prices from Gemini API docs.
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-flash-lite": {"input": 0.05, "output": 0.20},
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
}

# Fallback for unknown models
DEFAULT_PRICING = {"input": 1.00, "output": 5.00}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a single LLM call."""
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return round(cost, 6)


@dataclass
class LLMCallRecord:
    """Single LLM API call record."""
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    phase: str  # "expert", "arbiter", "archon", "translation"
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class CostTracker:
    """Per-request cost and token usage tracker."""

    def __init__(self, request_id: str = ""):
        self.request_id = request_id
        self.calls: List[LLMCallRecord] = []
        self._start_time = time.time()

    def record(self,
               model: str,
               input_tokens: int,
               output_tokens: int,
               phase: str = "unknown",
               latency_ms: float = 0.0) -> None:
        """Record a single LLM call."""
        cost = _estimate_cost(model, input_tokens, output_tokens)
        record = LLMCallRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            phase=phase,
            latency_ms=latency_ms,
        )
        self.calls.append(record)
        logger.info(
            f"LLM call: {model} | {input_tokens}+{output_tokens} tokens | "
            f"${cost:.4f} | phase={phase}",
            extra={"model": model, "tokens": input_tokens + output_tokens,
                   "cost_usd": cost, "phase": phase, "latency_ms": latency_ms},
        )

    def summary(self) -> Dict[str, Any]:
        """Return aggregate cost/token summary for the request."""
        total_input = sum(c.input_tokens for c in self.calls)
        total_output = sum(c.output_tokens for c in self.calls)
        total_cost = sum(c.cost_usd for c in self.calls)
        elapsed = time.time() - self._start_time

        # Per-phase breakdown
        phase_costs: Dict[str, float] = {}
        phase_calls: Dict[str, int] = {}
        for c in self.calls:
            phase_costs[c.phase] = phase_costs.get(c.phase, 0) + c.cost_usd
            phase_calls[c.phase] = phase_calls.get(c.phase, 0) + 1

        # Per-model breakdown
        model_costs: Dict[str, float] = {}
        for c in self.calls:
            model_costs[c.model] = model_costs.get(c.model, 0) + c.cost_usd

        return {
            "request_id": self.request_id,
            "total_calls": len(self.calls),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost_usd": round(total_cost, 4),
            "elapsed_seconds": round(elapsed, 1),
            "by_phase": {
                phase: {"calls": phase_calls[phase], "cost_usd": round(cost, 4)}
                for phase, cost in phase_costs.items()
            },
            "by_model": {
                model: round(cost, 4)
                for model, cost in model_costs.items()
            },
        }


# ── ContextVar-based per-request isolation ─────────────────────────────────
_cost_tracker: ContextVar[Optional[CostTracker]] = ContextVar("cost_tracker", default=None)


def init_cost_tracker(request_id: str = "") -> CostTracker:
    """Create and set a fresh CostTracker for the current context."""
    tracker = CostTracker(request_id=request_id)
    _cost_tracker.set(tracker)
    return tracker


def get_cost_tracker() -> Optional[CostTracker]:
    """Get the CostTracker for the current context, or None."""
    return _cost_tracker.get()

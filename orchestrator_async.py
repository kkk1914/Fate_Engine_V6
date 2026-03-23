"""Async orchestration layer — Phase 2.2.

Wraps the sync FatesOrchestrator with async I/O patterns:
  - Layer 1 (Calculations): CPU-bound swe calls run in thread pool via asyncio.to_thread()
  - Layer 2 (Experts): 4 concurrent async LLM calls via asyncio.gather()
  - Layer 3 (Arbiter): Single async structured_generate call
  - Layer 4 (Archon): Section generation runs in thread pool (archon uses sync gateway internally)
  - Layer 5 (Save): File I/O via asyncio.to_thread()

The sync orchestrator.py is preserved for CLI usage. This module is used
exclusively by the FastAPI endpoint (api/main.py).

Key insight: "Sequential Compute, Concurrent Network"
  - swe calculations (~2-5s) CANNOT be parallelized within a process (global C state)
  - LLM calls (~60-120s) CAN and SHOULD be concurrent
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

from config import settings
from core.logging_config import set_request_id, get_request_id
from core.telemetry import init_cost_tracker, get_cost_tracker
from core.storage import get_storage, LocalStorage
from experts.gateway_async import async_gateway

logger = logging.getLogger(__name__)


class AsyncFatesOrchestrator:
    """Async wrapper that uses sync calculation engine + async LLM calls."""

    def __init__(self):
        # Import sync orchestrator lazily to share calculation engines
        from orchestrator import FatesOrchestrator
        self._sync = FatesOrchestrator()

    @property
    def last_degraded_systems(self) -> List[str]:
        return self._sync.last_degraded_systems

    @property
    def last_cost_summary(self) -> Dict[str, Any]:
        return self._sync.last_cost_summary

    async def generate_report_async(
        self,
        birth_datetime: str,
        location: str,
        gender: str = "unspecified",
        name: str = "Unknown",
        output_dir: str = "./reports",
        lat: float = None,
        lon: float = None,
        user_questions: list = None,
        language: str = None,
    ) -> str:
        """Generate complete report with async LLM calls.

        Returns path to the saved English report.
        """
        if language is None:
            language = settings.report_language
        self._sync.last_degraded_systems = []
        self._sync.last_cost_summary = {}

        # Phase 1.2: Request-scoped tracing
        request_id = set_request_id()
        logger.info("Async report generation started", extra={"phase": "init"})

        # Phase 1.3: Per-request cost tracking
        init_cost_tracker(request_id=request_id)

        t_start = time.time()
        print(f"🔮 Fates Engine v{settings.engine_version} [ASYNC]: Initializing...")
        print(f"   Subject: {name}")
        print(f"   Birth: {birth_datetime}")
        print(f"   Location: {location}")

        # ── Layer 1: Calculations (CPU-bound → thread pool) ───────────────
        print("\n📊 Layer 1: Mathematical Calculations (async offloaded to thread)...")
        chart_data = await asyncio.to_thread(
            self._sync._calculate_charts,
            birth_datetime, location, gender, lat=lat, lon=lon,
        )

        # Pydantic validation at boundary — Option B (defensive):
        # overwrite raw dict with validated/coerced model, never abort report.
        from core.models import ChartData
        try:
            validated_model = ChartData.validate_chart(chart_data)
            chart_data = validated_model.model_dump(exclude_unset=True)
        except Exception as e:
            logger.warning(f"Chart data validation warning: {e}")
            chart_data["validation_warnings"] = str(e)

        # House lords (deterministic, fast)
        from orchestrator import _compute_house_lords
        chart_data["house_lords"] = _compute_house_lords(chart_data)

        print("   ✓ All 4 base systems calculated")

        # ── Layer 2a: Prediction rules (CPU-bound, fast) ──────────────────
        print("\n🧠 Layer 2a: Deterministic Prediction Rules...")
        from core.prediction_rules import PredictionRulesEngine
        rules_engine = PredictionRulesEngine(chart_data)
        rule_events = rules_engine.run_all_rules()

        # ── Layer 2b: Validation Matrix ───────────────────────────────────
        print("\n⚖️  Layer 2b: Algorithmic Reconciliation...")
        from synthesis.validation_matrix import ValidationMatrix
        validation_matrix = ValidationMatrix()
        events = self._sync._extract_prediction_events(chart_data)
        events.extend(rule_events)
        for event in events:
            validation_matrix.add_prediction(event)

        convergences = validation_matrix.find_convergences(tolerance_days=30)
        contradictions = validation_matrix.find_contradictions()
        from orchestrator import _convergences_to_clusters
        clusters = _convergences_to_clusters(convergences, chart_data["meta"]["jd"])

        print(f"   ✓ {len(convergences)} convergences, {len(contradictions)} contradictions")

        # ── Layer 3: Expert Swarm (4 concurrent async LLM calls) ──────────
        print("\n🎭 Layer 3: Expert Swarm Analysis (async concurrent)...")
        analyses = await self._gather_experts_async(
            chart_data, convergences, contradictions, user_questions,
        )
        print(f"   ✓ All 4 experts completed")

        # ── Layer 4: Arbiter synthesis ────────────────────────────────────
        print("\n🌐 Layer 4: Cross-System Synthesis...")
        synthesis = await asyncio.to_thread(
            self._sync.arbiter.reconcile,
            analyses, chart_data,
            convergences=convergences,
            contradictions=contradictions,
            temporal_clusters=clusters,
            user_questions=user_questions,
        )

        verdict_ledger = self._sync._build_verdict_ledger(synthesis)
        from synthesis.citation_chain import build_citation_chains
        citation_data = build_citation_chains(convergences, contradictions, top_n=10)

        # ── Layer 5: Archon report generation (thread pool — uses sync gateway) ──
        print("\n📜 Layer 5: Archon Generating Report...")
        metadata = {
            "name": name,
            "location": location,
            "birth_time": birth_datetime,
            "birth_year": chart_data.get("meta", {}).get("birth_year"),
        }

        original_questions = None
        english_questions = user_questions
        if user_questions and language == "my":
            english_questions, original_questions = self._sync._detect_and_translate_questions(user_questions)

        query_context = None
        if english_questions:
            from query_engine import build_query_context
            clean_qs = [q.strip() for q in english_questions if q and q.strip()][:5]
            if clean_qs:
                query_context = build_query_context(clean_qs)

        report_dict = await asyncio.to_thread(
            self._sync.archon.generate_report,
            synthesis, chart_data, metadata,
            temporal_clusters=clusters,
            user_questions=english_questions,
            query_context=query_context,
            expert_analyses=analyses,
            language=language,
            original_questions=original_questions,
            verdict_ledger=verdict_ledger,
            citation_data=citation_data,
            validation_matrix=validation_matrix,
        )

        # ── Layer 6: Save ─────────────────────────────────────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')

        storage = get_storage()
        if isinstance(storage, LocalStorage):
            storage.base_dir = output_dir

        en_report = report_dict.get("en", "")
        en_filename = f"master_report_v2_{safe_name}_{timestamp}_en.md"
        en_filepath = await asyncio.to_thread(storage.save_report, en_filename, en_report)

        cost_tracker = get_cost_tracker()
        cost_summary = cost_tracker.summary() if cost_tracker else {}
        self._sync.last_cost_summary = cost_summary

        elapsed = time.time() - t_start
        print(f"\n✨ Complete! ({elapsed:.1f}s)")
        print(f"   English report: {en_filepath}")
        print(f"   Length: {len(en_report):,} characters")
        if cost_summary:
            print(f"   Cost: ${cost_summary.get('total_cost_usd', 0):.4f}")
            print(f"   Tokens: {cost_summary.get('total_tokens', 0):,}")

        if "my" in report_dict:
            my_report = report_dict["my"]
            my_filename = f"master_report_v2_{safe_name}_{timestamp}_my.md"
            await asyncio.to_thread(storage.save_report, my_filename, my_report)
            print(f"   Burmese report: {len(my_report):,} characters")

        logger.info(f"Async report complete in {elapsed:.1f}s", extra={"phase": "complete"})
        return en_filepath

    async def _gather_experts_async(
        self,
        chart_data: Dict,
        convergences: list,
        contradictions: list,
        user_questions: list = None,
    ) -> list:
        """Run 4 experts concurrently using async gateway.

        Each expert.analyze() uses the sync gateway internally. We offload
        each to a thread so they run concurrently without blocking the event loop.
        """
        # Inject validation + house lord data (same as sync version)
        chart_data["validation"] = {
            "convergences": convergences[:10] if convergences else [],
            "contradictions": contradictions[:5] if contradictions else [],
            "convergence_summary": self._sync._build_convergence_summary(convergences),
        }

        hl = chart_data.get("house_lords", {})
        w_lords = hl.get("western_lords", {})
        v_lords = hl.get("vedic_lords", {})
        bazi_el = hl.get("bazi_elements", {})
        lord_lines = ["=== MANDATORY HOUSE LORD REFERENCE (computed from chart cusps) ===",
                      "DO NOT invent house lords. Use ONLY these values:", ""]
        if w_lords:
            lord_lines.append("WESTERN (Tropical Placidus):")
            for h in range(1, 13):
                lord_lines.append(f"  House {h} lord = {w_lords.get(h, '?')}")
        if v_lords:
            lord_lines.append("\nVEDIC (Sidereal Whole Sign):")
            for h in range(1, 13):
                lord_lines.append(f"  House {h} lord = {v_lords.get(h, '?')}")
        if bazi_el.get("day_master_element"):
            lord_lines.append(f"\nBAZI ELEMENT RELATIONS (Day Master: {bazi_el['day_master_element']}):")
            for role in ["Output", "Wealth", "Power", "Resource", "Companion"]:
                lord_lines.append(f"  {role} = {bazi_el.get(role, '?')}")
        lord_lines.append("=== END HOUSE LORD REFERENCE ===")
        chart_data["_house_lord_reference_block"] = "\n".join(lord_lines)

        experts = [
            ("Western", self._sync.western_expert),
            ("Vedic", self._sync.vedic_expert),
            ("Saju", self._sync.saju_expert),
            ("Hellenistic", self._sync.hellenistic_expert),
        ]

        async def _run_expert(name: str, expert) -> dict:
            """Run a single expert in a thread (expert uses sync gateway)."""
            print(f"   Analyzing with {name} Expert...")
            for attempt in range(2):
                try:
                    result = await asyncio.to_thread(
                        expert.analyze, chart_data, "natal",
                        user_questions=user_questions,
                    )
                    if result.get("analysis"):
                        return result
                    logger.warning(f"{name} Expert empty (attempt {attempt + 1})")
                except Exception as e:
                    logger.error(f"{name} Expert failed (attempt {attempt + 1}): {e}")
                    if attempt == 0:
                        print(f"   ⚠️  {name} Expert failed — retrying...")

            logger.error(f"{name} Expert failed after retries")
            return {
                "system": name, "mode": "natal",
                "analysis": f"[{name} expert analysis unavailable]",
                "confidence": 0.0, "model_used": "fallback", "degraded": True,
            }

        # Run all 4 experts concurrently
        results = await asyncio.gather(
            *[_run_expert(name, expert) for name, expert in experts]
        )
        return list(results)


# Global async orchestrator instance
async_orchestrator = AsyncFatesOrchestrator()

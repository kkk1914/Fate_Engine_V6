"""Main orchestration layer - Version 2 with Primary Directions, Ashtakavarga, and Validation Matrix."""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import logging
import threading

logger = logging.getLogger(__name__)
import swisseph as swe
import os

# Phase 1 modules
from core.logging_config import set_request_id, get_request_id
from core.geocoder import geocoder
from core.storage import get_storage, LocalStorage
from core.telemetry import init_cost_tracker, get_cost_tracker

# Swiss Ephemeris is a C-library wrapper with ONE global memory space.
# swe.set_sid_mode(), swe.set_ephe_path(), swe.set_topo() etc. all mutate
# process-wide C state. Separate per-system locks do NOT protect this shared
# state — a sidereal thread calling set_sid_mode() while a tropical thread
# reads calc_ut() can corrupt positions silently.
#
# SINGLE GLOBAL LOCK: All swe calls serialize under one lock. This eliminates
# an entire class of silent data corruption. The ~2-4s added latency is
# negligible vs. the 60-90s LLM call phase.
#
# For true parallelism between systems, use ProcessPoolExecutor (Phase 2.4)
# which gives each process its own copy of the C library's global state.
_swe_lock = threading.Lock()

# Core mathematical engines
from core.ephemeris import ephe
from core.primary_directions import PrimaryDirections
from core.solar_return import SolarReturnEngine
from core.tajaka import TajakaEngine
from core.vedic_engines import AshtakavargaEngine, DivisionalCharts
from core.house_lords import HouseLordMapper
from core.lunar_return import LunarReturnEngine
from core.syzygy import SyzygyEngine
from core.essential_dignities import EssentialDignities
from core.dodecatemoria import DodecatemoriaEngine  # Phase 5

# System calculation engines
from systems.western import WesternEngine
from systems.hellenistic import HellenisticEngine
from systems.vedic import calculate_vedic
from systems.saju import calculate_bazi

# Expert analysis layer
from experts.western_expert import WesternExpert
from experts.vedic_expert import VedicExpert
from experts.saju_expert import SajuExpert
from experts.hellenistic_expert import HellenisticExpert

# Synthesis layer
from synthesis.validation_matrix import ValidationMatrix, PredictionEvent
# TemporalAligner deleted — convergences flow directly from ValidationMatrix
from synthesis.arbiter import Arbiter
from synthesis.archon import Archon
from query_engine import build_query_context
from config import settings


# ── Deterministic House Lord Computation ─────────────────────────────────────
# These are computed once from chart cusps and injected into expert prompts
# so LLMs CANNOT fabricate house lords.

_SIGN_RULER_WESTERN = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Pluto", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Uranus", "Pisces": "Neptune",
}
# Traditional rulers (no outer planets) — used when traditional context needed
_SIGN_RULER_WESTERN_TRAD = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}
_SIGN_RULER_VEDIC = {
    "Mesha": "Mars", "Vrishabha": "Venus", "Mithuna": "Mercury",
    "Karka": "Moon", "Simha": "Sun", "Kanya": "Mercury",
    "Tula": "Venus", "Vrischika": "Mars", "Dhanus": "Jupiter",
    "Makara": "Saturn", "Kumbha": "Saturn", "Meena": "Jupiter",
}

# Bazi: Day Master → Five Element Relations
# Relations: Output, Wealth, Power, Resource, Companion
_BAZI_ELEMENT_RELATIONS = {
    "Wood":  {"Output": "Fire",  "Wealth": "Earth", "Power": "Metal", "Resource": "Water", "Companion": "Wood"},
    "Fire":  {"Output": "Earth", "Wealth": "Metal", "Power": "Water", "Resource": "Wood",  "Companion": "Fire"},
    "Earth": {"Output": "Metal", "Wealth": "Water", "Power": "Wood",  "Resource": "Fire",  "Companion": "Earth"},
    "Metal": {"Output": "Water", "Wealth": "Wood",  "Power": "Fire",  "Resource": "Earth", "Companion": "Metal"},
    "Water": {"Output": "Wood",  "Wealth": "Fire",  "Power": "Earth", "Resource": "Metal", "Companion": "Water"},
}


def _datetime_to_jd(dt) -> float:
    """Convert datetime to Julian Day."""
    from datetime import timezone as tz
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz.utc)
    # J2000.0 epoch: 2000-01-01T12:00:00 UTC = JD 2451545.0
    j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=tz.utc)
    delta = dt - j2000
    return 2451545.0 + delta.total_seconds() / 86400.0


def _convergences_to_clusters(convergences: list, natal_jd: float) -> list:
    """Convert ValidationMatrix convergences to the cluster format archon expects.

    Maps: convergence_date → center_jd, combined_confidence → convergence_score,
    systems → systems_involved, etc.
    """
    from datetime import timezone as tz

    clusters = []
    now_jd = _datetime_to_jd(datetime.now(tz.utc))

    for conv in convergences:
        center_dt = conv["convergence_date"]
        center_jd = _datetime_to_jd(center_dt)

        # Derive start/end from event date ranges
        all_starts = [e.date_range[0] for e in conv["events"]]
        all_ends = [e.date_range[1] for e in conv["events"]]
        start_jd = _datetime_to_jd(min(all_starts))
        end_jd = _datetime_to_jd(max(all_ends))

        score = conv["combined_confidence"]

        # Confidence labels matching archon's expectations
        if score >= 0.85:
            label, light = "NEAR-CERTAIN", "🔴"
        elif score >= 0.75:
            label, light = "HIGH-CONFIDENCE", "🟠"
        elif score >= 0.55:
            label, light = "MODERATE-CONFIDENCE", "🟡"
        else:
            label, light = "LOW-CONFIDENCE", "🟢"

        # Long-range decay
        years_ahead = (center_jd - now_jd) / 365.25
        long_range_decayed = years_ahead > 4

        # Convert PredictionEvent objects to dicts for archon formatters
        event_dicts = []
        for e in conv["events"]:
            event_dicts.append({
                "system": e.system,
                "technique": e.technique,
                "description": e.description,
                "confidence": e.confidence,
                "jd": _datetime_to_jd(e.date_range[0]),
            })

        clusters.append({
            "start_jd": start_jd,
            "end_jd": end_jd,
            "events": event_dicts,
            "systems_involved": conv["systems"],
            "techniques_involved": conv.get("techniques", []),
            "intensity": len(conv["events"]),
            "n_systems": conv["intensity"],
            "multi_system": conv["intensity"] >= 2,
            "avg_confidence": score,
            "convergence_score": score,
            "confidence_label": label,
            "stoplight": light,
            "long_range_decayed": long_range_decayed,
            "center_jd": center_jd,
        })

    clusters.sort(key=lambda c: c["convergence_score"], reverse=True)
    return clusters


def _compute_house_lords(chart_data: Dict) -> Dict[str, Any]:
    """
    Compute ACTUAL house lords from chart cusps (not natural rulerships).

    Returns a dict with:
        western_lords:  {1: "Mercury", 2: "Moon", ...}  based on sign on each cusp
        vedic_lords:    {1: "Venus", 2: "Mercury", ...}  based on sidereal sign on cusp
        bazi_elements:  {"Day Master": "Wood", "Output": "Fire", "Wealth": "Earth", ...}
    """
    result = {}

    # ── Western House Lords ──────────────────────────────────────────────
    w_houses = chart_data.get("western", {}).get("natal", {}).get("houses", {})
    western_lords = {}
    for i in range(1, 13):
        h = w_houses.get(f"House_{i}", {})
        sign = h.get("sign", "")
        if sign:
            western_lords[i] = _SIGN_RULER_WESTERN.get(sign, "Unknown")
    result["western_lords"] = western_lords

    # ── Vedic House Lords (Whole Sign from Ascendant) ────────────────────
    v_natal = chart_data.get("vedic", {}).get("natal", {})
    vedic_lords = {}
    # Vedic whole sign: Ascendant sign = House 1
    asc_sign_v = v_natal.get("ascendant_sign", "")
    if asc_sign_v:
        vedic_signs = list(_SIGN_RULER_VEDIC.keys())
        try:
            asc_idx = vedic_signs.index(asc_sign_v)
            for i in range(12):
                sign = vedic_signs[(asc_idx + i) % 12]
                vedic_lords[i + 1] = _SIGN_RULER_VEDIC[sign]
        except ValueError:
            logger.warning(f"Vedic ascendant sign '{asc_sign_v}' not recognized")
    result["vedic_lords"] = vedic_lords

    # ── Bazi Element Relations ───────────────────────────────────────────
    bazi = chart_data.get("bazi", {})
    day_master_element = bazi.get("day_master", {}).get("element", "")
    bazi_elements = {"day_master_element": day_master_element}
    if day_master_element in _BAZI_ELEMENT_RELATIONS:
        bazi_elements.update(_BAZI_ELEMENT_RELATIONS[day_master_element])
    result["bazi_elements"] = bazi_elements

    # ── House System Reconciliation Warnings ─────────────────────────────
    # Flag planets whose house differs between Placidus (Western) and
    # Whole Sign (Hellenistic/Vedic) so experts can address discrepancies.
    w_placements = chart_data.get("western", {}).get("natal", {}).get("placements", {})
    h_natal = chart_data.get("hellenistic", {}).get("natal", {})
    h_placements = h_natal.get("placements", {})
    discrepancies = []
    for planet in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"]:
        w_house = w_placements.get(planet, {}).get("house")
        h_house = h_placements.get(planet, {}).get("house")
        if w_house and h_house and w_house != h_house:
            discrepancies.append(
                f"{planet}: House {w_house} (Placidus) vs House {h_house} (Whole Sign)"
            )
    result["house_discrepancies"] = discrepancies
    if discrepancies:
        logger.info(f"House system discrepancies: {discrepancies}")

    return result


class FatesOrchestrator:
    """Coordinates calculation, analysis, and synthesis with V2 mathematical rigor."""

    def __init__(self):
        # Per-report tracking (set during generate_report)
        self.last_degraded_systems: List[str] = []
        self.last_cost_summary: Dict[str, Any] = {}

        # Traditional engines
        self.western_engine = WesternEngine()
        self.hellenistic_engine = HellenisticEngine()
        self.dignity_engine = EssentialDignities()

        # Expert LLM layer
        self.western_expert = WesternExpert()
        self.vedic_expert = VedicExpert()
        self.saju_expert = SajuExpert()
        self.hellenistic_expert = HellenisticExpert()

        # Synthesis layer
        self.arbiter = Arbiter()
        self.archon = Archon()

    @staticmethod
    def _detect_and_translate_questions(questions: list) -> tuple:
        """Detect Burmese input questions and translate to English.

        Returns:
            (english_questions, original_questions)
            If no Burmese detected, original_questions is None.
        """
        import re
        myanmar_pattern = re.compile(r'[\u1000-\u109F]')
        has_burmese = any(myanmar_pattern.search(q) for q in questions if q)
        if not has_burmese:
            return questions, None

        from experts.gateway import gateway
        original_questions = list(questions)
        english_questions = []
        for q in questions:
            if myanmar_pattern.search(q):
                resp = gateway.generate(
                    system_prompt=(
                        "You are a translator. Translate the following Burmese text "
                        "to English. Output ONLY the English translation, nothing else."
                    ),
                    user_prompt=q,
                    model="gemini-2.5-flash-lite",
                    max_tokens=500,
                    temperature=0.1,
                )
                if resp.get("success"):
                    english_questions.append(resp["content"].strip())
                    logger.info(f"Translated Burmese question: {q[:30]}... → {english_questions[-1][:50]}")
                else:
                    english_questions.append(q)  # fallback
            else:
                english_questions.append(q)
        return english_questions, original_questions

    def generate_report(self,
                       birth_datetime: str,
                       location: str,
                       gender: str = "unspecified",
                       name: str = "Unknown",
                       output_dir: str = "./reports",
                       lat: float = None,
                       lon: float = None,
                       user_questions: list = None,
                       language: str = None) -> str:
        """
        Generate complete master report with V2 predictive engines.
        user_questions: list of up to 5 question strings (optional).
          When provided, QueryEngine extracts themes and steers every section
          of the report toward what the user asked about, then adds a direct
          Q&A section (Part IV) with verdicts at the end.
        language: "en" or "my". If None, uses config setting.
        """
        if language is None:
            language = settings.report_language
        self.last_degraded_systems = []  # Reset per-report

        # Phase 1.2: Request-scoped tracing
        request_id = set_request_id()
        logger.info(f"Report generation started", extra={"phase": "init"})

        # Phase 1.3: Per-request cost tracking
        init_cost_tracker(request_id=request_id)

        # Phase 3.1: Generate deterministic report_id for idempotency
        import time as _time
        _t_start = _time.time()
        from core.report_metadata import generate_report_id, ReportMetadata, get_idempotency_cache
        report_id = generate_report_id(
            birth_datetime=birth_datetime, location=location,
            lat=lat, lon=lon, questions=user_questions,
        )
        logger.info(f"Report ID: {report_id}", extra={"report_id": report_id})

        # Check idempotency cache
        cache = get_idempotency_cache()
        cached = cache.get(report_id)
        if cached:
            logger.info(f"Returning cached report: {report_id}")
            self.last_cost_summary = {"total_cost_usd": cached.get("cost_usd", 0)}
            return cached["storage_path"]

        print(f"🔮 Fates Engine v{settings.engine_version}: Initializing Mathematical Core...")
        print(f"   Subject: {name}")
        print(f"   Birth: {birth_datetime}")
        print(f"   Location: {location}")

        # 1. Parse inputs and calculate charts (V2 with Primary Directions, Ashtakavarga, etc.)
        print("\n📊 Layer 1: Mathematical Calculations (4 systems + Vargas + Directions)...")
        chart_data = self._calculate_charts(birth_datetime, location, gender, lat=lat, lon=lon)

        # Phase 1.6: Validate chart_data structure at boundary
        # Option B (defensive): overwrite raw dict with validated/coerced model,
        # but never abort the report over a minor type mismatch.
        from core.models import ChartData
        try:
            validated_model = ChartData.validate_chart(chart_data)
            chart_data = validated_model.model_dump(exclude_unset=True)
            logger.info("Chart data validated against Pydantic schema")
        except Exception as e:
            logger.warning(f"Chart data validation warning: {e}")
            chart_data["validation_warnings"] = str(e)

        # ── Deterministic House Lord & Element Table ─────────────────────
        # Computed ONCE from cusps so LLMs cannot hallucinate lords/elements
        chart_data["house_lords"] = _compute_house_lords(chart_data)
        logger.info(f"House lords computed: W={chart_data['house_lords'].get('western_lords', {})}")

        print("   ✓ Western (Tropical) + Primary Directions + Solar Returns")
        print("   ✓ Vedic (Sidereal) + Full Ashtakavarga + Divisional Charts (D7,D9,D10,D12,D16,D30,D60)")
        print("   ✓ Saju (Bazi) + Da Yun")
        print("   ✓ Hellenistic + Zodiacal Releasing + Dodecatemoria")
        # Note: Event count will be displayed after extraction in Layer 2

        # 2a. Deterministic Prediction Rules Engine (NEW V3)
        print("\n🧠 Layer 2a: Deterministic Prediction Rules Engine...")
        from core.prediction_rules import PredictionRulesEngine
        rules_engine = PredictionRulesEngine(chart_data)
        rule_events = rules_engine.run_all_rules()
        print(f"   ✓ Generated {len(rule_events)} deterministic rule-based predictions")

        # 2b. Algorithmic Validation Matrix
        print("\n⚖️  Layer 2b: Algorithmic Reconciliation (Validation Matrix)...")
        validation_matrix = ValidationMatrix()

        # Extract all predictive events into standardized format
        events = self._extract_prediction_events(chart_data)
        # Add deterministic rule-based events
        events.extend(rule_events)
        for event in events:
            validation_matrix.add_prediction(event)

        # Find convergences and contradictions
        convergences = validation_matrix.find_convergences(tolerance_days=30)
        contradictions = validation_matrix.find_contradictions()

        print(f"   ✓ Processed {len(events)} predictions")
        print(f"   ✓ Found {len(convergences)} multi-system convergences")
        print(f"   ✓ Flagged {len(contradictions)} contradictions for resolution")

        # Convert ValidationMatrix convergences to cluster format for Archon
        clusters = _convergences_to_clusters(convergences, chart_data["meta"]["jd"])
        print(f"   ✓ Converted {len(clusters)} convergences to storm windows")

        # 3. Expert analysis (with validation data + question focus)
        print("\n🎭 Layer 3: Expert Swarm Analysis...")
        analyses = self._gather_expert_analyses(chart_data, convergences, contradictions,
                                                user_questions=user_questions)
        print(f"   ✓ Western Expert ({analyses[0].get('model_used')})")
        print(f"   ✓ Vedic Expert ({analyses[1].get('model_used')})")
        print(f"   ✓ Saju Expert ({analyses[2].get('model_used')})")
        print(f"   ✓ Hellenistic Expert ({analyses[3].get('model_used')})")

        # 4. Arbiter synthesis with pre-validated data + question focus
        print("\n🌐 Layer 4: Cross-System Synthesis...")
        synthesis = self.arbiter.reconcile(
            analyses,
            chart_data,
            convergences=convergences,
            contradictions=contradictions,
            temporal_clusters=clusters,
            user_questions=user_questions,
        )

        consensus_count = len(synthesis.get('consensus_points', []))
        critical_count = len(synthesis.get('critical_periods', []))
        print(f"   ✓ Synthesized {consensus_count} consensus themes")
        print(f"   ✓ Validated {critical_count} critical periods")

        # 4b. Build Verdict Ledger — binding constraint for all downstream sections
        verdict_ledger = self._build_verdict_ledger(synthesis)
        print(f"   ✓ Verdict Ledger: {len(verdict_ledger.get('entries', []))} binding predictions locked")

        # 4c. Build Evidence Citation Chains — traceable evidence for predictions
        from synthesis.citation_chain import build_citation_chains
        citation_data = build_citation_chains(convergences, contradictions, top_n=10)
        print(f"   ✓ Evidence Citation Chains: {len(convergences)} predictions with traceable evidence")

        # 5. Master narrative generation
        print("\n📜 Layer 5: Archon Generating Master Report...")
        metadata = {
            "name": name,
            "location": location,
            "birth_time": birth_datetime,
            "birth_year": chart_data.get("meta", {}).get("birth_year"),
        }

        # Build query context — steers every section toward user's questions
        # Detect Burmese input and translate if needed
        original_questions = None
        english_questions = user_questions
        if user_questions and language == "my":
            english_questions, original_questions = self._detect_and_translate_questions(user_questions)

        query_context = None
        if english_questions:
            clean_qs = [q.strip() for q in english_questions if q and q.strip()][:5]
            if clean_qs:
                query_context = build_query_context(clean_qs)
                themes = query_context.get("themes", [])
                print(f"   ✓ Query context built — {len(clean_qs)} questions, "
                      f"themes: {', '.join(themes) if themes else 'general'}")

        report_dict = self.archon.generate_report(
                   synthesis,
                   chart_data,
                   metadata,
                   temporal_clusters=clusters,
                   user_questions=english_questions,
                   query_context=query_context,
                   expert_analyses=analyses,
                   language=language,
                   original_questions=original_questions,
                   verdict_ledger=verdict_ledger,
                   citation_data=citation_data,
                   validation_matrix=validation_matrix)

        # 6. Save with storage backend (Phase 1.4)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')

        storage = get_storage()
        # For local storage, use output_dir as base; for cloud, subdir is output_dir
        if isinstance(storage, LocalStorage):
            storage.base_dir = output_dir

        # Always save English report
        en_report = report_dict.get("en", "")
        en_filename = f"master_report_v2_{safe_name}_{timestamp}_en.md"
        en_filepath = storage.save_report(en_filename, en_report)

        # Phase 1.3: Log cost summary
        cost_tracker = get_cost_tracker()
        cost_summary = cost_tracker.summary() if cost_tracker else {}

        print(f"\n✨ Complete! Report generated with V2 mathematical precision.")
        print(f"   English report: {en_filepath}")
        print(f"   Length: {len(en_report):,} characters")
        print(f"   Convergences detected: {len(convergences)}")
        if cost_summary:
            print(f"   Total cost: ${cost_summary.get('total_cost_usd', 0):.4f}")
            print(f"   Total tokens: {cost_summary.get('total_tokens', 0):,}")
            print(f"   LLM calls: {cost_summary.get('total_calls', 0)}")

        # Save Burmese report if generated
        if "my" in report_dict:
            my_report = report_dict["my"]
            my_filename = f"master_report_v2_{safe_name}_{timestamp}_my.md"
            my_filepath = storage.save_report(my_filename, my_report)
            print(f"   Burmese report: {my_filepath}")
            print(f"   Length: {len(my_report):,} characters")

        # Store cost summary for API access
        self.last_cost_summary = cost_summary

        # Phase 3.1: Save metadata and cache for idempotency
        elapsed = _time.time() - _t_start
        meta = ReportMetadata(
            report_id=report_id,
            engine_version=settings.engine_version,
            generation_time_seconds=round(elapsed, 1),
            cost_usd=cost_summary.get("total_cost_usd", 0),
            total_tokens=cost_summary.get("total_tokens", 0),
            total_llm_calls=cost_summary.get("total_calls", 0),
            input_params={"birth_datetime": birth_datetime, "location": location,
                          "name": name, "gender": gender},
            degraded_systems=self.last_degraded_systems,
        )
        meta.save_alongside(en_filepath)
        cache.set(report_id, en_filepath, meta.to_dict())
        self.last_report_id = report_id

        logger.info(f"Report generation complete", extra={"phase": "complete"})
        return en_filepath

    def _calculate_charts(self, birth_dt: str, location: str, gender: str, lat: float = None, lon: float = None, time_known: bool = True) -> Dict:
        """Calculate all systems with V2 mathematical engines.

        time_known=False activates birth-time-unknown mode:
          • Houses, Ascendant, MC, house-based techniques are suppressed.
          • Whole-sign placeholders are used for house-sensitive engines.
          • Hellenistic (ZR, Profections) and Fixed Star Parans are skipped.
          • All planet-only calculations (aspects, dashas, transits) still run.

        The engine auto-detects unknown time when birth_dt time is "00:00" or
        when the string contains the literal word 'unknown'.
        """
        # Auto-detect unknown birth time
        _lower = birth_dt.lower()
        if "unknown" in _lower or "00:00" in birth_dt:
            time_known = False
            logger.info("Birth-time-unknown mode activated — house-sensitive techniques suppressed")

        # Parse datetime
        dt = None
        parse_error = None
        _s = birth_dt.strip()

        # Strategy 1: split on space — handles "YYYY-MM-DD HH:MM" and variants
        if dt is None and ' ' in _s:
            try:
                _date, _time = _s.split(' ', 1)
                _h, _m = map(int, _time.split(':')[:2])
                # Try YYYY-MM-DD first, then DD-MM-YYYY, then MM-DD-YYYY
                for _sep in ('-', '/'):
                    parts = _date.split(_sep)
                    if len(parts) == 3:
                        try:
                            _y, _mo, _d = int(parts[0]), int(parts[1]), int(parts[2])
                            if _y > 31:                            # YYYY-MM-DD (most common)
                                dt = datetime(_y, _mo, _d, _h, _m, 0, tzinfo=ZoneInfo("UTC"))
                            elif _d > 31:                          # DD-MM-YYYY
                                dt = datetime(_d, _mo, _y, _h, _m, 0, tzinfo=ZoneInfo("UTC"))
                            elif int(parts[1]) > 12:               # MM-DD-YYYY
                                dt = datetime(_d, _mo, _y, _h, _m, 0, tzinfo=ZoneInfo("UTC"))
                            else:                                   # ambiguous: assume YYYY first
                                dt = datetime(_y, _mo, _d, _h, _m, 0, tzinfo=ZoneInfo("UTC"))
                            break
                        except ValueError:
                            try:                                    # try DD-MM-YYYY fallback
                                _y2, _mo2, _d2 = int(parts[2]), int(parts[1]), int(parts[0])
                                dt = datetime(_y2, _mo2, _d2, _h, _m, 0, tzinfo=ZoneInfo("UTC"))
                                break
                            except ValueError:
                                continue
            except Exception as e:
                parse_error = str(e)

        # Strategy 2: fromisoformat (handles "YYYY-MM-DDTHH:MM:SS", "YYYY-MM-DD", etc.)
        if dt is None:
            try:
                _parsed = datetime.fromisoformat(_s.replace('Z', '+00:00'))
                dt = _parsed.replace(tzinfo=ZoneInfo("UTC")) if _parsed.tzinfo is None else _parsed.astimezone(ZoneInfo("UTC"))
            except Exception as e:
                parse_error = str(e)

        # Strategy 3: try common strptime formats
        if dt is None:
            for fmt in ("%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M", "%m/%d/%Y %H:%M",
                        "%d/%m/%Y %H:%M", "%Y/%m/%d %H:%M",
                        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
                try:
                    _parsed = datetime.strptime(_s, fmt)
                    dt = _parsed.replace(tzinfo=ZoneInfo("UTC"))
                    break
                except ValueError:
                    continue

        if dt is None:
            raise ValueError(
                f"Could not parse birth date/time: '{birth_dt}'\n"
                f"  Please use format: YYYY-MM-DD HH:MM  (e.g. 1990-03-15 14:30)\n"
                f"  Also accepted: DD-MM-YYYY HH:MM, DD/MM/YYYY HH:MM"
            )

        # Extract bare components used throughout _calculate_charts
        year   = dt.year
        month  = dt.month
        day    = dt.day
        hour   = dt.hour
        minute = dt.minute

        # Geocoding (Phase 1.1: cached via core.geocoder)
        if lat is not None and lon is not None:
            print(f"   📍 Using provided coordinates → {lat:.4f}, {lon:.4f}")
        else:
            lat, lon = geocoder.geocode(location)
            print(f"   📍 Geocoded '{location}' → {lat:.4f}, {lon:.4f}")

        # Validate lat/lon range (whether user-supplied or geocoded)
        if not (-90 <= lat <= 90):
            raise ValueError(f"Latitude {lat} out of range. Must be between -90 and 90.")
        if not (-180 <= lon <= 180):
            raise ValueError(f"Longitude {lon} out of range. Must be between -180 and 180.")

        # Julian Day
        jd = ephe.julian_day(dt)

        # Initialize predictive container
        predictive_events = []
        all_predictive = {}

        # ── PARALLEL BASE CALCULATIONS (Phase 2.4: ProcessPoolExecutor) ─────
        # Each system runs in its own process with isolated C-library state.
        # No _swe_lock needed — processes don't share memory.
        from concurrent.futures.process import BrokenProcessPool
        from core.compute_pool import (
            get_compute_pool,
            recycle_pool,
            _calculate_western_process,
            _calculate_vedic_process,
            _calculate_saju_process,
            _calculate_hellenistic_process,
        )

        print("   → Calculating all 4 systems in parallel (process pool)...")
        pool = get_compute_pool()
        ephe_path = settings.ephe_path

        _needs_recycle = False
        try:
            f_western     = pool.submit(_calculate_western_process, jd, lat, lon, time_known, year, ephe_path)
            f_vedic       = pool.submit(_calculate_vedic_process, jd, lat, lon, time_known, year, month, day, hour, minute, ephe_path, settings.ayanamsa)
            f_saju        = pool.submit(_calculate_saju_process, year, month, day, hour, minute, time_known, gender, jd, lon, ephe_path)
            f_hellenistic = pool.submit(_calculate_hellenistic_process, jd, lat, lon, time_known, year, ephe_path)
        except BrokenProcessPool:
            logger.critical("Process pool broken during submit — recycling")
            pool = recycle_pool(reason="BrokenProcessPool on submit")
            f_western     = pool.submit(_calculate_western_process, jd, lat, lon, time_known, year, ephe_path)
            f_vedic       = pool.submit(_calculate_vedic_process, jd, lat, lon, time_known, year, month, day, hour, minute, ephe_path, settings.ayanamsa)
            f_saju        = pool.submit(_calculate_saju_process, year, month, day, hour, minute, time_known, gender, jd, lon, ephe_path)
            f_hellenistic = pool.submit(_calculate_hellenistic_process, jd, lat, lon, time_known, year, ephe_path)

        # Collect results with individual timeout protection.
        # TimeoutError does NOT kill the hung process — it becomes a zombie.
        # If any worker zombies, flag for pool recycling after collection.
        def _safe_result(future, system_name: str, fallback: dict, timeout: int = 60):
            nonlocal _needs_recycle
            try:
                return future.result(timeout=timeout)
            except TimeoutError:
                logger.critical(
                    f"ZOMBIE WORKER: {system_name} process exceeded {timeout}s timeout. "
                    f"Worker is hung and will not be recovered. Pool recycle required."
                )
                _needs_recycle = True
                return fallback
            except BrokenProcessPool:
                logger.critical(f"BrokenProcessPool while collecting {system_name} result")
                _needs_recycle = True
                return fallback
            except Exception as e:
                logger.error(f"{system_name} calculation failed in process pool: {e}")
                return fallback

        western     = _safe_result(f_western, "Western", {"natal": {"placements": {}}, "predictive": {}})
        vedic       = _safe_result(f_vedic, "Vedic", {"natal": {"placements": {}}, "predictive": {}, "strength": {}})
        saju        = _safe_result(f_saju, "Saju", {"natal": {}, "strength": {}, "predictive": {}})
        hellenistic = _safe_result(f_hellenistic, "Hellenistic", {"lots": {}, "zodiacal_releasing": {}, "annual_profections": {}})

        # Recycle the pool if any worker zombied or the pool broke
        if _needs_recycle:
            recycle_pool(reason="worker timeout or broken pool during calculation")

        # Track which systems failed so downstream layers don't claim false convergence
        degradation_flags = {}
        if not vedic.get("natal", {}).get("placements"):
            degradation_flags["Vedic"] = "calculation_failed"
        if not saju.get("natal", {}).get("pillars"):
            degradation_flags["Saju"] = "calculation_failed"
        if not western.get("natal", {}).get("placements"):
            degradation_flags["Western"] = "calculation_failed"
        # Hellenistic returns data at top level (no "natal" wrapper)
        if not hellenistic.get("lots") and not hellenistic.get("zodiacal_releasing"):
            degradation_flags["Hellenistic"] = "calculation_failed"
        if degradation_flags:
            logger.error(f"System degradation: {degradation_flags}")

        # Surface degradation to instance for API access
        self.last_degraded_systems = list(degradation_flags.keys())

        print("   ✓ All 4 base systems calculated")

        # ── POST-PROCESSING (parallelized where safe) ─────────────────────
        # Group 1: swe-dependent engines (all serialize under _swe_lock)
        # Group 2: Essential Dignities (pure Python, no swe calls — truly parallel)
        # Group 3: Kakshya Transit (swe-dependent, serializes under _swe_lock)
        def _compute_tropical_chain():
            """All swe-dependent post-processing engines under global lock."""
            results = {}
            try:
                with _swe_lock:
                    # Primary Directions (Gold Standard)
                    print("   → Computing Primary Directions...")
                    pd_engine = PrimaryDirections(jd, lat, lon)
                    results["primary_dirs"] = pd_engine.get_critical_directions(years_ahead=15)

                    # Lunar Returns (15-year window) — guarded against degraded Western data
                    moon_data = western.get('natal', {}).get('placements', {}).get('Moon', {})
                    moon_lon = moon_data.get('longitude') if isinstance(moon_data, dict) else None
                    if moon_lon is not None:
                        print("   → Calculating Lunar Returns (15yr)...")
                        results["lunar_returns"] = self.western_engine.calculate_lunar_returns(
                            jd, moon_lon, years=15
                        )
                    else:
                        logger.warning("Moon longitude unavailable — skipping Lunar Returns")
                        results["lunar_returns"] = []

                    # Pre-natal Syzygy (Phase 3)
                    print("   → Calculating Pre-natal Syzygy...")
                    syzygy_engine = SyzygyEngine(jd)
                    results["syzygy"] = syzygy_engine.calculate_syzygy()

                    # Solar Returns — 15-year window
                    sr_engine = SolarReturnEngine(jd, lat, lon)
                    current_year = datetime.now().year
                    solar_returns = sr_engine.get_return_series(current_year, years=15)
                    results["solar_returns"] = solar_returns
                    results["solar_return_analysis"] = [
                        sr_engine.analyze_return_vs_natal(sr) for sr in solar_returns
                    ]

                    # Dodecatemoria (12th parts)
                    print("   → Calculating Dodecatemoria (12th parts)...")
                    try:
                        dodec_engine = DodecatemoriaEngine()
                        results["dodecatemoria"] = dodec_engine.calculate(jd, lat, lon, True)
                    except Exception as e:
                        print(f"   ⚠️  Dodecatemoria error: {e}")
                        results["dodecatemoria"] = {"error": str(e)}

                    # Fixed Star Parans — conditional
                    if time_known:
                        print("   → Calculating Fixed Star Parans...")
                        try:
                            from core.fixed_star_parans import calculate_parans
                            parans_data = calculate_parans(jd, lat, lon, time_known=True)
                            results["parans"] = parans_data
                        except Exception as e:
                            print(f"   ⚠️  Parans error: {e}")
                            results["parans"] = None
                    else:
                        print("   ℹ️  Skipping Fixed Star Parans (birth time unknown — RAMC required)")
                        results["parans"] = None

            except Exception as e:
                logger.error(f"Tropical chain error: {e}")
                results.setdefault("primary_dirs", [])
                results.setdefault("lunar_returns", [])
                results.setdefault("syzygy", {})
                results.setdefault("solar_returns", [])
                results.setdefault("solar_return_analysis", [])
                results.setdefault("dodecatemoria", {"error": str(e)})
                results.setdefault("parans", None)
            return results

        def _compute_dignities():
            """Essential Dignities — pure Python, no ephemeris lock needed."""
            print("   → Validating Essential Dignities...")
            try:
                dignity_engine = EssentialDignities()
                is_day = self._is_day_chart(western['natal']['placements'], western['natal']['angles'])

                valid_placements = {
                    p: d for p, d in western['natal']['placements'].items()
                    if isinstance(d, dict) and 'sign' in d and 'degree' in d
                }

                dignities = dignity_engine.calculate_dignities(
                    valid_placements, is_day=is_day
                )
                receptions = dignity_engine.find_receptions(
                    {p: (d['sign'], d['degree']) for p, d in valid_placements.items()},
                    is_day=is_day
                )
                patterns = western.get('natal', {}).get('patterns', {})
                pattern_summary = patterns.get('summary', {})
                if pattern_summary.get('dominant_pattern'):
                    print(f"   ✓ Dominant pattern: {pattern_summary['dominant_pattern']} "
                          f"(tension: {pattern_summary.get('chart_tension', 0)}, "
                          f"harmony: {pattern_summary.get('chart_harmony', 0)})")
                return {"dignities": dignities, "receptions": receptions}
            except Exception as e:
                print(f"   ⚠️  Dignity calculation error: {e}")
                return {"dignities": {}, "receptions": {}}

        def _compute_kakshya():
            """Kakshya Transit — swe-dependent, acquires global lock."""
            print("   → Calculating Kakshya Transit Quality...")
            try:
                from systems.kakshya_transit import calculate_kakshya_transits
                av_full = vedic.get("strength", {}).get("ashtakavarga_full", {})
                bhinna  = av_full.get("bhinna", {})
                sarva   = av_full.get("sarva",  [20] * 12)
                if not bhinna or not isinstance(bhinna, dict):
                    bhinna = {}
                if not sarva or not isinstance(sarva, list) or len(sarva) != 12:
                    sarva = [20] * 12
                with _swe_lock:
                    return calculate_kakshya_transits(
                        natal_jd=jd, lat=lat, lon=lon,
                        bhinna_av=bhinna, sarva_av=sarva, years_ahead=15
                    )
            except Exception as e:
                print(f"   ⚠️  Kakshya error: {e}")
                return {"error": str(e)}

        with ThreadPoolExecutor(max_workers=3) as pool:
            f_tropical  = pool.submit(_compute_tropical_chain)
            f_dignities = pool.submit(_compute_dignities)
            f_kakshya   = pool.submit(_compute_kakshya)

            try:
                tropical_results = f_tropical.result(timeout=120)
            except Exception as e:
                logger.error(f"Tropical chain timed out or failed: {e}")
                tropical_results = {
                    "primary_dirs": [], "lunar_returns": [], "syzygy": {},
                    "solar_returns": [], "solar_return_analysis": [],
                    "dodecatemoria": {"error": str(e)}, "parans": None,
                }
            try:
                dignity_results = f_dignities.result(timeout=120)
            except Exception as e:
                logger.error(f"Dignity computation timed out or failed: {e}")
                dignity_results = {"dignities": {}, "receptions": {}}
            try:
                kakshya_data = f_kakshya.result(timeout=120)
            except Exception as e:
                logger.error(f"Kakshya computation timed out or failed: {e}")
                kakshya_data = {"error": str(e)}

        # Unpack tropical chain results
        western["predictive"]["primary_directions"] = tropical_results["primary_dirs"]
        western["predictive"]["lunar_returns"] = tropical_results["lunar_returns"]
        western["natal"]["syzygy"] = tropical_results["syzygy"]
        western["predictive"]["solar_returns"] = tropical_results["solar_returns"]
        western["predictive"]["solar_return_analysis"] = tropical_results["solar_return_analysis"]
        hellenistic["dodecatemoria"] = tropical_results["dodecatemoria"]

        # Unpack parans
        parans_data = tropical_results["parans"]
        if parans_data:
            western["natal"]["fixed_stars"] = parans_data.get("conjunctions", [])
            western["natal"]["parans"] = parans_data.get("natal_parans", [])
            western["natal"]["heliacal_events"] = parans_data.get("heliacal_events", [])
            western["natal"]["star_windows"] = parans_data.get("five_year_windows", [])
            western["natal"]["significant_stars"] = parans_data.get("significant_stars", [])
        else:
            western["natal"].setdefault("fixed_stars", [])
            western["natal"]["parans"] = []
            western["natal"]["heliacal_events"] = []
            western["natal"]["star_windows"] = []
            western["natal"]["significant_stars"] = []

        # Unpack dignities
        western['natal']['dignities'] = dignity_results["dignities"]
        western['natal']['receptions'] = dignity_results["receptions"]

        # Unpack kakshya
        vedic["predictive"]["kakshya_transits"] = kakshya_data

        # Cross-system House Lord Validation (pure Python, needs both W+V complete)
        print("   → Validating Cross-System House Lords...")
        mapper = HouseLordMapper()
        lord_validations = mapper.validate_cross_system(
            western['natal'],
            vedic.get('natal', {})
        )

        return {
            "western": western,
            "vedic": vedic,
            "bazi": saju,
            "hellenistic": hellenistic,
            "meta": {
                "jd": jd,
                "lat": lat,
                "lon": lon,
                "birth_year": year,
                "birth_datetime": dt.isoformat(),
                "time_known": time_known,
            },
            "degradation_flags": degradation_flags,
            "lord_validations": lord_validations,
            "predictive": {
                "western": western.get("predictive", {}),
                "vedic": vedic.get("predictive", {}),
                "saju": saju.get("predictive", {}),
                "hellenistic": {
                    **hellenistic.get("predictive", {}),
                    "zodiacal_releasing": hellenistic.get("zodiacal_releasing", {}),
                    "firdaria":           hellenistic.get("firdaria", {}),
                    "alcocoden":          hellenistic.get("alcocoden", {}),
                }
            }
        }

    def _is_day_chart(self, placements: Dict, angles: Dict) -> bool:
        """Determine if day or night chart.

        Day chart: Sun ABOVE horizon = Sun in houses 7-12 (upper hemisphere).
        Sun is above the horizon when it is 0-180° ahead of the Ascendant
        in zodiac order.  Matches the Hellenistic engine formula exactly.
        """
        if 'Ascendant' not in angles or 'Sun' not in placements:
            return True  # Default to day
        asc = angles['Ascendant']['longitude']
        sun = placements['Sun']['longitude']
        diff = (sun - asc) % 360
        return 0.0 < diff < 180.0

    @staticmethod
    def _build_verdict_ledger(synthesis: Dict) -> Dict:
        """Build a Verdict Ledger from the Arbiter's synthesis.

        Extracts top_predictions, consensus_points, and critical_periods into
        a structured, deterministic ledger that becomes a BINDING CONSTRAINT
        for all downstream sections (Archon year chapters, Q&A pipeline).

        This ensures that once the Arbiter decides "house purchase: late 2030",
        every section and Q&A answer must be consistent with that verdict.
        """
        entries = []

        # Extract from top_predictions (highest authority)
        for pred in synthesis.get("top_predictions", []):
            entries.append({
                "source": "arbiter_top_prediction",
                "prediction": pred.get("prediction", ""),
                "date_range": pred.get("date_range", ""),
                "confidence": pred.get("confidence", 0),
                "systems": pred.get("systems", []),
                "evidence": pred.get("evidence", ""),
            })

        # Extract from consensus_points
        for cp in synthesis.get("consensus_points", []):
            entries.append({
                "source": "arbiter_consensus",
                "prediction": cp.get("description", cp.get("theme", "")),
                "date_range": "",  # consensus may not have dates
                "confidence": cp.get("confidence", 0),
                "systems": cp.get("systems_agreeing", []),
                "evidence": cp.get("description", ""),
            })

        # Extract from critical_periods
        for cp in synthesis.get("critical_periods", []):
            entries.append({
                "source": "arbiter_critical_period",
                "prediction": cp.get("meaning", cp.get("action", "")),
                "date_range": cp.get("period", ""),
                "confidence": cp.get("confidence", cp.get("combined_confidence", 0)),
                "systems": cp.get("systems_agreeing", []),
                "evidence": cp.get("meaning", ""),
            })

        # Build the formatted constraint block
        lines = [
            "═══ VERDICT LEDGER (BINDING — DO NOT CONTRADICT) ═══",
            "The Arbiter has analyzed all 4 systems and reached these verdicts.",
            "All downstream sections MUST be consistent with these predictions.",
            "If your section would contradict a verdict below, align with the verdict.",
            "",
        ]
        for i, entry in enumerate(entries[:12], 1):  # cap at 12 entries
            date_str = f" [{entry['date_range']}]" if entry['date_range'] else ""
            sys_str = ", ".join(entry['systems'][:4]) if entry['systems'] else "multi-system"
            lines.append(
                f"  [{i}] {entry['prediction'][:200]}{date_str}"
            )
            lines.append(
                f"      Confidence: {entry['confidence']} | Systems: {sys_str}"
            )
        lines.append("═══ END VERDICT LEDGER ═══")

        return {
            "entries": entries,
            "formatted_block": "\n".join(lines),
        }

    def _extract_prediction_events(self, chart_data: Dict) -> List[PredictionEvent]:
        """
        Extract standardized prediction events from all systems for Validation Matrix.
        Uses canonical weights from ValidationMatrix.TECHNIQUE_WEIGHTS.
        """
        from synthesis.validation_matrix import ValidationMatrix

        events = []
        now = datetime.now()
        # Weights are applied once by ValidationMatrix.add_prediction — events arrive with confidence=1.0

        # --- Western Events ---
        w_pred = chart_data["western"].get("predictive", {})

        # Primary Directions (Gold Standard: 0.95)
        for category, directions in w_pred.get("primary_directions", {}).items():
            if isinstance(directions, list):
                for pd in directions:
                    try:
                        event_date = now + timedelta(days=pd.get("years", 0) * 365.25)
                        events.append(PredictionEvent(
                            system="Western",
                            technique="Primary Direction",
                            date_range=(event_date, event_date + timedelta(days=30)),
                            theme=category.capitalize(),
                            confidence=1.0,  # raw — add_prediction applies weight once
                            description=f"{pd.get('promissor', '?')} to {pd.get('significator', '?')} ({pd.get('arc_degrees', 0):.2f}°)",
                            house_involved=10 if pd.get("significator") == "MC" else (1 if pd.get("significator") == "Asc" else 5),
                            planets_involved=[pd.get("promissor", "?"), pd.get("significator", "?")]
                        ))
                    except Exception as e:
                        logger.warning(f"Error processing PD: {e}")

        # Solar Returns (0.90)
        for sr in w_pred.get("solar_returns", []):
            if isinstance(sr, dict) and "date" in sr:
                try:
                    sr_date = datetime.fromisoformat(sr["date"].replace('Z', '+00:00'))
                    events.append(PredictionEvent(
                        system="Western",
                        technique="Solar Return",
                        date_range=(sr_date, sr_date + timedelta(days=365)),
                        theme="Annual Theme",
                        confidence=1.0,  # raw — add_prediction applies weight once
                        description=f"Solar Return {sr.get('year')} with Asc in natal house {sr.get('dominant_house', 'unknown')}",
                        house_involved=sr.get("dominant_house", 1),
                        planets_involved=["Sun"]
                    ))
                except Exception as e:
                    logger.warning(f"Error processing Solar Return: {e}")

        # Lunar Returns (0.82)
        for lr in w_pred.get("lunar_returns", []):
            if isinstance(lr, dict) and "date" in lr:
                try:
                    lr_date = datetime.fromisoformat(lr["date"].replace('Z', '+00:00'))
                    events.append(PredictionEvent(
                        system="Western",
                        technique="LUNAR_RETURN",
                        date_range=(lr_date, lr_date + timedelta(days=28)),
                        theme="Monthly Focus",
                        confidence=1.0,  # raw — add_prediction applies weight once
                        description=f"Lunar Return {lr.get('year')}-{lr.get('month')}",
                        house_involved=1,
                        planets_involved=["Moon"]
                    ))
                except Exception as e:
                    logger.warning(f"Error processing Lunar Return: {e}")

        # --- Vedic Events ---
        v_pred = chart_data.get("vedic", {}).get("predictive", {})

        # Vimshottari Dasha (0.88)
        dasha = v_pred.get("vimshottari", {})
        if dasha:
            try:
                remaining = dasha.get("approx_remaining_years", 1)
                events.append(PredictionEvent(
                    system="Vedic",
                    technique="Vimshottari Dasha",
                    date_range=(now, now + timedelta(days=remaining * 365)),
                    theme=f"{dasha.get('maha_lord', 'Unknown')} Period",
                    confidence=1.0,  # raw — add_prediction applies weight once
                    description=f"Maha Dasha of {dasha.get('maha_lord')}",
                    house_involved=1,
                    planets_involved=[dasha.get("maha_lord", "Sun")]
                ))
            except Exception as e:
                logger.warning(f"Error processing Dasha: {e}")

        # Tajaka (0.85)
        for taj in v_pred.get("tajaka", []):
            if isinstance(taj, dict):
                try:
                    taj_date = datetime(taj.get("year", now.year), 1, 1)
                    muntha = taj.get("muntha", 0)
                    house = int(muntha // 30) + 1 if muntha else 1
                    events.append(PredictionEvent(
                        system="Vedic",
                        technique="Tajaka",
                        date_range=(taj_date, taj_date + timedelta(days=365)),
                        theme="Muntha Year",
                        confidence=1.0,  # raw — add_prediction applies weight once
                        description=f"Muntha in {taj.get('muntha_sign', 'Unknown')}, Lord: {taj.get('lord_of_year', 'Unknown')}",
                        house_involved=house,
                        planets_involved=[taj.get("lord_of_year", "Sun")]
                    ))
                except Exception as e:
                    logger.warning(f"Error processing Tajaka: {e}")

        # --- Saju Events ---
        s_pred = chart_data.get("bazi", {}).get("predictive", {})

        # Da Yun (Major Luck)
        da_yun = s_pred.get("da_yun", {})
        if isinstance(da_yun, dict):
            for pillar in da_yun.get("pillars", [])[:3]:
                try:
                    start_age = pillar.get("start_age", 0)
                    birth_year = chart_data.get("meta", {}).get("birth_year", now.year)
                    start_year = birth_year + int(start_age)
                    start_date = datetime(start_year, 1, 1)

                    events.append(PredictionEvent(
                        system="Saju",
                        technique="Da Yun",
                        date_range=(start_date, start_date + timedelta(days=10 * 365)),
                        theme=f"Luck Pillar {pillar.get('stem', '?')}{pillar.get('branch', '?')}",
                        confidence=1.0,  # raw — add_prediction applies weight once
                        description=f"10-year luck pillar: {pillar.get('stem_element', '?')} {pillar.get('branch_element', '?')}",
                        house_involved=1,
                        planets_involved=[pillar.get("stem_element", "Wood")]
                    ))
                except Exception as e:
                    logger.warning(f"Error processing Da Yun: {e}")

        # Profections: extracted ONLY in temporal_aligner.py as system="Hellenistic"
        # (correct historical attribution). Removed here to prevent ghost cross-system
        # convergences from duplicate profection data labeled as two different systems.

        chart_data["predictive_event_count"] = len(events)

        # Outer Planet Transit Exact Hits (0.62 weight — individual aspect dates)
        # These are the most precise timing data in the chart: exact dates from ephemeris.
        outer = w_pred.get("outer_transit_aspects", {})
        for hit in outer.get("hits") or outer.get("all_hits", []):
            try:
                # Prefer ISO format; fall back to parsing "Mon DD, YYYY"
                iso_date = hit.get("exact_date_iso", "")
                if iso_date:
                    y, mo, d = map(int, iso_date.split("-"))
                    exact_dt = datetime(y, mo, d)
                else:
                    from datetime import datetime as _dt
                    exact_dt = _dt.strptime(hit.get("exact_date", ""), "%b %d, %Y")

                if exact_dt <= now:
                    continue   # past — skip

                # Entry/exit window from the hit dict (already ISO if present)
                entry_str = hit.get("entry_date", "")
                exit_str  = hit.get("exit_date", "")
                try:
                    entry_dt = datetime.strptime(entry_str, "%Y-%m-%d") if entry_str else exact_dt - timedelta(days=45)
                    exit_dt  = datetime.strptime(exit_str,  "%Y-%m-%d") if exit_str  else exact_dt + timedelta(days=45)
                except Exception:
                    entry_dt = exact_dt - timedelta(days=45)
                    exit_dt  = exact_dt + timedelta(days=45)

                transiting = hit.get("transiting") or hit.get("planet", "Unknown")
                natal_pt   = hit.get("natal_point", "Unknown")
                aspect     = hit.get("aspect", "?")

                # Use computed house lords to find which house a natal point rules
                # (fallback to natural house if no placement data)
                w_placements = chart_data.get("western", {}).get("natal", {}).get("placements", {})
                pt_data = w_placements.get(natal_pt, {})
                house = pt_data.get("house", 0)
                if not house:
                    # Fallback: Ascendant=1, Midheaven=10, else 0 (unassigned)
                    if natal_pt == "Ascendant":
                        house = 1
                    elif natal_pt == "Midheaven":
                        house = 10
                    else:
                        house = 0

                events.append(PredictionEvent(
                    system="Western",
                    technique="Transit_Aspect",
                    date_range=(entry_dt, exit_dt),
                    theme=f"{transiting} {aspect} {natal_pt}",
                    confidence=1.0,  # raw — add_prediction applies weight once
                    description=(
                        f"{transiting} {aspect} natal {natal_pt} "
                        f"exact {exact_dt.strftime('%Y-%m-%d')} (orb {hit.get('orb_at_exact','?')}°)"
                    ),
                    house_involved=house,
                    planets_involved=[transiting, natal_pt]
                ))
            except Exception as e:
                logger.warning(f"Error processing transit hit: {e}")

        if not events:
            logger.warning("No predictive events extracted - check chart data structure")

        logger.info(f"Extracted {len(events)} predictive events for Validation Matrix")
        return events

    def _gather_expert_analyses(self, chart_data: Dict, convergences: List[Dict],
                               contradictions: List[Dict],
                               user_questions: list = None) -> list:
        """Gather analyses in PARALLEL with retry on failure.

        Previously sequential (20-60s). Now uses ThreadPoolExecutor — same pattern
        as Layer 1 chart calculations. Each expert's retry logic stays intact.

        Convergences and contradictions from the Validation Matrix are injected
        into chart_data["validation"] so experts can reference cross-system
        agreement in their analysis.
        """
        # Inject validation matrix results into chart_data for expert access
        chart_data["validation"] = {
            "convergences": convergences[:10] if convergences else [],
            "contradictions": contradictions[:5] if contradictions else [],
            "convergence_summary": self._build_convergence_summary(convergences),
        }

        # Inject mandatory house lord reference block — prevents LLM hallucination
        hl = chart_data.get("house_lords", {})
        w_lords = hl.get("western_lords", {})
        v_lords = hl.get("vedic_lords", {})
        bazi_el = hl.get("bazi_elements", {})
        lord_lines = ["=== MANDATORY HOUSE LORD REFERENCE (computed from chart cusps) ===",
                      "DO NOT invent house lords. Use ONLY these values:",
                      ""]
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
            ("Western",     "Primary Directions emphasis", self.western_expert),
            ("Vedic",       "Ashtakavarga + Vargas",       self.vedic_expert),
            ("Saju",        "",                             self.saju_expert),
            ("Hellenistic", "",                             self.hellenistic_expert),
        ]

        def _run_expert(name, detail, expert):
            label = f"{name} Expert" + (f" ({detail})" if detail else "")
            print(f"   Analyzing with {label}...")
            result = None
            for attempt in range(2):  # 1 retry
                try:
                    result = expert.analyze(chart_data, "natal",
                                            user_questions=user_questions)
                    if result.get("analysis"):
                        return result
                    logger.warning(f"{name} Expert returned empty analysis (attempt {attempt + 1})")
                except Exception as e:
                    logger.error(f"{name} Expert failed (attempt {attempt + 1}): {e}")
                    if attempt == 0:
                        print(f"   ⚠️  {name} Expert failed — retrying...")

            logger.error(f"{name} Expert failed after retries — using fallback")
            return {
                "system": name,
                "mode": "natal",
                "analysis": f"[{name} expert analysis unavailable — API error during generation]",
                "confidence": 0.0,
                "model_used": "fallback",
                "degraded": True,
            }

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(_run_expert, name, detail, expert)
                for name, detail, expert in experts
            ]
            results = [f.result() for f in futures]

        degraded = [r["system"] for r in results if r.get("degraded")]
        if degraded:
            logger.warning(f"Expert degradation: {', '.join(degraded)} returned fallback content")

        return results

    @staticmethod
    def _build_convergence_summary(convergences: List[Dict]) -> str:
        """Build a short text summary of top convergences for expert prompts."""
        if not convergences:
            return ""
        lines = [
            "CROSS-SYSTEM CONVERGENCES (Validation Matrix — reference in your analysis):"
        ]
        for conv in convergences[:5]:
            theme = conv.get("theme_consensus", "Unknown")
            score = conv.get("combined_confidence", 0)
            systems = conv.get("systems", [])
            conv_date = conv.get("convergence_date", "")
            date_str = ""
            if conv_date:
                if hasattr(conv_date, "strftime"):
                    date_str = conv_date.strftime("%b %Y")
                else:
                    date_str = str(conv_date)[:10]
            lines.append(
                f"  • {theme} ({date_str}) — {len(systems)}-system agreement "
                f"(score: {score:.2f}) [{', '.join(systems)}]"
            )
        return "\n".join(lines)


# Global instance
orchestrator = FatesOrchestrator()

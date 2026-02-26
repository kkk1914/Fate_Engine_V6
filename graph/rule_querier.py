"""Graph Rule Querier — bridges Neo4j rule graph into chapter prompt injection.

This module is the missing link between:
  - database.py (which CAN query Neo4j rules)
  - archon.py (which generates chapter text)

The Archon calls GraphRuleQuerier.get_chapter_rules(chapter_name, chart_data)
and receives a formatted string of rules to inject into each chapter prompt.
Rules are ordered by priority/confidence so the highest-authority rules
appear first, preventing them from being overwhelmed by lower-confidence context.
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# ── Priority override map ─────────────────────────────────────────────────────
# Rules matching these placement prefixes ALWAYS appear first in the injected block.
# This implements the "CRITICAL priority overrides dignity" requirement from the roadmap.
CRITICAL_PLACEMENTS = {
    "PD_",           # Primary Directions (confidence 0.95 — gold standard)
    "Dignity_",      # Essential Dignities (exaltations/falls — structural facts)
    "Pattern_",      # Geometric patterns (chart-level configurations)
    "Atmakaraka",    # Soul planet (Jaimini — life-defining)
}


class GraphRuleQuerier:
    """
    Queries Neo4j for rules relevant to each chapter and formats them
    for injection into the Archon's chapter prompts.

    Gracefully degrades if Neo4j is unavailable (returns empty string).
    """

    # Mapping from Archon chapter numbers to Neo4j chapter names
    CHAPTER_MAP = {
        1: ["Identity"],
        2: ["Finances"],
        3: ["Career"],
        4: ["Relationships"],
        5: ["Health"],
        6: ["Destiny"],
        7: ["Finances", "Predictive"],
        8: ["Career", "Predictive"],
        9: ["Health", "Predictive"],
        10: ["Identity", "Career", "Destiny"],
    }

    def __init__(self):
        self._available = False
        self._db = None
        self._try_connect()

    def _try_connect(self):
        """Attempt to connect to Neo4j. Silently degrade if unavailable."""
        try:
            from graph.database import get_db_driver, fetch_rules_for_keys
            self._db_module = __import__("graph.database", fromlist=["get_db_driver",
                                                                      "fetch_rules_for_keys",
                                                                      "build_keys_from_calculated_charts",
                                                                      "RuleKey"])
            self._available = True
            logger.info("GraphRuleQuerier: Neo4j connection available")
        except Exception as e:
            logger.debug(f"GraphRuleQuerier: Neo4j unavailable ({e}). Degrading gracefully.")
            self._available = False

    def get_chapter_rules(self, chapter_num: int, chart_data: Dict[str, Any]) -> str:
        """
        Return a formatted rule-context block for injection into a chapter prompt.

        Format:
        === GRAPH RULES (Neo4j Authority Layer) ===
        [CRITICAL] Primary Direction Sun to MC: Career apex. Public prominence...
        [HIGH] Sun Exalted in Aries (19°): Peak solar authority...
        [Standard] Saturn in Libra: Justice and order...
        === END GRAPH RULES ===

        Returns empty string if Neo4j unavailable.
        """
        if not self._available:
            return ""

        try:
            chapters = self.CHAPTER_MAP.get(chapter_num, ["Identity"])
            keys = self._build_keys(chart_data)

            if not keys:
                return ""

            hits = self._db_module.fetch_rules_for_keys(
                keys,
                chapters=chapters,
                include_global=True
            )

            if not hits:
                return ""

            # Sort: CRITICAL placements first, then by confidence (if present), then alpha
            critical, standard = [], []
            for hit in hits:
                is_critical = any(hit.placement.startswith(p) for p in CRITICAL_PLACEMENTS)
                if is_critical:
                    critical.append(hit)
                else:
                    standard.append(hit)

            lines = ["=== GRAPH RULES (Neo4j Authority Layer — cite these when relevant) ==="]

            for hit in critical[:8]:  # Cap at 8 critical rules per chapter
                label = f"[CRITICAL] [{hit.system} {hit.placement} → {hit.sign}]"
                lines.append(f"{label}: {hit.meaning}")

            for hit in standard[:10]:  # Cap at 10 standard rules per chapter
                label = f"[{hit.system} {hit.placement} in {hit.sign}]"
                lines.append(f"{label}: {hit.meaning}")

            lines.append("=== END GRAPH RULES ===")
            return "\n".join(lines)

        except Exception as e:
            logger.debug(f"GraphRuleQuerier.get_chapter_rules skipped: {e}")
            return ""

    def _build_keys(self, chart_data: Dict[str, Any]) -> List:
        """Build RuleKey list from chart_data for the database query."""
        try:
            RuleKey = self._db_module.RuleKey

            keys = []

            # Western placements
            w_placements = chart_data.get("western", {}).get("natal", {}).get("placements", {})
            for planet, data in w_placements.items():
                if isinstance(data, dict) and data.get("sign"):
                    keys.append(RuleKey("Western", planet, data["sign"]))

            # Western dignity rules
            dignities = (chart_data.get("western", {}).get("natal", {})
                         .get("dignities", {}).get("planet_dignities", {}))
            for planet, ddata in dignities.items():
                if isinstance(ddata, dict):
                    if ddata.get("rulership", 0) > 0:
                        sign = ddata.get("sign", "")
                        keys.append(RuleKey("Western", f"Dignity_{planet}", f"Ruler_{sign}"))
                    if ddata.get("exaltation", 0) > 0:
                        sign = ddata.get("sign", "")
                        keys.append(RuleKey("Western", f"Dignity_{planet}", f"Exalted_{sign}"))
                    if ddata.get("fall", 0) < 0:
                        sign = ddata.get("sign", "")
                        keys.append(RuleKey("Western", f"Dignity_{planet}", f"Fall_{sign}"))

            # Aspects (tight ones only, orb ≤ 3°)
            aspects = chart_data.get("western", {}).get("natal", {}).get("aspects", [])
            for asp in aspects:
                if isinstance(asp, dict) and asp.get("orb", 99) <= 3.0:
                    keys.append(RuleKey(
                        "Western", "Aspects", asp.get("type", ""),
                        meta={"instance": f"{asp.get('p1', '?')} {asp.get('type', '?')} {asp.get('p2', '?')}"}
                    ))

            # Chart patterns
            patterns = chart_data.get("western", {}).get("natal", {}).get("patterns", {})
            for pattern_type in ["grand_trines", "t_squares", "grand_crosses", "yods", "stelliums"]:
                for p in patterns.get(pattern_type, []):
                    if isinstance(p, dict):
                        modality = p.get("modality") or p.get("element") or "General"
                        keys.append(RuleKey(
                            "Western",
                            f"Pattern_{p.get('pattern', '').replace(' ', '_')}",
                            modality
                        ))

            # Primary Directions (most critical)
            pd = chart_data.get("western", {}).get("predictive", {}).get("primary_directions", {})
            for category, dirs in pd.items():
                if isinstance(dirs, list):
                    for d in dirs[:2]:  # Top 2 per category
                        if isinstance(d, dict):
                            keys.append(RuleKey(
                                "Western",
                                f"PD_{d.get('promissor', '?')}_to_{d.get('significator', '?')}",
                                "Primary_Direction"
                            ))

            # Vedic placements
            v_placements = chart_data.get("vedic", {}).get("natal", {}).get("placements", {})
            for planet, data in v_placements.items():
                if isinstance(data, dict) and data.get("sign"):
                    keys.append(RuleKey("Vedic_engine", planet, data["sign"]))
                    if data.get("nakshatra"):
                        nak = data["nakshatra"].replace(" ", "_")
                        keys.append(RuleKey("Vedic_engine", "Nakshatra", nak))


            # Shadbala tiers
            shadbala = (chart_data.get("vedic", {}).get("strength", {})
                        .get("shadbala", {}).get("planet_scores", {}))
            for planet, data in shadbala.items():
                tier = data.get("tier")
                if tier:
                    keys.append(RuleKey("Vedic_engine", f"Shadbala_{planet}", tier))


            # Saju Day Master
            strength = chart_data.get("bazi", {}).get("strength", {})
            dm = strength.get("day_master", {})
            if dm.get("stem"):
                keys.append(RuleKey("Saju", "Day_Master_Stem", dm["stem"]))
            if dm.get("element"):
                keys.append(RuleKey("Saju", "Element_Lens", dm["element"]))

            return keys

        except Exception as e:
            logger.warning(f"_build_keys failed: {e}")
            return []


# Global singleton (lazy — won't fail on import if Neo4j unavailable)
_rule_querier: Optional[GraphRuleQuerier] = None


def get_rule_querier() -> GraphRuleQuerier:
    """Return the global GraphRuleQuerier singleton."""
    global _rule_querier
    if _rule_querier is None:
        _rule_querier = GraphRuleQuerier()
    return _rule_querier

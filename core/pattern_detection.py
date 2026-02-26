"""Geometric Pattern Detection - Yod, T-Square, Grand Cross, Grand Trine, Stellium."""
import math
from typing import Dict, Any, List, Optional, Tuple


def _angular_distance(a: float, b: float) -> float:
    """Smallest arc between two zodiac degrees."""
    diff = abs(a - b) % 360
    return diff if diff <= 180 else 360 - diff


def _is_aspect(d1: float, d2: float, target: float, orb: float) -> Tuple[bool, float]:
    dist = _angular_distance(d1, d2)
    dev = abs(dist - target)
    return dev <= orb, round(dev, 3)


class PatternDetector:
    """
    Detects major geometric patterns in a natal chart.
    All orbs are traditional (tight for multi-body patterns).
    """

    # Orbs for multi-body patterns (tighter than single aspects)
    ORB_TRINE = 8.0
    ORB_SEXTILE = 6.0
    ORB_SQUARE = 8.0
    ORB_OPPOSITION = 8.0
    ORB_CONJUNCTION = 8.0
    ORB_QUINCUNX = 3.0   # Yod uses tight quincunx
    ORB_SEXTILE_YOD = 3.0

    # Pattern confidence weights (maps to validation matrix weights)
    PATTERN_WEIGHTS = {
        "Grand Trine": 0.80,
        "T-Square": 0.82,
        "Grand Cross": 0.85,
        "Yod": 0.78,
        "Stellium": 0.75,
        "Mystic Rectangle": 0.72,
        "Kite": 0.77,
    }

    def detect_all(self, placements: Dict[str, Any],
                   angles: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run all pattern detections.
        placements: {planet_name: {"longitude": float, ...}}
        angles: {"Ascendant": {"longitude": float}, "Midheaven": {"longitude": float}}
        Returns dict with all found patterns.
        """
        # Build unified position map
        positions = {}
        for name, data in placements.items():
            lon = data.get("longitude") or data.get("lon")
            if lon is not None:
                positions[name] = float(lon)

        if angles:
            for name, data in angles.items():
                lon = data.get("longitude") or data.get("lon")
                if lon is not None:
                    positions[name] = float(lon)

        results = {
            "grand_trines": self._find_grand_trines(positions),
            "t_squares": self._find_t_squares(positions),
            "grand_crosses": self._find_grand_crosses(positions),
            "yods": self._find_yods(positions),
            "stelliums": self._find_stelliums(positions),
            "kites": self._find_kites(positions),
            "mystic_rectangles": self._find_mystic_rectangles(positions),
            "summary": {}
        }

        # Build summary
        total = sum(len(v) for k, v in results.items() if k != "summary")
        results["summary"] = {
            "total_patterns": total,
            "has_grand_trine": len(results["grand_trines"]) > 0,
            "has_t_square": len(results["t_squares"]) > 0,
            "has_grand_cross": len(results["grand_crosses"]) > 0,
            "has_yod": len(results["yods"]) > 0,
            "dominant_pattern": self._dominant_pattern(results),
            "chart_tension": self._calc_tension_score(results),
            "chart_harmony": self._calc_harmony_score(results),
        }

        return results

    # ------------------------------------------------------------------ #
    # GRAND TRINE: Three planets ~120° apart (same element)               #
    # ------------------------------------------------------------------ #
    def _find_grand_trines(self, positions: Dict[str, float]) -> List[Dict]:
        found = []
        names = list(positions.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                for k in range(j + 1, len(names)):
                    p1, p2, p3 = names[i], names[j], names[k]
                    ok12, orb12 = _is_aspect(positions[p1], positions[p2], 120, self.ORB_TRINE)
                    ok23, orb23 = _is_aspect(positions[p2], positions[p3], 120, self.ORB_TRINE)
                    ok13, orb13 = _is_aspect(positions[p1], positions[p3], 120, self.ORB_TRINE)
                    if ok12 and ok23 and ok13:
                        avg_orb = round((orb12 + orb23 + orb13) / 3, 3)
                        element = self._get_element(positions[p1])
                        found.append({
                            "pattern": "Grand Trine",
                            "planets": [p1, p2, p3],
                            "element": element,
                            "orbs": {"p1-p2": orb12, "p2-p3": orb23, "p1-p3": orb13},
                            "avg_orb": avg_orb,
                            "confidence": self.PATTERN_WEIGHTS["Grand Trine"],
                            "meaning": (
                                f"Harmonious {element} Grand Trine: natural gifts and ease in "
                                f"{self._element_theme(element)} domains. "
                                f"High talent but risk of complacency."
                            )
                        })
        return self._deduplicate(found)

    # ------------------------------------------------------------------ #
    # T-SQUARE: Opposition with a square apex planet                      #
    # ------------------------------------------------------------------ #
    def _find_t_squares(self, positions: Dict[str, float]) -> List[Dict]:
        found = []
        names = list(positions.keys())
        # Find oppositions first
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                p1, p2 = names[i], names[j]
                ok_opp, orb_opp = _is_aspect(positions[p1], positions[p2], 180, self.ORB_OPPOSITION)
                if not ok_opp:
                    continue
                # Find apex planet (square to both)
                for k in range(len(names)):
                    if k == i or k == j:
                        continue
                    apex = names[k]
                    ok1, orb1 = _is_aspect(positions[apex], positions[p1], 90, self.ORB_SQUARE)
                    ok2, orb2 = _is_aspect(positions[apex], positions[p2], 90, self.ORB_SQUARE)
                    if ok1 and ok2:
                        modality = self._get_modality(positions[apex])
                        found.append({
                            "pattern": "T-Square",
                            "planets": [p1, p2, apex],
                            "apex": apex,
                            "opposition": [p1, p2],
                            "modality": modality,
                            "orbs": {"opposition": orb_opp, "apex-p1": orb1, "apex-p2": orb2},
                            "avg_orb": round((orb_opp + orb1 + orb2) / 3, 3),
                            "confidence": self.PATTERN_WEIGHTS["T-Square"],
                            "meaning": (
                                f"{modality} T-Square: driven tension engine. "
                                f"{apex} is the focal stress point and the key to resolution. "
                                f"High achievement drive with internal friction."
                            )
                        })
        return self._deduplicate(found)

    # ------------------------------------------------------------------ #
    # GRAND CROSS: Four planets in two pairs of oppositions               #
    # ------------------------------------------------------------------ #
    def _find_grand_crosses(self, positions: Dict[str, float]) -> List[Dict]:
        found = []
        names = list(positions.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                ok_opp1, orb_opp1 = _is_aspect(positions[names[i]], positions[names[j]], 180, self.ORB_OPPOSITION)
                if not ok_opp1:
                    continue
                for k in range(j + 1, len(names)):
                    for l in range(k + 1, len(names)):
                        p1, p2, p3, p4 = names[i], names[j], names[k], names[l]
                        ok_opp2, orb_opp2 = _is_aspect(positions[p3], positions[p4], 180, self.ORB_OPPOSITION)
                        if not ok_opp2:
                            continue
                        # Check all four squares
                        ok_sq1, orb_sq1 = _is_aspect(positions[p1], positions[p3], 90, self.ORB_SQUARE)
                        ok_sq2, orb_sq2 = _is_aspect(positions[p1], positions[p4], 90, self.ORB_SQUARE)
                        ok_sq3, orb_sq3 = _is_aspect(positions[p2], positions[p3], 90, self.ORB_SQUARE)
                        ok_sq4, orb_sq4 = _is_aspect(positions[p2], positions[p4], 90, self.ORB_SQUARE)
                        if ok_sq1 and ok_sq2 and ok_sq3 and ok_sq4:
                            modality = self._get_modality(positions[p1])
                            found.append({
                                "pattern": "Grand Cross",
                                "planets": [p1, p2, p3, p4],
                                "modality": modality,
                                "avg_orb": round((orb_opp1 + orb_opp2 + orb_sq1 + orb_sq2 + orb_sq3 + orb_sq4) / 6, 3),
                                "confidence": self.PATTERN_WEIGHTS["Grand Cross"],
                                "meaning": (
                                    f"{modality} Grand Cross: maximum tension and drive. "
                                    f"Four-way pull creates profound inner conflict requiring "
                                    f"mastery—when integrated, this is the chart's greatest power source."
                                )
                            })
        return self._deduplicate(found)

    # ------------------------------------------------------------------ #
    # YOD (Finger of God): Two quincunxes (150°) to one apex, sextile base #
    # ------------------------------------------------------------------ #
    def _find_yods(self, positions: Dict[str, float]) -> List[Dict]:
        found = []
        names = list(positions.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                # Check sextile (60°) between the two base planets
                p_base1, p_base2 = names[i], names[j]
                ok_sxt, orb_sxt = _is_aspect(positions[p_base1], positions[p_base2], 60, self.ORB_SEXTILE_YOD)
                if not ok_sxt:
                    continue
                # Find apex: quincunx (150°) to both base planets
                for k in range(len(names)):
                    if k == i or k == j:
                        continue
                    apex = names[k]
                    ok_q1, orb_q1 = _is_aspect(positions[apex], positions[p_base1], 150, self.ORB_QUINCUNX)
                    ok_q2, orb_q2 = _is_aspect(positions[apex], positions[p_base2], 150, self.ORB_QUINCUNX)
                    if ok_q1 and ok_q2:
                        found.append({
                            "pattern": "Yod",
                            "planets": [p_base1, p_base2, apex],
                            "apex": apex,
                            "base": [p_base1, p_base2],
                            "orbs": {"sextile": orb_sxt, "quincunx-1": orb_q1, "quincunx-2": orb_q2},
                            "avg_orb": round((orb_sxt + orb_q1 + orb_q2) / 3, 3),
                            "confidence": self.PATTERN_WEIGHTS["Yod"],
                            "meaning": (
                                f"Yod (Finger of God): {apex} is the activated apex—a fated, "
                                f"compulsive drive that cannot be ignored. "
                                f"{p_base1} and {p_base2} form the sextile base of cooperative talent "
                                f"that constantly 'points at' {apex}'s mission."
                            )
                        })
        return self._deduplicate(found)

    # ------------------------------------------------------------------ #
    # STELLIUM: 3+ planets within ~10° or in same sign                    #
    # ------------------------------------------------------------------ #
    def _find_stelliums(self, positions: Dict[str, float]) -> List[Dict]:
        found = []
        names = list(positions.keys())
        # Group by sign
        sign_groups: Dict[str, List[str]] = {}
        for name, lon in positions.items():
            sign_idx = int(lon // 30)
            sign_groups.setdefault(sign_idx, []).append(name)

        signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                 "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

        for sign_idx, members in sign_groups.items():
            if len(members) >= 3:
                sign_name = signs[sign_idx]
                lons = [positions[m] for m in members]
                span = max(lons) - min(lons)
                # Handle 0° wrap for Aries
                if span > 180:
                    span = 360 - span
                found.append({
                    "pattern": "Stellium",
                    "planets": members,
                    "sign": sign_name,
                    "span_degrees": round(span, 2),
                    "count": len(members),
                    "confidence": self.PATTERN_WEIGHTS["Stellium"],
                    "meaning": (
                        f"Stellium in {sign_name}: intense concentration of {len(members)} planets. "
                        f"Life force is heavily focused in {sign_name}'s domain—"
                        f"both its gifts and its blindspots are amplified."
                    )
                })

        # Also check degree-based stelliums (within 10°) regardless of sign
        for i in range(len(names)):
            cluster = [names[i]]
            for j in range(len(names)):
                if j == i:
                    continue
                if _angular_distance(positions[names[i]], positions[names[j]]) <= 10.0:
                    cluster.append(names[j])
            if len(cluster) >= 3:
                center = positions[names[i]]
                signs_in_cluster = list(set(signs[int(positions[p] // 30)] for p in cluster))
                # Only add if not already captured by sign grouping
                if len(signs_in_cluster) > 1:
                    found.append({
                        "pattern": "Stellium",
                        "planets": sorted(set(cluster)),
                        "sign": "cross-sign",
                        "span_degrees": round(max(_angular_distance(positions[p], center) for p in cluster) * 2, 2),
                        "count": len(cluster),
                        "confidence": self.PATTERN_WEIGHTS["Stellium"],
                        "meaning": (
                            f"Degree Stellium ({len(cluster)} planets within 10°): "
                            f"extreme concentration of energy crossing sign boundaries."
                        )
                    })

        return self._deduplicate(found)

    # ------------------------------------------------------------------ #
    # KITE: Grand Trine + opposition to one trine planet + sextiles       #
    # ------------------------------------------------------------------ #
    def _find_kites(self, positions: Dict[str, float]) -> List[Dict]:
        found = []
        grand_trines = self._find_grand_trines(positions)
        for gt in grand_trines:
            p1, p2, p3 = gt["planets"]
            # Look for a 4th planet opposing one of the three
            for name, lon in positions.items():
                if name in [p1, p2, p3]:
                    continue
                for apex, opp_to in [(p1, name), (p2, name), (p3, name)]:
                    ok_opp, orb_opp = _is_aspect(positions[apex], lon, 180, self.ORB_OPPOSITION)
                    if ok_opp:
                        others = [x for x in [p1, p2, p3] if x != apex]
                        ok1, orb1 = _is_aspect(lon, positions[others[0]], 60, self.ORB_SEXTILE)
                        ok2, orb2 = _is_aspect(lon, positions[others[1]], 60, self.ORB_SEXTILE)
                        if ok1 and ok2:
                            found.append({
                                "pattern": "Kite",
                                "planets": [p1, p2, p3, name],
                                "tail": name,
                                "apex": apex,
                                "grand_trine_base": others,
                                "confidence": self.PATTERN_WEIGHTS["Kite"],
                                "meaning": (
                                    f"Kite: Grand Trine made actionable by {name} as the 'tail'. "
                                    f"The harmony of the trine is focused into purpose through {apex}. "
                                    f"Rare pattern combining ease with directed ambition."
                                )
                            })
        return self._deduplicate(found)

    # ------------------------------------------------------------------ #
    # MYSTIC RECTANGLE: Two oppositions + sextile/trine connections       #
    # ------------------------------------------------------------------ #
    def _find_mystic_rectangles(self, positions: Dict[str, float]) -> List[Dict]:
        found = []
        names = list(positions.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                ok_opp1, _ = _is_aspect(positions[names[i]], positions[names[j]], 180, self.ORB_OPPOSITION)
                if not ok_opp1:
                    continue
                for k in range(j + 1, len(names)):
                    for l in range(k + 1, len(names)):
                        p1, p2, p3, p4 = names[i], names[j], names[k], names[l]
                        ok_opp2, _ = _is_aspect(positions[p3], positions[p4], 180, self.ORB_OPPOSITION)
                        if not ok_opp2:
                            continue
                        # Check sextile + trine connections
                        ok_s1, _ = _is_aspect(positions[p1], positions[p3], 60, self.ORB_SEXTILE)
                        ok_t1, _ = _is_aspect(positions[p1], positions[p4], 120, self.ORB_TRINE)
                        ok_t2, _ = _is_aspect(positions[p2], positions[p3], 120, self.ORB_TRINE)
                        ok_s2, _ = _is_aspect(positions[p2], positions[p4], 60, self.ORB_SEXTILE)
                        if ok_s1 and ok_t1 and ok_t2 and ok_s2:
                            found.append({
                                "pattern": "Mystic Rectangle",
                                "planets": [p1, p2, p3, p4],
                                "confidence": self.PATTERN_WEIGHTS["Mystic Rectangle"],
                                "meaning": (
                                    f"Mystic Rectangle: practical mysticism—combines the "
                                    f"tension of two oppositions with the harmony of "
                                    f"trines and sextiles. Rare capacity for bridging "
                                    f"spiritual and material domains."
                                )
                            })
        return self._deduplicate(found)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #
    def _get_element(self, lon: float) -> str:
        sign_idx = int(lon // 30) % 12
        elements = ["Fire", "Earth", "Air", "Water"] * 3
        fire = [0, 4, 8]; earth = [1, 5, 9]; air = [2, 6, 10]; water = [3, 7, 11]
        if sign_idx in fire: return "Fire"
        if sign_idx in earth: return "Earth"
        if sign_idx in air: return "Air"
        return "Water"

    def _element_theme(self, element: str) -> str:
        return {"Fire": "identity/spirit", "Earth": "material/body",
                "Air": "mind/communication", "Water": "emotion/psyche"}.get(element, "life")

    def _get_modality(self, lon: float) -> str:
        sign_idx = int(lon // 30) % 12
        if sign_idx in [0, 3, 6, 9]: return "Cardinal"
        if sign_idx in [1, 4, 7, 10]: return "Fixed"
        return "Mutable"

    def _deduplicate(self, items: List[Dict]) -> List[Dict]:
        """Remove duplicate patterns (same planet sets)."""
        seen = set()
        unique = []
        for item in items:
            key = frozenset(item.get("planets", []))
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return sorted(unique, key=lambda x: x.get("avg_orb", 99))

    def _dominant_pattern(self, results: Dict) -> Optional[str]:
        priority = ["grand_crosses", "yods", "t_squares", "kites",
                    "grand_trines", "mystic_rectangles", "stelliums"]
        for key in priority:
            if results.get(key):
                return results[key][0]["pattern"]
        return None

    def _calc_tension_score(self, results: Dict) -> float:
        """0-100 tension score based on hard patterns."""
        score = 0.0
        score += len(results.get("grand_crosses", [])) * 30
        score += len(results.get("t_squares", [])) * 20
        score += len(results.get("yods", [])) * 15
        return min(100.0, round(score, 1))

    def _calc_harmony_score(self, results: Dict) -> float:
        """0-100 harmony score based on soft patterns."""
        score = 0.0
        score += len(results.get("grand_trines", [])) * 25
        score += len(results.get("kites", [])) * 20
        score += len(results.get("mystic_rectangles", [])) * 15
        return min(100.0, round(score, 1))

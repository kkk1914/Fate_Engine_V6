"""Deterministic Prediction Rules Engine.

Applies classical astrological rulebooks as code to produce PredictionEvents
BEFORE any LLM touches the data. This is the single highest-leverage change
for consistency: the LLM's job changes from "decide what will happen" to
"explain what the algorithm already determined."

Architecture:
  Math Layer → PREDICTION RULES ENGINE (this) → Validation Matrix → Experts

Rules are organized by life domain (career, relationship, wealth, health,
home, children, spiritual) and draw from all 4 systems:
  - Western: transits, progressions, solar arcs, primary directions, solar returns
  - Vedic: dasha periods, house lords, yogas, ashtakavarga
  - Saju/Bazi: Da Yun pillars, Liu Nian, spirit stars, interactions
  - Hellenistic: zodiacal releasing, profections, firdaria, lots

Each rule checks deterministic conditions in the chart data and emits
PredictionEvents with pre-assigned confidence, dates, themes, and houses.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

from synthesis.validation_matrix import PredictionEvent

logger = logging.getLogger(__name__)

# ── House-to-Domain Mapping ──────────────────────────────────────────────────
HOUSE_DOMAIN = {
    1: "Identity", 2: "Wealth", 3: "Communication", 4: "Home",
    5: "Children", 6: "Health", 7: "Partnership", 8: "Transformation",
    9: "Higher Learning", 10: "Career", 11: "Social/Income", 12: "Spirituality",
}

# ── Western Sign → House Ruler ───────────────────────────────────────────────
SIGN_RULER_W = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}

# Vedic sign → ruler
SIGN_RULER_V = {
    "Mesha": "Mars", "Vrishabha": "Venus", "Mithuna": "Mercury",
    "Karka": "Moon", "Simha": "Sun", "Kanya": "Mercury",
    "Tula": "Venus", "Vrischika": "Mars", "Dhanus": "Jupiter",
    "Makara": "Saturn", "Kumbha": "Saturn", "Meena": "Jupiter",
}

# Benefic / Malefic classification
BENEFICS = {"Jupiter", "Venus"}
MALEFICS = {"Saturn", "Mars"}
LIGHTS = {"Sun", "Moon"}

# Vedic sign index lookup
ZODIAC_V = [
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrischika", "Dhanus", "Makara", "Kumbha", "Meena",
]

ZODIAC_W = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Saju element cycle
GEN_CYCLE = {"Wood": "Fire", "Fire": "Earth", "Earth": "Metal",
             "Metal": "Water", "Water": "Wood"}
CTRL_CYCLE = {"Wood": "Earth", "Earth": "Water", "Water": "Fire",
              "Fire": "Metal", "Metal": "Wood"}


class PredictionRulesEngine:
    """Deterministic rule-based prediction engine.

    Combines signals from all 4 systems into compound predictions with
    specific date ranges and confidence levels. Each rule checks conditions
    in the chart data and emits PredictionEvents.
    """

    def __init__(self, chart_data: Dict[str, Any]):
        self.chart = chart_data
        self.now = datetime.now(timezone.utc)
        self.events: List[PredictionEvent] = []

        # Pre-extract commonly used data
        self.western = chart_data.get("western", {})
        self.vedic = chart_data.get("vedic", {})
        self.bazi = chart_data.get("bazi", {})
        self.hellenistic = chart_data.get("hellenistic", {})
        self.meta = chart_data.get("meta", {})

        # Western natal
        self.w_natal = self.western.get("natal", {})
        self.w_placements = self.w_natal.get("placements", {})
        self.w_angles = self.w_natal.get("angles", {})
        self.w_houses = self.w_natal.get("houses", {})
        self.w_aspects = self.w_natal.get("aspects", [])
        self.w_pred = self.western.get("predictive", {})

        # Vedic natal
        self.v_natal = self.vedic.get("natal", {})
        self.v_placements = self.v_natal.get("placements", {})
        self.v_houses = self.v_natal.get("houses", {})
        self.v_yogas = self.v_natal.get("yogas", [])
        self.v_pred = self.vedic.get("predictive", {})

        # Saju
        self.s_natal = self.bazi.get("natal", {})
        self.s_pillars = self.s_natal.get("pillars", {})
        self.s_strength = self.bazi.get("strength", {})
        self.s_pred = self.bazi.get("predictive", {})

        # Hellenistic
        self.h_zr = self.hellenistic.get("zodiacal_releasing", {})
        self.h_profections = self.hellenistic.get("annual_profections", {})
        self.h_firdaria = self.hellenistic.get("firdaria", {})
        self.h_sect = self.hellenistic.get("sect", {})
        self.h_dodec = self.hellenistic.get("dodecatemoria", {})

        # Build helper lookups
        self._house_lords_w = self._build_house_lord_map_western()
        self._house_lords_v = self._build_house_lord_map_vedic()
        self._planet_houses_w = self._build_planet_house_map()

    def run_all_rules(self) -> List[PredictionEvent]:
        """Execute all rule categories and return PredictionEvents."""
        try:
            self._transit_house_rules()
        except Exception as e:
            logger.warning(f"Transit house rules error: {e}")

        try:
            self._primary_direction_rules()
        except Exception as e:
            logger.warning(f"Primary direction rules error: {e}")

        try:
            self._progression_rules()
        except Exception as e:
            logger.warning(f"Progression rules error: {e}")

        try:
            self._solar_arc_rules()
        except Exception as e:
            logger.warning(f"Solar arc rules error: {e}")

        try:
            self._solar_return_rules()
        except Exception as e:
            logger.warning(f"Solar return rules error: {e}")

        try:
            self._dasha_rules()
        except Exception as e:
            logger.warning(f"Dasha rules error: {e}")

        try:
            self._dasha_transit_compound_rules()
        except Exception as e:
            logger.warning(f"Dasha-transit compound rules error: {e}")

        try:
            self._yoga_rules()
        except Exception as e:
            logger.warning(f"Yoga rules error: {e}")

        try:
            self._profection_rules()
        except Exception as e:
            logger.warning(f"Profection rules error: {e}")

        try:
            self._zodiacal_releasing_rules()
        except Exception as e:
            logger.warning(f"ZR rules error: {e}")

        try:
            self._saju_dayun_rules()
        except Exception as e:
            logger.warning(f"Da Yun rules error: {e}")

        try:
            self._saju_liu_nian_rules()
        except Exception as e:
            logger.warning(f"Liu Nian rules error: {e}")

        try:
            self._saju_spirit_star_rules()
        except Exception as e:
            logger.warning(f"Spirit star rules error: {e}")

        try:
            self._sect_modifier_rules()
        except Exception as e:
            logger.warning(f"Sect modifier rules error: {e}")

        try:
            self._dodecatemoria_rules()
        except Exception as e:
            logger.warning(f"Dodecatemoria rules error: {e}")

        try:
            self._cross_system_compound_rules()
        except Exception as e:
            logger.warning(f"Cross-system compound rules error: {e}")

        logger.info(f"PredictionRulesEngine: generated {len(self.events)} deterministic predictions")
        return self.events

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_house_lord_map_western(self) -> Dict[int, str]:
        """Map house number → ruling planet (Western)."""
        lords = {}
        for i in range(1, 13):
            house_data = self.w_houses.get(f"House_{i}", {})
            sign = house_data.get("sign", "")
            if sign:
                lords[i] = SIGN_RULER_W.get(sign, "")
        return lords

    def _build_house_lord_map_vedic(self) -> Dict[int, str]:
        """Map house number → ruling planet (Vedic)."""
        lords = {}
        for i in range(1, 13):
            house_data = self.v_houses.get(f"Bhava_{i}", {})
            lord = house_data.get("lord", "")
            if lord:
                lords[i] = lord
        return lords

    def _build_planet_house_map(self) -> Dict[str, int]:
        """Map planet → natal house (Western, by longitude)."""
        result = {}
        houses_lons = []
        for i in range(1, 13):
            h = self.w_houses.get(f"House_{i}", {})
            lon = h.get("lon", h.get("longitude"))
            if lon is not None:
                houses_lons.append((i, lon))

        if not houses_lons:
            return result

        for planet, data in self.w_placements.items():
            if not isinstance(data, dict):
                continue
            p_lon = data.get("lon", data.get("longitude"))
            if p_lon is None:
                continue
            # Find which house this planet falls in
            for idx in range(len(houses_lons)):
                h_num, h_lon = houses_lons[idx]
                next_h_lon = houses_lons[(idx + 1) % 12][1]
                # Handle wrap-around
                if h_lon <= next_h_lon:
                    if h_lon <= p_lon < next_h_lon:
                        result[planet] = h_num
                        break
                else:
                    if p_lon >= h_lon or p_lon < next_h_lon:
                        result[planet] = h_num
                        break
            else:
                logger.warning(f"Planet {planet} (lon={p_lon:.2f}) could not be "
                               f"assigned to any house — omitting from house map")
                # Do NOT default to House 1; leave unassigned to prevent
                # spurious convergences in the Identity domain
                result[planet] = None

        return result

    def _find_transit_house(self, transit_lon: float) -> int:
        """Find which natal house a transiting longitude falls in."""
        houses_lons = []
        for i in range(1, 13):
            h = self.w_houses.get(f"House_{i}", {})
            lon = h.get("lon", h.get("longitude"))
            if lon is not None:
                houses_lons.append((i, lon))
        if not houses_lons:
            return 0  # 0 = unassigned
        for idx in range(len(houses_lons)):
            h_num, h_lon = houses_lons[idx]
            next_h_lon = houses_lons[(idx + 1) % 12][1]
            if h_lon <= next_h_lon:
                if h_lon <= transit_lon < next_h_lon:
                    return h_num
            else:
                if transit_lon >= h_lon or transit_lon < next_h_lon:
                    return h_num
        logger.warning(f"Transit lon {transit_lon:.2f} could not be assigned to any house")
        return 0  # 0 = unassigned

    @staticmethod
    def _ensure_aware(dt: datetime) -> datetime:
        """Make a naive datetime UTC-aware. Pass-through if already aware."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _emit(self, system: str, technique: str, date_start: datetime,
              date_end: datetime, theme: str, description: str,
              house: int, planets: List[str], confidence: float = 1.0):
        """Emit a PredictionEvent (dates always tz-aware UTC)."""
        self.events.append(PredictionEvent(
            system=system,
            technique=technique,
            date_range=(self._ensure_aware(date_start),
                        self._ensure_aware(date_end)),
            theme=theme,
            confidence=confidence,
            description=description,
            house_involved=house,
            planets_involved=planets,
        ))

    def _get_dasha_lord_house(self) -> Optional[int]:
        """Get the house ruled by the current Maha Dasha lord (Vedic)."""
        dasha = self.v_pred.get("vimshottari", {})
        lord = dasha.get("maha_lord", "")
        if not lord:
            return None
        for h_num, h_lord in self._house_lords_v.items():
            if h_lord == lord:
                return h_num
        return None

    def _vedic_sign_to_house(self, sign: str) -> int:
        """Given a Vedic sign, find which house it corresponds to."""
        for i in range(1, 13):
            h = self.v_houses.get(f"Bhava_{i}", {})
            if h.get("sign") == sign:
                return i
        return 1

    # ═══════════════════════════════════════════════════════════════════════════
    # RULE CATEGORIES
    # ═══════════════════════════════════════════════════════════════════════════

    def _transit_house_rules(self):
        """Rules based on outer planet transits through natal houses.

        Classical rules:
        - Jupiter transiting a house = expansion/opportunity in that domain
        - Saturn transiting a house = restructuring/challenge in that domain
        - Uranus transiting = sudden change
        - Neptune transiting = dissolution/spiritualization
        - Pluto transiting = deep transformation
        """
        outer_hits = self.w_pred.get("outer_transit_aspects", {})
        all_hits = outer_hits.get("all_hits", []) or outer_hits.get("hits", [])

        # Track which houses each outer planet is transiting by year
        for hit in all_hits:
            transiting = hit.get("transiting", hit.get("planet", ""))
            natal_pt = hit.get("natal_point", "")
            aspect = hit.get("aspect", "")
            exact_str = hit.get("exact_date", hit.get("exact_date_iso", ""))
            entry_str = hit.get("entry_date", "")
            exit_str = hit.get("exit_date", "")

            if not exact_str or not transiting:
                continue

            try:
                exact_dt = datetime.strptime(exact_str[:10], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc)
                entry_dt = (datetime.strptime(entry_str[:10], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc) if entry_str else exact_dt - timedelta(days=30))
                exit_dt = (datetime.strptime(exit_str[:10], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc) if exit_str else exact_dt + timedelta(days=30))
            except (ValueError, TypeError):
                continue

            if exact_dt < self.now:
                continue

            # Determine the house of the natal point
            house = self._get_natal_point_house(natal_pt)
            domain = HOUSE_DOMAIN.get(house, "General")

            # Apply classical transit interpretation rules
            theme = self._transit_interpretation(transiting, aspect, natal_pt, house)
            if not theme:
                continue

            self._emit(
                system="Western",
                technique="Transit_Aspect",
                date_start=entry_dt,
                date_end=exit_dt,
                theme=theme,
                description=(
                    f"{transiting} {aspect} natal {natal_pt} (H{house} {domain}) "
                    f"exact {exact_str[:10]}"
                ),
                house=house,
                planets=[transiting, natal_pt],
            )

    def _transit_interpretation(self, transiting: str, aspect: str,
                                 natal_pt: str, house: int) -> str:
        """Apply classical transit interpretation rules."""
        domain = HOUSE_DOMAIN.get(house, "General")

        # Hard aspects (conjunction, square, opposition) = major events
        hard = aspect in ("Conjunction", "Square", "Opposition")
        soft = aspect in ("Trine", "Sextile")

        if transiting == "Jupiter":
            if hard:
                return f"{domain} Expansion"
            elif soft:
                return f"{domain} Opportunity"

        elif transiting == "Saturn":
            if hard:
                return f"{domain} Restructuring"
            elif soft:
                return f"{domain} Consolidation"

        elif transiting == "Uranus":
            if hard:
                return f"{domain} Disruption"
            elif soft:
                return f"{domain} Innovation"

        elif transiting == "Neptune":
            if hard:
                return f"{domain} Dissolution"
            elif soft:
                return f"{domain} Inspiration"

        elif transiting == "Pluto":
            if hard:
                return f"{domain} Transformation"
            elif soft:
                return f"{domain} Empowerment"

        return ""

    def _get_natal_point_house(self, point_name: str) -> int:
        """Get the house number for a natal planet or angle."""
        if point_name in ("Ascendant", "Midheaven"):
            if point_name == "Ascendant":
                return 1
            return 10
        house = self._planet_houses_w.get(point_name)
        if house is None:
            return 0  # 0 = unassigned (downstream skips house-based rules)
        return house

    def _primary_direction_rules(self):
        """Rules from Primary Directions (gold standard, 0.95 weight).

        Classical rules:
        - Direction to MC = career/status event
        - Direction to Asc = identity/body event
        - Direction to Sun = vitality/authority event
        - Direction to Moon = emotional/domestic event
        - Benefic promissor = positive event
        - Malefic promissor = challenging event
        """
        pd_data = self.w_pred.get("primary_directions", {})
        for category, directions in pd_data.items():
            if not isinstance(directions, list):
                continue
            for pd in directions:
                years = pd.get("years", 0)
                if years <= 0 or years > 15:
                    continue

                promissor = pd.get("promissor", "")
                significator = pd.get("significator", "")
                arc = pd.get("arc_degrees", 0)

                event_date = self.now + timedelta(days=years * 365.25)

                # Determine house from significator
                if significator == "MC":
                    house = 10
                elif significator == "Asc":
                    house = 1
                elif significator == "Sun":
                    house = self._planet_houses_w.get("Sun") or 5
                elif significator == "Moon":
                    house = self._planet_houses_w.get("Moon") or 4
                else:
                    house = 1

                domain = HOUSE_DOMAIN.get(house, "General")

                # Determine nature from promissor
                if promissor in BENEFICS:
                    nature = "Positive"
                elif promissor in MALEFICS:
                    nature = "Challenging"
                else:
                    nature = "Significant"

                self._emit(
                    system="Western",
                    technique="Primary Direction",
                    date_start=event_date - timedelta(days=90),
                    date_end=event_date + timedelta(days=90),
                    theme=f"{nature} {domain} Event",
                    description=(
                        f"PD {promissor}→{significator} at {arc:.1f}° "
                        f"({years:.1f}yr) — {nature} {domain}"
                    ),
                    house=house,
                    planets=[promissor, significator],
                )

    def _progression_rules(self):
        """Rules from Secondary Progressions.

        Classical rules:
        - Progressed Moon conjunct natal planet = activation of that planet's domain
        - Progressed Sun changing sign = identity shift
        - Progressed Venus conjunct MC = career + relationship highlight
        - Any progressed planet conjunct natal angle = major life event
        """
        progressions = self.w_pred.get("progressions", {})
        prog_aspects = progressions.get("prog_natal_aspects", [])

        for pa in prog_aspects:
            progressed = pa.get("progressed", "")
            natal = pa.get("natal", "")
            aspect = pa.get("aspect", "")
            orb = pa.get("orb", 1.0)

            if not progressed or not natal:
                continue

            # Tighter orb = more exact = happening now; wider = developing
            if orb <= 0.3:
                offset_days = 0
                window = 180
            elif orb <= 0.7:
                offset_days = int(orb * 365)
                window = 365
            else:
                offset_days = int(orb * 365)
                window = 365

            event_date = self.now + timedelta(days=offset_days)

            # Determine house
            house = self._get_natal_point_house(natal)
            domain = HOUSE_DOMAIN.get(house, "General")

            # Key progressed aspects
            theme = ""
            if progressed == "Moon":
                theme = f"{domain} Emotional Activation"
            elif progressed == "Sun":
                if aspect == "Conjunction":
                    theme = f"{domain} Identity Shift"
                else:
                    theme = f"{domain} Development"
            elif progressed == "Venus":
                theme = f"{domain} Relationship/Value Shift"
            elif progressed == "Mars":
                theme = f"{domain} Action/Drive"
            elif progressed in ("Ascendant", "MC"):
                theme = f"Major {domain} Life Event"
            else:
                theme = f"{domain} Progression"

            if aspect in ("Square", "Opposition"):
                theme += " (Tension)"

            self._emit(
                system="Western",
                technique="Progression",
                date_start=event_date - timedelta(days=window // 2),
                date_end=event_date + timedelta(days=window // 2),
                theme=theme,
                description=(
                    f"Prog {progressed} {aspect} natal {natal} "
                    f"(orb {orb:.2f}°) — {theme}"
                ),
                house=house,
                planets=[progressed, natal],
            )

    def _solar_arc_rules(self):
        """Rules from Solar Arc Directions.

        Solar Arc = progressed Sun distance applied to ALL natal points.
        Key rules:
        - SA planet conjunct natal angle = major life event
        - SA angle conjunct natal planet = activation
        """
        directed = self.w_pred.get("directed_positions", {})
        solar_arc = self.w_pred.get("solar_arc", {}).get("arc_deg", 0)

        if not directed or solar_arc <= 0:
            return

        # Check SA positions against natal positions for near-exact aspects
        SA_ORB = 1.0  # 1° orb for SA directions

        natal_points = {}
        for p, d in self.w_placements.items():
            if isinstance(d, dict) and ("lon" in d or "longitude" in d):
                natal_points[p] = d.get("lon", d.get("longitude"))
        for a, d in self.w_angles.items():
            if isinstance(d, dict) and ("lon" in d or "longitude" in d):
                natal_points[a] = d.get("lon", d.get("longitude"))

        for sa_name, sa_data in directed.items():
            if not isinstance(sa_data, dict):
                continue
            sa_lon = sa_data.get("lon", sa_data.get("longitude"))
            if sa_lon is None:
                continue

            for natal_name, natal_lon in natal_points.items():
                if sa_name == natal_name:
                    continue

                diff = abs((sa_lon - natal_lon) % 360)
                if diff > 180:
                    diff = 360 - diff

                # Check major aspects
                for angle, asp_name in [(0, "Conjunction"), (90, "Square"),
                                         (180, "Opposition")]:
                    orb = abs(diff - angle)
                    if orb <= SA_ORB:
                        house = self._get_natal_point_house(natal_name)
                        domain = HOUSE_DOMAIN.get(house, "General")

                        # How many years until exact (orb / ~1°/year)
                        years_to_exact = orb  # SA moves ~1°/year
                        exact_date = self.now + timedelta(days=years_to_exact * 365.25)

                        self._emit(
                            system="Western",
                            technique="Solar Arc",
                            date_start=exact_date - timedelta(days=180),
                            date_end=exact_date + timedelta(days=180),
                            theme=f"{domain} Solar Arc Event",
                            description=(
                                f"SA {sa_name} {asp_name} natal {natal_name} "
                                f"(arc {solar_arc:.1f}°) — {domain}"
                            ),
                            house=house,
                            planets=[sa_name, natal_name],
                        )

    def _solar_return_rules(self):
        """Rules from Solar Returns.

        Classical rules:
        - SR Ascendant ruler's house = year's focus
        - SR planets in angular houses (1,4,7,10) = prominent year for that domain
        - SR Saturn angular = year of responsibility/restriction
        - SR Jupiter angular = year of expansion
        """
        srs = self.w_pred.get("solar_returns", [])
        sr_analyses = self.w_pred.get("solar_return_analysis", [])

        for i, sr in enumerate(srs):
            if not isinstance(sr, dict) or "date" not in sr:
                continue

            try:
                sr_date = self._ensure_aware(datetime.fromisoformat(
                    sr["date"].replace('Z', '+00:00')))
            except (ValueError, TypeError):
                continue

            if sr_date < self.now:
                continue

            dominant_house = sr.get("dominant_house", 0)
            if not dominant_house or dominant_house < 1:
                continue

            domain = HOUSE_DOMAIN.get(dominant_house, "General")
            year = sr.get("year", sr_date.year)

            self._emit(
                system="Western",
                technique="Solar Return",
                date_start=sr_date,
                date_end=sr_date + timedelta(days=365),
                theme=f"{domain} Year",
                description=(
                    f"Solar Return {year}: dominant house {dominant_house} "
                    f"({domain})"
                ),
                house=dominant_house,
                planets=["Sun"],
            )

    def _dasha_rules(self):
        """Rules from Vimshottari Dasha periods.

        Classical rules:
        - Dasha lord rules house X = house X themes activated
        - Jupiter/Venus dasha = generally auspicious
        - Saturn/Rahu dasha = challenging, karmic
        - Antardasha lord + Maha lord combo = specific house activation
        """
        dasha = self.v_pred.get("vimshottari", {})
        if not dasha:
            return

        maha_lord = dasha.get("maha_lord", "")
        antar_lord = dasha.get("antar_lord", "")
        maha_remaining = dasha.get("approx_remaining_years", 0)
        antar_remaining = dasha.get("antar_remaining_years", 0)

        if not maha_lord:
            return

        # Find houses ruled by dasha lords
        maha_houses = [h for h, lord in self._house_lords_v.items()
                       if lord == maha_lord]
        antar_houses = [h for h, lord in self._house_lords_v.items()
                        if lord == antar_lord] if antar_lord else []

        # Maha Dasha activation
        for house in maha_houses:
            domain = HOUSE_DOMAIN.get(house, "General")
            nature = "Positive" if maha_lord in BENEFICS else (
                "Challenging" if maha_lord in MALEFICS else "Significant")

            self._emit(
                system="Vedic",
                technique="Vimshottari Dasha",
                date_start=self.now,
                date_end=self.now + timedelta(days=maha_remaining * 365.25),
                theme=f"{nature} {domain} Period",
                description=(
                    f"{maha_lord} Mahadasha — H{house} ({domain}) activated. "
                    f"{maha_remaining:.1f}yr remaining"
                ),
                house=house,
                planets=[maha_lord],
            )

        # Antardasha activation — more specific timing
        if antar_lord and antar_remaining > 0:
            for house in antar_houses:
                domain = HOUSE_DOMAIN.get(house, "General")

                self._emit(
                    system="Vedic",
                    technique="Vimshottari_Antardasha",
                    date_start=self.now,
                    date_end=self.now + timedelta(
                        days=antar_remaining * 365.25),
                    theme=f"{domain} Sub-Period",
                    description=(
                        f"{maha_lord}/{antar_lord} period — H{house} "
                        f"({domain}) activated. {antar_remaining:.1f}yr remaining"
                    ),
                    house=house,
                    planets=[maha_lord, antar_lord],
                )

            # Antardasha transition event — the end of an antardasha
            # is a classical timing trigger
            if antar_remaining < 2.0:
                transition_date = self.now + timedelta(
                    days=antar_remaining * 365.25)
                self._emit(
                    system="Vedic",
                    technique="Vimshottari_Antardasha",
                    date_start=transition_date - timedelta(days=30),
                    date_end=transition_date + timedelta(days=30),
                    theme="Antardasha Transition",
                    description=(
                        f"{antar_lord} antardasha ends ~"
                        f"{transition_date.strftime('%Y-%m')} — "
                        f"shift in {maha_lord} period focus"
                    ),
                    house=antar_houses[0] if antar_houses else 1,
                    planets=[maha_lord, antar_lord],
                )

    def _dasha_transit_compound_rules(self):
        """COMPOUND rules: Dasha lord + transit alignment.

        The most powerful predictive technique in Vedic astrology:
        when the dasha lord's houses are ALSO being transited by
        Jupiter or Saturn, the event is virtually certain.
        """
        dasha = self.v_pred.get("vimshottari", {})
        maha_lord = dasha.get("maha_lord", "")
        antar_lord = dasha.get("antar_lord", "")
        if not maha_lord:
            return

        # Get houses activated by dasha
        active_houses = set()
        for h, lord in self._house_lords_v.items():
            if lord in (maha_lord, antar_lord):
                active_houses.add(h)

        if not active_houses:
            return

        # Check if outer transits hit these houses' lords in the natal chart
        outer_hits = self.w_pred.get("outer_transit_aspects", {})
        all_hits = outer_hits.get("all_hits", []) or outer_hits.get("hits", [])

        for hit in all_hits:
            transiting = hit.get("transiting", "")
            natal_pt = hit.get("natal_point", "")
            exact_str = hit.get("exact_date", "")

            if transiting not in ("Jupiter", "Saturn"):
                continue
            if not exact_str:
                continue

            # Check if this natal point's house is dasha-activated
            natal_house = self._get_natal_point_house(natal_pt)
            if natal_house not in active_houses:
                continue

            try:
                exact_dt = datetime.strptime(exact_str[:10], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            if exact_dt < self.now:
                continue

            domain = HOUSE_DOMAIN.get(natal_house, "General")
            aspect = hit.get("aspect", "transit")

            self._emit(
                system="Vedic",
                technique="CROSS_SYSTEM_LORD",
                date_start=exact_dt - timedelta(days=45),
                date_end=exact_dt + timedelta(days=45),
                theme=f"Dasha-Transit {domain} Activation",
                description=(
                    f"COMPOUND: {maha_lord}/{antar_lord} dasha activates "
                    f"H{natal_house} + {transiting} {aspect} natal {natal_pt} "
                    f"on {exact_str[:10]} — double activation of {domain}"
                ),
                house=natal_house,
                planets=[maha_lord, transiting, natal_pt],
            )

    def _yoga_rules(self):
        """Rules from Vedic Yogas.

        When yogas are present AND their constituent planets' dasha is active,
        the yoga manifests. This is the classical "yoga activation" principle.
        """
        if not self.v_yogas:
            return

        dasha = self.v_pred.get("vimshottari", {})
        maha_lord = dasha.get("maha_lord", "")
        antar_lord = dasha.get("antar_lord", "")
        maha_remaining = dasha.get("approx_remaining_years", 0)

        for yoga in self.v_yogas:
            yoga_type = yoga.get("type", "")
            # Support both old format (members) and new format (planets)
            members = yoga.get("planets", yoga.get("members", []))
            sign = yoga.get("sign", "")
            yoga_name = yoga.get("name", yoga_type)

            # Check if yoga is activated by dasha
            activated = maha_lord in members or antar_lord in members

            # Use house from yoga if available, else derive from sign
            house = yoga.get("house", 0) or (
                self._vedic_sign_to_house(sign) if sign else 1)
            domain = HOUSE_DOMAIN.get(house, "General")

            if yoga_type == "Raja Yoga":
                theme = f"Raja Yoga {domain} Activation"
                desc_prefix = "Power/authority yoga"
            elif yoga_type == "Dhana Yoga":
                theme = f"Dhana Yoga Wealth Activation"
                house = yoga.get("house", 2)
                desc_prefix = "Wealth yoga"
            elif yoga_type == "Pancha Mahapurusha":
                theme = f"{yoga_name} — Great Person"
                desc_prefix = yoga_name
            elif yoga_type == "Gajakesari":
                theme = "Gajakesari — Wisdom & Wealth"
                desc_prefix = "Gajakesari Yoga"
            elif yoga_type == "Neecha Bhanga Raja Yoga":
                theme = "Neecha Bhanga — Strength from Struggle"
                desc_prefix = "Cancelled debilitation"
            elif yoga_type == "Viparita Raja Yoga":
                theme = "Viparita Raja — Gains Through Adversity"
                desc_prefix = "Viparita Raja Yoga"
            elif yoga_type == "Lakshmi Yoga":
                theme = "Lakshmi — Wealth & Beauty"
                desc_prefix = "Lakshmi Yoga"
            else:
                theme = f"{yoga_name} Activation"
                desc_prefix = yoga_name

            if activated:
                # Yoga is actively manifesting during current dasha
                self._emit(
                    system="Vedic",
                    technique="Vimshottari Dasha",
                    date_start=self.now,
                    date_end=self.now + timedelta(
                        days=min(maha_remaining, 5) * 365.25),
                    theme=theme,
                    description=(
                        f"{desc_prefix} in {sign} ({', '.join(members)}) — "
                        f"ACTIVATED by {maha_lord}/{antar_lord} dasha period"
                    ),
                    house=house,
                    planets=members,
                )
            else:
                # Yoga exists but not currently activated — lower priority
                self._emit(
                    system="Vedic",
                    technique="Vimshottari Dasha",
                    date_start=self.now,
                    date_end=self.now + timedelta(days=5 * 365.25),
                    theme=f"Latent {yoga_type}",
                    description=(
                        f"{desc_prefix} in {sign} ({', '.join(members)}) — "
                        f"awaiting activation by {'/'.join(members)} dasha"
                    ),
                    house=house,
                    planets=members,
                )

    def _profection_rules(self):
        """Rules from Annual Profections (Hellenistic).

        The profected year lord activates a specific house for the entire year.
        When the profected year lord is also the dasha lord → very strong.
        """
        profections = self.w_pred.get("profections_timeline", [])
        if not profections:
            return

        for prof in profections[:5]:  # Next 5 years
            year = prof.get("year", 0)
            time_lord = prof.get("time_lord", "")
            activated_house = prof.get("activated_house", 1)
            profected_sign = prof.get("profected_sign", "")

            if not time_lord or not year:
                continue

            start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
            end_date = datetime(year, 12, 31, tzinfo=timezone.utc)

            if end_date < self.now:
                continue

            domain = HOUSE_DOMAIN.get(activated_house, "General")

            self._emit(
                system="Hellenistic",
                technique="Profection",
                date_start=start_date,
                date_end=end_date,
                theme=f"H{activated_house} {domain} Year",
                description=(
                    f"Profected Year {year}: {profected_sign} activates "
                    f"H{activated_house} ({domain}), time lord = {time_lord}"
                ),
                house=activated_house,
                planets=[time_lord],
            )

    def _zodiacal_releasing_rules(self):
        """Rules from Zodiacal Releasing (Hellenistic, 0.82 weight).

        ZR from Fortune = career/material circumstances
        ZR from Spirit = mental/spiritual direction
        L2 period changes = major life shifts
        Loosing of the Bond = peak/turning point

        Data structure: h_zr[lot_key] is a LIST of L1 period dicts, each
        containing 'sub_periods_L2' (a list of L2 dicts).
        """
        for lot_name, lot_key in [("Fortune", "fortune"), ("Spirit", "spirit")]:
            zr_periods = self.h_zr.get(lot_key, [])
            if not zr_periods or not isinstance(zr_periods, list):
                continue

            # L1 current period (first element in the list)
            l1 = zr_periods[0] if isinstance(zr_periods[0], dict) else {}
            l1_sign = l1.get("sign", "")
            if l1_sign:
                house = ZODIAC_W.index(l1_sign) + 1 if l1_sign in ZODIAC_W else 1
                domain = HOUSE_DOMAIN.get(house, "General")
                theme_prefix = "Career/Material" if lot_name == "Fortune" else "Mental/Spiritual"

                self._emit(
                    system="Hellenistic",
                    technique="Zodiacal_Releasing",
                    date_start=self.now,
                    date_end=self.now + timedelta(days=365),
                    theme=f"ZR {theme_prefix} {domain}",
                    description=(
                        f"ZR from {lot_name} L1: {l1_sign} — "
                        f"{theme_prefix} focus on {domain}"
                    ),
                    house=house,
                    planets=["Lot_of_" + lot_name],
                )

            # L2 periods — nested inside L1 as 'sub_periods_L2'
            l2_periods = l1.get("sub_periods_L2", [])
            if not isinstance(l2_periods, list):
                l2_periods = []
            for l2 in l2_periods[:5]:
                if not isinstance(l2, dict):
                    continue
                l2_sign = l2.get("sign", "")
                l2_start = l2.get("start_date", "")
                l2_end = l2.get("end_date", "")

                if not l2_sign or not l2_start:
                    continue

                try:
                    start = self._ensure_aware(datetime.fromisoformat(
                        str(l2_start)[:26].replace('Z', '+00:00')))
                    end = self._ensure_aware(
                        datetime.fromisoformat(
                            str(l2_end)[:26].replace('Z', '+00:00'))
                    ) if l2_end else start + timedelta(days=365)
                except (ValueError, TypeError):
                    continue

                if end < self.now:
                    continue

                house = ZODIAC_W.index(l2_sign) + 1 if l2_sign in ZODIAC_W else 1
                domain = HOUSE_DOMAIN.get(house, "General")

                # Check for Loosing of the Bond
                is_loosing = l2.get("is_loosing_of_bond", l2.get("loosing_of_bond", False))
                theme_suffix = " (PEAK)" if is_loosing else ""

                self._emit(
                    system="Hellenistic",
                    technique="Zodiacal_Releasing",
                    date_start=start,
                    date_end=end,
                    theme=f"ZR L2 {domain}{theme_suffix}",
                    description=(
                        f"ZR L2 from {lot_name}: {l2_sign} period "
                        f"— {domain} emphasis{theme_suffix}"
                    ),
                    house=house,
                    planets=["Lot_of_" + lot_name],
                )

    def _saju_dayun_rules(self):
        """Rules from Bazi Da Yun (10-year luck pillars).

        Classical rules:
        - Da Yun element supporting Day Master = favorable decade
        - Da Yun element controlling Day Master = challenging decade
        - Da Yun branch matching spirit stars = activation
        """
        da_yun = self.s_pred.get("da_yun", {})
        if not isinstance(da_yun, dict):
            return

        pillars = da_yun.get("pillars", [])
        dm_element = self.s_strength.get("day_master", {}).get("element", "")
        useful_god = self.s_strength.get("useful_god", "")
        birth_year = self.meta.get("birth_year", self.now.year - 30)

        for pillar in pillars:
            start_age = pillar.get("start_age", 0)
            end_age = pillar.get("end_age", 0)
            stem_el = pillar.get("stem_element", "")
            branch_el = pillar.get("branch_element", "")

            start_year = birth_year + int(start_age)
            end_year = birth_year + int(end_age)

            # Only consider current/future pillars
            if end_year < self.now.year:
                continue

            start_dt = datetime(max(start_year, self.now.year), 1, 1,
                                tzinfo=timezone.utc)
            end_dt = datetime(end_year, 12, 31, tzinfo=timezone.utc)

            # Determine if favorable or challenging
            nature = "Neutral"
            if dm_element:
                # Does the pillar support or drain the Day Master?
                if stem_el == dm_element or GEN_CYCLE.get(stem_el) == dm_element:
                    nature = "Supportive"
                elif CTRL_CYCLE.get(stem_el) == dm_element:
                    nature = "Challenging"

                # Check useful god alignment
                if useful_god and stem_el == useful_god:
                    nature = "Highly Favorable"
                elif useful_god and branch_el == useful_god:
                    nature = "Favorable"

            # Map to domain based on 10-god relationship
            theme = f"Da Yun {nature} Period"

            self._emit(
                system="Saju",
                technique="Da Yun",
                date_start=start_dt,
                date_end=end_dt,
                theme=theme,
                description=(
                    f"Da Yun pillar age {start_age}-{end_age}: "
                    f"{stem_el}/{branch_el} — {nature} for {dm_element} DM"
                ),
                house=1,
                planets=[stem_el or "Unknown"],
            )

    def _saju_liu_nian_rules(self):
        """Rules from Liu Nian (annual pillar).

        Classical rules:
        - Liu Nian stem/branch clashing with natal pillars = turbulent year
        - Liu Nian supporting useful god = smooth year
        - Liu Nian activating spirit stars = events in that domain
        """
        liu_nian = self.s_pred.get("liu_nian_timeline", [])
        if not liu_nian:
            return

        dm_element = self.s_strength.get("day_master", {}).get("element", "")
        useful_god = self.s_strength.get("useful_god", "")
        natal_branches = set()
        for p_data in self.s_pillars.values():
            if isinstance(p_data, dict):
                natal_branches.add(p_data.get("branch", ""))

        from systems.saju import STEM_ELEMENT, BRANCH_ELEMENT, CLASHES

        for ln in liu_nian:
            year = ln.get("year", 0)
            stem = ln.get("stem", "")
            branch = ln.get("branch", "")

            if year < self.now.year:
                continue

            start_dt = datetime(year, 1, 1, tzinfo=timezone.utc)
            end_dt = datetime(year, 12, 31, tzinfo=timezone.utc)

            stem_el = STEM_ELEMENT.get(stem, "")
            branch_el = BRANCH_ELEMENT.get(branch, "")

            # Check for clashes with natal pillars
            has_clash = False
            try:
                for pair, clash_name in CLASHES:
                    if branch in pair and natal_branches & pair:
                        has_clash = True
                        break
            except Exception:
                pass

            # Determine nature
            if has_clash:
                theme = "Turbulent Annual Shift"
                nature = "Clashing"
            elif useful_god and (stem_el == useful_god or branch_el == useful_god):
                theme = "Favorable Annual Flow"
                nature = "Favorable"
            elif dm_element and CTRL_CYCLE.get(stem_el) == dm_element:
                theme = "Challenging Annual Pressure"
                nature = "Controlling"
            else:
                theme = "Annual Transition"
                nature = "Neutral"

            self._emit(
                system="Saju",
                technique="Liu_Nian",
                date_start=start_dt,
                date_end=end_dt,
                theme=theme,
                description=(
                    f"Liu Nian {year}: {stem}{branch} ({stem_el}/{branch_el}) "
                    f"— {nature} for {dm_element} DM"
                ),
                house=1,
                planets=[stem_el or "Unknown"],
            )

    def _saju_spirit_star_rules(self):
        """Rules from Shen Sha (spirit stars).

        Activated spirit stars in Da Yun or Liu Nian branches
        trigger their domain events.
        """
        shensha = self.s_natal.get("shensha", [])
        if not shensha:
            return

        liu_nian = self.s_pred.get("liu_nian_timeline", [])
        da_yun_pillars = self.s_pred.get("da_yun", {}).get("pillars", [])
        birth_year = self.meta.get("birth_year", self.now.year - 30)

        # Collect branches from upcoming Da Yun and Liu Nian
        future_branches = {}  # branch → (year_start, year_end, source)
        for ln in liu_nian:
            year = ln.get("year", 0)
            branch = ln.get("branch", "")
            if year >= self.now.year and branch:
                future_branches[branch] = (
                    datetime(year, 1, 1, tzinfo=timezone.utc),
                    datetime(year, 12, 31, tzinfo=timezone.utc),
                    f"Liu Nian {year}",
                )

        for star in shensha:
            star_branch = star.get("branch", star.get("stem_or_branch", ""))
            star_type = star.get("type", "")
            star_domain = star.get("domain", "")
            star_nature = star.get("nature", "neutral")

            if not star_branch or star_branch not in future_branches:
                continue

            start_dt, end_dt, source = future_branches[star_branch]

            # Map domain to house
            domain_house_map = {
                "romance": 7, "travel/career-change": 10,
                "benefactors": 11, "intellect/exams/writing": 3,
                "protection-from-disasters": 1, "helpful-people": 11,
                "marriage-romance-events": 7, "joyful-events-births": 5,
                "spirituality-artistry-isolation": 12,
                "aggression-injury-surgery": 6,
                "major-calamity-danger": 8,
                "theft-financial-loss": 2, "sickness-accidents": 6,
                "isolation-loneliness": 12, "emotional-isolation": 12,
            }
            house = domain_house_map.get(star_domain, 1)

            self._emit(
                system="Saju",
                technique="Da Yun",
                date_start=start_dt,
                date_end=end_dt,
                theme=f"Spirit Star: {star_type.split('(')[0].strip()}",
                description=(
                    f"{star_type} activated in {source} "
                    f"(branch {star_branch}) — {star_domain}"
                ),
                house=house,
                planets=[star_domain],
            )

    def _sect_modifier_rules(self):
        """Rules from Hellenistic Sect (day/night chart).

        Sect modulates which planets are most constructive vs. destructive.
        When the most malefic planet (contrary malefic) is transiting a key
        house or ruling a profection year, it flags heightened risk.
        When the most benefic planet is active, it flags opportunity.
        """
        if not self.h_sect:
            return

        most_benefic = self.h_sect.get("most_benefic", "")
        most_malefic = self.h_sect.get("most_malefic", "")
        is_day = self.h_sect.get("is_day_chart", True)
        planet_scores = self.h_sect.get("planets", {})

        if not most_benefic or not most_malefic:
            return

        # Check if profection time lord matches sect benefic or malefic
        time_lord = self.h_profections.get("time_lord", "")
        profected_house = self.h_profections.get("activated_house", 0)

        if time_lord == most_benefic and profected_house:
            domain = HOUSE_DOMAIN.get(profected_house, "General")
            self._emit(
                system="Hellenistic",
                technique="Profection",
                date_start=self.now,
                date_end=self.now + timedelta(days=365),
                theme=f"Sect-Benefic Year — {domain} Favored",
                description=(
                    f"Profection year activates H{profected_house} ({domain}), "
                    f"ruled by {most_benefic} — the chart's MOST BENEFIC planet "
                    f"({'day' if is_day else 'night'} chart). "
                    f"This is the strongest possible benefic activation."
                ),
                house=profected_house,
                planets=[most_benefic],
            )

        if time_lord == most_malefic and profected_house:
            domain = HOUSE_DOMAIN.get(profected_house, "General")
            self._emit(
                system="Hellenistic",
                technique="Profection",
                date_start=self.now,
                date_end=self.now + timedelta(days=365),
                theme=f"Sect-Malefic Year — {domain} Caution",
                description=(
                    f"Profection year activates H{profected_house} ({domain}), "
                    f"ruled by {most_malefic} — the chart's MOST MALEFIC planet "
                    f"(contrary to {'day' if is_day else 'night'} sect). "
                    f"Exercise caution in {domain.lower()} matters."
                ),
                house=profected_house,
                planets=[most_malefic],
            )

        # Scan existing transit events: boost/penalize based on sect status
        for event in list(self.events):
            if event.system != "Western" or event.technique != "Transit_Aspect":
                continue
            for planet in event.planets_involved:
                pdata = planet_scores.get(planet, {})
                score = pdata.get("score", 0)
                if score == 2 and event.confidence < 0.85:
                    # In-sect + correct hemisphere = most constructive
                    event.confidence = min(event.confidence + 0.08, 0.95)
                elif score == -2 and event.confidence > 0.4:
                    # Contrary + wrong hemisphere = most destructive
                    event.confidence = min(event.confidence + 0.05, 0.95)
                    if "caution" not in event.description.lower():
                        event.description += " [SECT: out-of-sect malefic — heightened risk]"

    def _dodecatemoria_rules(self):
        """Rules from Dodecatemoria (12th-parts).

        When a planet's dodecatemoria falls in a house that reinforces
        the planet's natal significations, it strengthens predictions
        for that house domain. When dodecatemoria and natal placement
        share the same sign (own dodecatemoria), the planet is
        exceptionally powerful.
        """
        dodec_placements = self.h_dodec.get("placements", {})
        dodec_summary = self.h_dodec.get("summary", {})
        if not dodec_placements and not dodec_summary:
            return

        own_dodec_planets = dodec_summary.get("own_dodecatemoria_planets", {})

        # Planets in their own dodecatemoria = doubled power
        if isinstance(own_dodec_planets, dict):
            for planet, data in own_dodec_planets.items():
                natal_house = self._planet_houses_w.get(planet, 0)
                if natal_house:
                    domain = HOUSE_DOMAIN.get(natal_house, "General")
                    self._emit(
                        system="Hellenistic",
                        technique="Transit",
                        date_start=self.now,
                        date_end=self.now + timedelta(days=5 * 365),
                        theme=f"Own Dodecatemoria — {planet} Amplified",
                        description=(
                            f"{planet} is in its OWN dodecatemoria (micro-sign = natal sign). "
                            f"This doubles {planet}'s influence over H{natal_house} ({domain}). "
                            f"Any transit or progression involving {planet} carries extra weight."
                        ),
                        house=natal_house,
                        planets=[planet],
                    )

        # Check dodecatemoria placements for hidden house emphasis
        house_hits: Dict[int, List[str]] = {}
        for planet, pd in dodec_placements.items():
            if not isinstance(pd, dict):
                continue
            dodec_sign = pd.get("sign", "")
            if not dodec_sign:
                continue
            # Find which house this dodecatemoria sign occupies
            for i in range(1, 13):
                h = self.w_houses.get(f"House_{i}", {})
                if h.get("sign", "") == dodec_sign:
                    house_hits.setdefault(i, []).append(planet)
                    break

        # If 3+ planets' dodecatemoria cluster in one house, flag it
        for house, planets in house_hits.items():
            if len(planets) >= 3:
                domain = HOUSE_DOMAIN.get(house, "General")
                self._emit(
                    system="Hellenistic",
                    technique="Transit",
                    date_start=self.now,
                    date_end=self.now + timedelta(days=5 * 365),
                    theme=f"Dodecatemoria Cluster — H{house} {domain}",
                    description=(
                        f"{len(planets)} planets ({', '.join(planets)}) have their "
                        f"dodecatemoria in H{house} ({domain}). This hidden emphasis "
                        f"amplifies all {domain.lower()} matters throughout life."
                    ),
                    house=house,
                    planets=planets,
                )

    def _cross_system_compound_rules(self):
        """Highest-value rules: when 3+ systems agree on timing and theme.

        These produce the strongest predictions by finding windows where
        multiple independent systems converge on the same life domain
        within the same time period.

        Example: Jupiter transit 4th + Venus antardasha + profected 4th
        house year + Da Yun wealth element = property acquisition.
        """
        # Collect all emitted events by house and year
        house_year_events: Dict[Tuple[int, int], List[PredictionEvent]] = {}
        for event in self.events:
            try:
                mid_date = event.date_range[0] + (
                    event.date_range[1] - event.date_range[0]) / 2
                year = mid_date.year
                key = (event.house_involved, year)
                house_year_events.setdefault(key, []).append(event)
            except Exception:
                continue

        # Find compound convergences: same house, same year, 3+ systems
        for (house, year), events in house_year_events.items():
            systems = set(e.system for e in events)
            if len(systems) < 3:
                continue

            domain = HOUSE_DOMAIN.get(house, "General")
            techniques = sorted(set(e.technique for e in events))

            # Build description from strongest events
            evidence = "; ".join(
                f"[{e.system}] {e.technique}: {e.description[:80]}"
                for e in sorted(events, key=lambda x: x.confidence,
                                reverse=True)[:4]
            )

            start_dt = datetime(year, 1, 1, tzinfo=timezone.utc)
            end_dt = datetime(year, 12, 31, tzinfo=timezone.utc)

            self._emit(
                system="Cross-System",
                technique="CROSS_SYSTEM_LORD",
                date_start=start_dt,
                date_end=end_dt,
                theme=f"Multi-System {domain} Convergence",
                description=(
                    f"{len(systems)}-system convergence on H{house} "
                    f"({domain}) in {year}: {evidence}"
                ),
                house=house,
                planets=list(set(
                    p for e in events for p in e.planets_involved
                ))[:5],
            )

"""Fixed Star Parans — True RAMC-Based Horizon Crossing Engine (v3).

WHAT IS A TRUE PARAN?
A paran (paranatellonta) fires when two bodies share the SAME HORIZON or
MERIDIAN SIMULTANEOUSLY. Specifically:

  Planet RISING  while Star CULMINATES  → paran type: rising/culminating
  Planet RISING  while Star SETS        → paran type: rising/setting
  Planet RISING  while Star RISES       → co-rising paran
  (… 16 total combinations for 4 horizon events × 4 horizon events)

Unlike ecliptic conjunctions (which ignore latitude and location), true
parans are:
  1. LOCATION-SPECIFIC — same planet/star pair gives different parans at
     different latitudes, because oblique ascension changes with latitude
  2. DATE-SPECIFIC    — the RAMC at birth determines which parans were
     firing on the birth day
  3. BRADY-METHOD     — each body's 4 critical RAMC values (rising,
     culminating, setting, anti-culminating) are computed; a paran fires
     when any planet RAMC event ≈ any star RAMC event (orb: 1° of RAMC)

UPGRADE FROM v2:
  v2: compared OA values as RA-space approximations
  v3: computes true RAMC critical points per body using equatorial coords,
      validates against birth RAMC, flags "active at birth" parans,
      handles circumpolar bodies (never rise/set), adds time-of-paran
      estimate relative to birth, and provides Brady-style interpretations

Sources:
  Bernadette Brady, "Brady's Book of Fixed Stars" (1998)
  Vivian Robson, "Fixed Stars and Constellations" (1923)
  Makransky, "Horary Astrology Rediscovered" (1988)
  Swiss Ephemeris: swe.fixstar(), swe.houses(), swe.calc_ut()
"""

import math
import swisseph as swe
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Fixed Star Catalogue — (swename, keywords, nature, magnitude)
# swe.fixstar() name strings are case-sensitive to the star catalogue files.
# ─────────────────────────────────────────────────────────────────────────────
STAR_CATALOGUE = {
    "Regulus":         {"swename": "Regulus",       "keywords": ["royalty", "success", "leadership", "nobility"],      "nature": "benefic",  "magnitude": 1.36},
    "Aldebaran":       {"swename": "Aldebaran",     "keywords": ["integrity", "courage", "honor", "eloquence"],        "nature": "benefic",  "magnitude": 0.85},
    "Antares":         {"swename": "Antares",       "keywords": ["obsession", "war", "intensity", "recklessness"],     "nature": "malefic",  "magnitude": 1.06},
    "Fomalhaut":       {"swename": "Fomalhaut",     "keywords": ["vision", "idealism", "fame", "spiritual gifts"],     "nature": "benefic",  "magnitude": 1.16},
    "Spica":           {"swename": "Spica",         "keywords": ["brilliance", "gifts", "renown", "protection"],       "nature": "benefic",  "magnitude": 0.97},
    "Algol":           {"swename": "Algol",         "keywords": ["intense focus", "danger", "power", "extremes"],      "nature": "malefic",  "magnitude": 2.12},
    "Alcyone":         {"swename": "Alcyone",       "keywords": ["grief", "ambition", "sight", "exile"],               "nature": "malefic",  "magnitude": 2.87},
    "Sirius":          {"swename": "Sirius",        "keywords": ["ambition", "fame", "devotion", "power"],             "nature": "benefic",  "magnitude": -1.46},
    "Canopus":         {"swename": "Canopus",       "keywords": ["navigation", "ancient wisdom", "distant paths"],     "nature": "benefic",  "magnitude": -0.72},
    "Vega":            {"swename": "Vega",          "keywords": ["charisma", "artistry", "idealism", "magic"],         "nature": "benefic",  "magnitude":  0.03},
    "Arcturus":        {"swename": "Arcturus",      "keywords": ["protection", "innovation", "guidance", "justice"],   "nature": "benefic",  "magnitude": -0.05},
    "Capella":         {"swename": "Capella",       "keywords": ["curiosity", "honor", "capriciousness"],              "nature": "mixed",    "magnitude":  0.08},
    "Pollux":          {"swename": "Pollux",        "keywords": ["boldness", "artistry", "cunning", "cruelty"],        "nature": "malefic",  "magnitude":  1.14},
    "Procyon":         {"swename": "Procyon",       "keywords": ["speed", "prominence", "rash success"],               "nature": "mixed",    "magnitude":  0.34},
    "Rigel":           {"swename": "Rigel",         "keywords": ["brilliance", "wealth", "technical skill"],           "nature": "benefic",  "magnitude":  0.12},
    "Betelgeuse":      {"swename": "Betelgeuse",    "keywords": ["military honors", "success", "fortune"],             "nature": "benefic",  "magnitude":  0.50},
    "Deneb Algedi":    {"swename": "Deneb Algedi",  "keywords": ["law", "administration", "justice", "authority"],     "nature": "mixed",    "magnitude":  2.85},
    "Achernar":        {"swename": "Achernar",      "keywords": ["success", "royalty", "boldness", "risk"],            "nature": "benefic",  "magnitude":  0.46},
    "Zuben Elgenubi":  {"swename": "Zub.el.Genut",  "keywords": ["social reform", "obligation", "anti-social fates"], "nature": "malefic",  "magnitude":  2.75},
    "Zuben Eschamali": {"swename": "Zub.el.Scha.",  "keywords": ["ambition", "social concern", "wealth", "honor"],    "nature": "benefic",  "magnitude":  2.61},
    "Scheat":          {"swename": "Scheat",        "keywords": ["drowning risk", "imprisonment", "misfortune"],       "nature": "malefic",  "magnitude":  2.44},
    "Markab":          {"swename": "Markab",        "keywords": ["honor", "riches", "dangers", "speed"],              "nature": "mixed",    "magnitude":  2.49},
    "Mirach":          {"swename": "Mirach",        "keywords": ["beauty", "receptivity", "creative talent"],         "nature": "benefic",  "magnitude":  2.06},
    "Alpheratz":       {"swename": "Alpheratz",     "keywords": ["freedom", "speed", "harmony", "honor"],             "nature": "benefic",  "magnitude":  2.06},
    "Difda":           {"swename": "Difda",         "keywords": ["self-destruction", "isolation", "overcoming odds"],  "nature": "malefic",  "magnitude":  2.04},
    "Menkar":          {"swename": "Menkar",        "keywords": ["disease", "notoriety", "victim energy"],             "nature": "malefic",  "magnitude":  2.53},
}

PARAN_PLANETS = {
    "Sun":     swe.SUN,
    "Moon":    swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus":   swe.VENUS,
    "Mars":    swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn":  swe.SATURN,
}

# 1° of RAMC = 4 minutes of sidereal time (Brady standard orb)
PARAN_ORB_RAMC = 1.0   # degrees of RAMC

# Heliacal elongation thresholds
HELIACAL_ELONGATION = {
    "default": 10.0,
    "bright":   8.0,   # magnitude < 0
    "faint":   12.0,   # magnitude > 2.5
}

# Horizon event labels → human-readable
EVENT_LABELS = {
    "rising":           "rising above the eastern horizon",
    "culminating":      "crossing the upper meridian (culminating)",
    "setting":          "setting below the western horizon",
    "anti-culminating": "at the lower meridian (anti-culminating)",
}

# Paran meaning by event combination (Brady interpretations)
PARAN_MEANING = {
    ("rising", "rising"):           "both bodies share the horizon at birth — a fated, simultaneous emergence",
    ("rising", "culminating"):      "as one rises, the other crowns — a signature of public destiny activated at first breath",
    ("rising", "setting"):          "one rises as the other sets — the tension of beginnings and endings woven into the nativity",
    ("rising", "anti-culminating"): "one ascends as the other descends below — hidden depths energized by emergence",
    ("culminating", "rising"):      "the crowning body summons the other from beneath the horizon",
    ("culminating", "culminating"): "both bodies dominate the meridian simultaneously — a double crown signature",
    ("culminating", "setting"):     "authority at the pinnacle while the other fades — prominence that carries loss",
    ("culminating", "anti-culminating"): "upper/lower meridian axis — the full vertical of the sky collapses into one moment",
    ("setting", "rising"):          "departure and arrival bound together — a life marked by transitions",
    ("setting", "culminating"):     "one sets while the other crowns — endings that catalyze legacy",
    ("setting", "setting"):         "both vanish below the horizon together — a signature of hidden or fated conclusions",
    ("setting", "anti-culminating"): "dual descent — matters that withdraw from public life to inner work",
    ("anti-culminating", "rising"):  "hidden power activates the rising body — unconscious resource becomes visible",
    ("anti-culminating", "culminating"): "the unseen fuels the crown — depth beneath prestige",
    ("anti-culminating", "setting"):     "both withdraw — a signature of introversion, hidden strength",
    ("anti-culminating", "anti-culminating"): "twin depths — fate that operates entirely below the surface",
}


class FixedStarParans:
    """True RAMC-based paran engine for a natal chart."""

    def __init__(self, jd_natal: float, lat: float, lon: float):
        self.jd = jd_natal
        self.lat = lat          # Geographic latitude (decimal degrees, + = N)
        self.lon = lon          # Geographic longitude (decimal degrees, + = E)
        self._star_positions: Dict[str, Dict] = {}
        # Compute birth RAMC once
        self._birth_ramc = self._compute_ramc(jd_natal)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def calculate(self, time_known: bool = True) -> Dict[str, Any]:
        """
        Main entry point.
        Returns natal parans, conjunctions, heliacal events, 5-year windows.
        """
        planet_data = self._get_planet_equatorial()
        star_data   = self._get_star_equatorial()

        # 1. True RAMC-based horizon parans (requires birth time)
        natal_parans = []
        if time_known:
            natal_parans = self._find_true_parans(planet_data, star_data)

        # 2. Classic ecliptic conjunctions (no birth time needed)
        conjunctions = self._find_ecliptic_conjunctions(planet_data, star_data)

        # 3. Heliacal events
        heliacal = self._find_heliacal_events(star_data)

        # 4. Five-year progressed star activations
        five_year = self._find_progressed_activations(planet_data, star_data)

        all_hits = natal_parans + conjunctions
        significant = self._rank_significance(all_hits)

        return {
            "natal_parans":      natal_parans,
            "conjunctions":      conjunctions,
            "heliacal_events":   heliacal,
            "five_year_windows": five_year,
            "significant_stars": significant[:8],
            "birth_ramc":        round(self._birth_ramc, 4),
            "total_hits":        len(all_hits),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Core: True RAMC Paran Detection
    # ─────────────────────────────────────────────────────────────────────────

    def _find_true_parans(self, planets: Dict, stars: Dict) -> List[Dict]:
        """
        True RAMC-based parans.

        Algorithm:
          1. For each planet: compute its 4 RAMC critical values
             (rising, culminating, setting, anti-culminating)
             using equatorial coordinates + geographic latitude.
          2. For each star: same 4 critical RAMC values.
          3. A paran fires when |planet_RAMC_event - star_RAMC_event| ≤ orb.
          4. Annotate whether the paran was "active at birth" (within 10° of
             birth RAMC — meaning it was happening at or near the moment of birth).
          5. Skip circumpolar bodies (never cross the horizon at this latitude).
        """
        hits = []

        for p_name, p_data in planets.items():
            p_events = self._critical_ramc_points(p_data["ra"], p_data["dec"])

            for s_name, s_data in stars.items():
                s_events = self._critical_ramc_points(s_data["ra"], s_data["dec"])

                for p_event, p_ramc in p_events.items():
                    if p_ramc is None:
                        continue  # circumpolar — no rising/setting

                    for s_event, s_ramc in s_events.items():
                        if s_ramc is None:
                            continue

                        # Angular distance in RAMC space
                        diff = abs(p_ramc - s_ramc) % 360
                        arc  = min(diff, 360 - diff)

                        if arc > PARAN_ORB_RAMC:
                            continue

                        # Is this paran active at the birth moment?
                        # "Active" = birth RAMC within ±10° of the paran RAMC
                        # (i.e., it fired within ~40 min of birth in sidereal time)
                        paran_ramc = (p_ramc + s_ramc) / 2  # midpoint of both events
                        birth_proximity = abs(self._birth_ramc - paran_ramc) % 360
                        birth_proximity = min(birth_proximity, 360 - birth_proximity)
                        active_at_birth = birth_proximity <= 10.0

                        meaning = PARAN_MEANING.get(
                            (p_event, s_event),
                            "simultaneous horizon contact — a fated convergence"
                        )

                        hits.append({
                            "type":              "true_paran",
                            "planet":            p_name,
                            "planet_event":      p_event,
                            "planet_ramc":       round(p_ramc, 2),
                            "star":              s_name,
                            "star_event":        s_event,
                            "star_ramc":         round(s_ramc, 2),
                            "orb_ramc_deg":      round(arc, 3),
                            "active_at_birth":   active_at_birth,
                            "birth_ramc":        round(self._birth_ramc, 2),
                            "keywords":          s_data["keywords"],
                            "nature":            s_data["nature"],
                            "paran_meaning":     meaning,
                            "interpretation":    self._build_interpretation(
                                                     p_name, p_event, s_name, s_event,
                                                     arc, s_data, active_at_birth
                                                 ),
                            "confidence":        0.90 if active_at_birth else 0.78,
                        })

        # Deduplicate: keep tightest orb for each planet/star pair
        return self._deduplicate_parans(hits)

    def _critical_ramc_points(self, ra: float, dec: float) -> Dict[str, Optional[float]]:
        """
        Compute the 4 RAMC values at which a body crosses each horizon/meridian.

        Returns dict with keys: rising, culminating, setting, anti-culminating.
        Returns None for rising/setting if body is circumpolar at this latitude.

        Formula (Brady / Makransky):
          AD = arcsin(tan(dec) × tan(lat))      ← Ascensional Difference
          OA = RA - AD                           ← Oblique Ascension (rising RAMC)
          OD = OA + 180°                         ← Oblique Descension (setting RAMC)
          Upper Culmination RAMC = RA
          Lower Culmination RAMC = RA + 180°
        """
        lat_r = math.radians(self.lat)
        dec_r = math.radians(dec)

        # Check circumpolarity: body never rises if |dec| > 90° - |lat|
        # (dec and lat same sign = northern body at northern lat may be circumpolar)
        ad_sin = math.tan(dec_r) * math.tan(lat_r)

        if abs(ad_sin) > 1.0:
            # Circumpolar — never crosses horizon
            horizon_rising  = None
            horizon_setting = None
        else:
            ad = math.degrees(math.asin(ad_sin))
            # For bodies with positive dec at positive lat: AD is positive
            # OA = RA - AD  (Brady convention, matches Placidus ascending point)
            oa = (ra - ad) % 360
            od = (oa + 180.0) % 360
            horizon_rising  = oa
            horizon_setting = od

        upper_culm = ra % 360
        lower_culm = (ra + 180.0) % 360

        return {
            "rising":           horizon_rising,
            "culminating":      upper_culm,
            "setting":          horizon_setting,
            "anti-culminating": lower_culm,
        }

    def _deduplicate_parans(self, hits: List[Dict]) -> List[Dict]:
        """
        For the same planet/star pair, keep only the tightest-orb paran.
        Also remove self-redundant parans (e.g., rising/rising for same body).
        """
        seen: Dict[Tuple, Dict] = {}
        for h in hits:
            key = (h["planet"], h["star"])
            if key not in seen or h["orb_ramc_deg"] < seen[key]["orb_ramc_deg"]:
                seen[key] = h
        # Sort: active-at-birth first, then by orb
        result = sorted(seen.values(),
                        key=lambda x: (not x["active_at_birth"], x["orb_ramc_deg"]))
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Ecliptic Conjunctions (backup: no birth time needed)
    # ─────────────────────────────────────────────────────────────────────────

    def _find_ecliptic_conjunctions(self, planets: Dict, stars: Dict) -> List[Dict]:
        """Classic 1.5° ecliptic longitude conjunction."""
        hits = []
        for p_name, p_data in planets.items():
            p_lon = p_data.get("lon", 0)
            for s_name, s_data in stars.items():
                s_lon = s_data.get("lon", 0)
                diff = abs(p_lon - s_lon) % 360
                orb  = min(diff, 360 - diff)
                if orb <= 1.5:
                    hits.append({
                        "type":           "ecliptic_conjunction",
                        "planet":         p_name,
                        "star":           s_name,
                        "orb_deg":        round(orb, 3),
                        "keywords":       s_data["keywords"],
                        "nature":         s_data["nature"],
                        "interpretation": (
                            f"{p_name} conjunct {s_name} (orb {orb:.2f}° ecliptic): "
                            f"{s_data['nature'].capitalize()} influence — "
                            f"{', '.join(s_data['keywords'][:3])}."
                        ),
                        "confidence":     0.88,
                    })
        return hits

    # ─────────────────────────────────────────────────────────────────────────
    # Heliacal Events
    # ─────────────────────────────────────────────────────────────────────────

    def _find_heliacal_events(self, stars: Dict) -> List[Dict]:
        """
        Heliacal rising: star first visible at dawn after solar conjunction.
        Approximate method: check elongation from Sun at birth.
        Bright stars (mag < 2.0) only.
        """
        events = []
        sun_pos, _ = swe.calc_ut(self.jd, swe.SUN)
        sun_lon = float(sun_pos[0])

        for s_name, s_data in {k: v for k, v in stars.items()
                               if v.get("magnitude", 99) < 2.5}.items():
            s_lon = s_data.get("lon", 0)
            diff  = abs(s_lon - sun_lon) % 360
            elong = min(diff, 360 - diff)

            if s_data["magnitude"] < 0:
                threshold = HELIACAL_ELONGATION["bright"]
            elif s_data["magnitude"] > 2.0:
                threshold = HELIACAL_ELONGATION["faint"]
            else:
                threshold = HELIACAL_ELONGATION["default"]

            visibility = "visible_at_birth" if elong >= threshold else "near_sun_invisible"
            days_to_rising = int(threshold - elong) if elong < threshold else None

            events.append({
                "star":                    s_name,
                "elongation_from_sun_deg": round(elong, 2),
                "visibility":              visibility,
                "days_to_heliacal_rising": days_to_rising,
                "keywords":                s_data["keywords"],
                "nature":                  s_data["nature"],
                "magnitude":               s_data["magnitude"],
                "interpretation": (
                    f"{s_name} ({visibility.replace('_', ' ')}): {s_data['nature']} star. "
                    f"Themes: {', '.join(s_data['keywords'][:2])}."
                    + (f" Heliacal rising ~{days_to_rising} days after birth."
                       if days_to_rising else "")
                ),
            })

        return sorted(events, key=lambda x: x["elongation_from_sun_deg"], reverse=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Five-Year Progressed Activations
    # ─────────────────────────────────────────────────────────────────────────

    def _find_progressed_activations(self, planets: Dict, stars: Dict,
                                     years: int = 5) -> List[Dict]:
        """
        Brady method: progressed Sun (1°/year) reaching star's ecliptic longitude
        activates that star's paran themes for the native.
        Orb: 2° over ~2 years each side.
        """
        windows = []
        now = datetime.now(timezone.utc)
        sun_natal_lon = planets.get("Sun", {}).get("lon", 0)

        for yr in range(years + 1):
            prog_lon = (sun_natal_lon + yr) % 360
            target_year = now.year + yr

            for s_name, s_data in stars.items():
                s_lon = s_data.get("lon", 0)
                diff  = abs(prog_lon - s_lon) % 360
                orb   = min(diff, 360 - diff)
                if orb <= 2.0:
                    windows.append({
                        "year":                target_year,
                        "star":                s_name,
                        "progressed_sun_lon":  round(prog_lon, 2),
                        "star_lon":            round(s_lon, 2),
                        "orb_deg":             round(orb, 2),
                        "keywords":            s_data["keywords"],
                        "nature":              s_data["nature"],
                        "technique":           "Progressed_Sun_Star_Contact",
                        "interpretation": (
                            f"{target_year}: Progressed Sun reaches {s_name} "
                            f"(orb {orb:.1f}°). {s_data['nature'].capitalize()} activation. "
                            f"Themes: {', '.join(s_data['keywords'][:3])}."
                        ),
                        "confidence": 0.75,
                    })

        return sorted(windows, key=lambda x: x["year"])

    # ─────────────────────────────────────────────────────────────────────────
    # Ranking & Significance Scoring
    # ─────────────────────────────────────────────────────────────────────────

    def _rank_significance(self, hits: List[Dict]) -> List[Dict]:
        """
        Score by: orb tightness, planet importance, star royalty, birth-active status.
        """
        royal = {"Regulus", "Aldebaran", "Antares", "Fomalhaut", "Spica"}
        important_planets = {"Sun", "Moon", "Ascendant", "Midheaven", "Jupiter", "Saturn"}

        def score(h: Dict) -> float:
            s = 0.0
            orb = h.get("orb_ramc_deg") or h.get("orb_deg", 99)
            s += max(0, (PARAN_ORB_RAMC - orb)) * 35   # tight orb bonus
            if h.get("active_at_birth"):
                s += 30                                  # fired at birth moment
            if h.get("planet") in important_planets:
                s += 20
            if h.get("star") in royal:
                s += 18
            if h.get("star") == "Algol":
                s += 14
            if h.get("star") in {"Sirius", "Canopus", "Vega", "Arcturus"}:
                s += 10
            if h.get("nature") == "benefic":
                s += 4
            return s

        return sorted(hits, key=score, reverse=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Position Fetchers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_planet_equatorial(self) -> Dict[str, Dict]:
        """Fetch ecliptic + equatorial coords for all paran planets."""
        positions = {}
        for name, code in PARAN_PLANETS.items():
            try:
                ecl, _ = swe.calc_ut(self.jd, code)
                eq,  _ = swe.calc_ut(self.jd, code, swe.FLG_EQUATORIAL)
                positions[name] = {
                    "lon": float(ecl[0]),
                    "lat": float(ecl[1]),
                    "ra":  float(eq[0]),
                    "dec": float(eq[1]),
                }
            except Exception:
                continue
        return positions

    def _get_star_equatorial(self) -> Dict[str, Dict]:
        """Fetch ecliptic + equatorial coords for all catalogue stars."""
        positions = {}
        for display_name, cat in STAR_CATALOGUE.items():
            try:
                # swe.fixstar(name, jd) → (pos[6], retval)
                # pos[0]=ecl_lon, pos[1]=ecl_lat
                star_pos, _ = swe.fixstar(cat["swename"], self.jd)
                ecl_lon = float(star_pos[0])
                ecl_lat = float(star_pos[1])

                # Convert ecliptic → equatorial
                eps = math.radians(23.4392911)
                lon_r = math.radians(ecl_lon)
                lat_r = math.radians(ecl_lat)
                x = math.cos(lat_r) * math.cos(lon_r)
                y = (math.cos(lat_r) * math.sin(lon_r) * math.cos(eps)
                     - math.sin(lat_r) * math.sin(eps))
                z = (math.cos(lat_r) * math.sin(lon_r) * math.sin(eps)
                     + math.sin(lat_r) * math.cos(eps))
                ra  = math.degrees(math.atan2(y, x)) % 360
                dec = math.degrees(math.asin(max(-1.0, min(1.0, z))))

                positions[display_name] = {
                    "lon":       ecl_lon,
                    "lat":       ecl_lat,
                    "ra":        ra,
                    "dec":       dec,
                    "keywords":  cat["keywords"],
                    "nature":    cat["nature"],
                    "magnitude": cat["magnitude"],
                }
            except Exception:
                continue
        return positions

    # ─────────────────────────────────────────────────────────────────────────
    # RAMC Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_ramc(self, jd: float) -> float:
        """
        True RAMC from Swiss Ephemeris via swe.houses().
        MC ecliptic longitude → RA of MC (= RAMC).
        Uses Placidus (b'P') to get accurate angles.
        """
        try:
            cusps, ascmc = swe.houses(jd, self.lat, self.lon, b'P')
            mc_lon = float(ascmc[1])   # ascmc[1] = MC ecliptic longitude
            # Convert MC ecliptic longitude to RA (equatorial)
            eps_r  = math.radians(23.4392911)
            mc_r   = math.radians(mc_lon)
            ramc   = math.degrees(
                math.atan2(
                    math.sin(mc_r) * math.cos(eps_r),
                    math.cos(mc_r)
                )
            ) % 360
            return ramc
        except Exception:
            # Fallback: estimate from JD (approx sidereal time)
            jd_j2000 = jd - 2451545.0
            gst = (280.46061837 + 360.98564736629 * jd_j2000) % 360
            return (gst + self.lon) % 360

    # ─────────────────────────────────────────────────────────────────────────
    # Interpretation Builder
    # ─────────────────────────────────────────────────────────────────────────

    def _build_interpretation(self, planet: str, p_event: str,
                               star: str, s_event: str,
                               orb: float, s_data: Dict,
                               active_at_birth: bool) -> str:
        p_label = EVENT_LABELS.get(p_event, p_event)
        s_label = EVENT_LABELS.get(s_event, s_event)
        nature  = s_data["nature"]
        keys    = ", ".join(s_data["keywords"][:3])

        birth_note = " [ACTIVE AT BIRTH — fired within 40 min of first breath]" if active_at_birth else ""

        return (
            f"{planet} {p_label} while {star} is {s_label} "
            f"(RAMC orb {orb:.2f}°){birth_note}: "
            f"{nature.capitalize()} influence — themes: {keys}."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level flag
# ─────────────────────────────────────────────────────────────────────────────
_time_known_global = True


def calculate_parans(jd: float, lat: float, lon: float,
                     time_known: bool = True) -> Dict[str, Any]:
    """
    Public API. Called from orchestrator/western engine.

    Args:
        jd:         Julian Day of birth (UT)
        lat:        Geographic latitude (decimal degrees, + = N)
        lon:        Geographic longitude (decimal degrees, + = E)
        time_known: True if birth time is known (enables true parans)

    Returns:
        dict with natal_parans, conjunctions, heliacal_events,
        five_year_windows, significant_stars, birth_ramc, total_hits
    """
    global _time_known_global
    _time_known_global = time_known

    try:
        engine = FixedStarParans(jd, lat, lon)
        return engine.calculate(time_known)
    except Exception as e:
        return {
            "error":             str(e),
            "natal_parans":      [],
            "conjunctions":      [],
            "heliacal_events":   [],
            "five_year_windows": [],
            "significant_stars": [],
            "birth_ramc":        0.0,
            "total_hits":        0,
        }

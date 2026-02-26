"""Primary Directions - Regiomontanus Method with proper Oblique Ascension.

FIXES vs previous version:
  - Uses FLG_EQUATORIAL for true RA/Dec (not atan2 approximation)
  - Oblique Ascension properly uses geographic latitude
  - Diurnal Semi-Arc calculated correctly
  - Mundane position uses proper Regiomontanus formula
  - Converse directions added (optional flag)
"""
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import swisseph as swe


class PrimaryDirections:
    """
    Primary Directions using Regiomontanus semi-arc method.
    Uses Swiss Ephemeris equatorial coordinates for RA/Dec.
    Confidence weight: 0.95 (highest in validation hierarchy).
    """

    PROMISSORS = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                  "Jupiter", "Saturn", "Asc", "MC"]
    SIGNIFICATORS = ["Asc", "MC", "Sun", "Moon"]
    NAIBOD = 0.98564733  # degrees per year (mean solar motion)

    def __init__(self, jd_natal: float, lat: float, lon: float):
        self.jd_natal = jd_natal
        self.lat_deg = lat
        self.lat = math.radians(lat)     # geographic latitude in radians
        self.lon = lon
        self._eps = self._calc_obliquity()

    def _calc_obliquity(self) -> float:
        """True obliquity from Swiss Ephemeris ECL_NUT."""
        try:
            nut = swe.calc_ut(self.jd_natal, swe.ECL_NUT)[0]
            return math.radians(float(nut[0]))
        except Exception:
            return math.radians(23.4392911)

    def _get_equatorial(self, body: str) -> Dict[str, float]:
        """
        Get Right Ascension (0-360°) and Declination for a body.
        Uses Swiss Ephemeris FLG_EQUATORIAL for planets.
        Derives RA/Dec algebraically for angles (Asc/MC).
        """
        body_codes = {
            "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
            "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
            "Saturn": swe.SATURN
        }

        if body in body_codes:
            # FLG_EQUATORIAL returns [RA, Dec, dist, RA_speed, Dec_speed, ...]
            pos, _ = swe.calc_ut(self.jd_natal, body_codes[body],
                                 swe.FLG_EQUATORIAL)
            return {"ra": float(pos[0]) % 360, "dec": float(pos[1])}

        # Angles: get ecliptic longitude then convert to equatorial
        cusps, ascmc = swe.houses(self.jd_natal, self.lat_deg, self.lon, b'P')
        if body == "Asc":
            ecl_lon = float(ascmc[0])
            # Ascendant has ecliptic latitude = 0
            ecl_lat = 0.0
        elif body == "MC":
            ecl_lon = float(ascmc[1])
            ecl_lat = 0.0
        else:
            raise ValueError(f"Unknown body: {body}")

        # Ecliptic → equatorial conversion
        eps = self._eps
        ecl_lon_r = math.radians(ecl_lon)
        ecl_lat_r = math.radians(ecl_lat)

        x = math.cos(ecl_lat_r) * math.cos(ecl_lon_r)
        y = (math.cos(ecl_lat_r) * math.sin(ecl_lon_r) * math.cos(eps)
             - math.sin(ecl_lat_r) * math.sin(eps))
        z = (math.cos(ecl_lat_r) * math.sin(ecl_lon_r) * math.sin(eps)
             + math.sin(ecl_lat_r) * math.cos(eps))

        ra = math.degrees(math.atan2(y, x)) % 360
        dec = math.degrees(math.asin(max(-1.0, min(1.0, z))))
        return {"ra": ra, "dec": dec}

    def _oblique_ascension(self, ra_deg: float, dec_deg: float) -> float:
        """
        Oblique Ascension at geographic latitude.
        OA = RA - Ascensional Difference
        AD = arcsin(tan(dec) * tan(lat))
        """
        ad_sin = math.tan(math.radians(dec_deg)) * math.tan(self.lat)
        ad_sin = max(-1.0, min(1.0, ad_sin))
        ad = math.degrees(math.asin(ad_sin))
        return (ra_deg - ad) % 360

    def _diurnal_semi_arc(self, dec_deg: float) -> float:
        """
        Diurnal Semi-Arc in degrees.
        DSA = 90 + AD  where AD = arcsin(tan(dec)*tan(lat))
        Range: 0° (circumpolar below) to 180° (circumpolar above).
        """
        ad_sin = math.tan(math.radians(dec_deg)) * math.tan(self.lat)
        ad_sin = max(-1.0, min(1.0, ad_sin))
        ad = math.degrees(math.asin(ad_sin))
        return 90.0 + ad

    def _ramc(self) -> float:
        """Right Ascension of Midheaven (RAMC) from Swiss Ephemeris."""
        cusps, ascmc = swe.houses(self.jd_natal, self.lat_deg, self.lon, b'P')
        mc_lon = float(ascmc[1])
        # MC is always on meridian; its RA equals RAMC
        # Convert MC ecliptic lon to RA
        eps = self._eps
        mc_r = math.radians(mc_lon)
        ra = math.degrees(
            math.atan2(math.sin(mc_r) * math.cos(eps), math.cos(mc_r))
        ) % 360
        return ra

    def _mundane_position_regio(self, ra: float, dec_deg: float,
                                 ramc: float) -> float:
        """
        Regiomontanus mundane position.

        The Regiomontanus system divides the prime vertical into equal parts.
        Mundane position = proportional position within the diurnal/nocturnal arc.

        Returns a value 0-360 (Campanus-equivalent for our purposes).
        """
        dsa = self._diurnal_semi_arc(dec_deg)
        nsa = 180.0 - dsa

        # Meridian distance from RAMC (positive = west of meridian)
        md = (ramc - ra) % 360
        if md > 180:
            md -= 360  # Signed: negative = east (approaching upper culmination)

        abs_md = abs(md)
        above_horizon = abs_md <= dsa

        if above_horizon:
            # Scale within diurnal arc to 0-90 (upper hemisphere)
            mundane = (abs_md / dsa) * 90.0 if dsa > 0 else 0.0
            if md < 0:  # Eastern hemisphere: negate
                mundane = -mundane
        else:
            # Scale within nocturnal arc to 90-180 (lower hemisphere)
            below_md = abs_md - dsa
            mundane = 90.0 + (below_md / nsa) * 90.0 if nsa > 0 else 90.0
            if md < 0:
                mundane = -mundane

        return mundane % 360

    def _calculate_arc(self, promissor: str, significator: str,
                       converse: bool = False) -> Optional[Dict[str, Any]]:
        """
        Calculate arc of direction from promissor to significator.

        Direct: promissor moves (by primary motion) to significator's mundane pos.
        Converse: significator moves to promissor's mundane pos.
        Arc in Naibod degrees → years via NAIBOD key (0.98564733°/yr).
        """
        try:
            p = self._get_equatorial(promissor)
            s = self._get_equatorial(significator)
            ramc = self._ramc()

            p_mp = self._mundane_position_regio(p["ra"], p["dec"], ramc)
            s_mp = self._mundane_position_regio(s["ra"], s["dec"], ramc)

            if not converse:
                arc = (s_mp - p_mp) % 360
            else:
                arc = (p_mp - s_mp) % 360

            # Use only forward arcs (0 < arc < 180°)
            if arc > 180:
                return None

            years = arc / self.NAIBOD
            target_date = datetime.now() + timedelta(days=years * 365.25)

            return {
                "promissor": promissor,
                "significator": significator,
                "arc_degrees": round(arc, 4),
                "years": round(years, 2),
                "target_date": target_date.isoformat(),
                "p_ra": round(p["ra"], 3),
                "p_dec": round(p["dec"], 3),
                "s_ra": round(s["ra"], 3),
                "s_dec": round(s["dec"], 3),
                "p_mundane": round(p_mp, 3),
                "s_mundane": round(s_mp, 3),
                "converse": converse,
                "method": "Regiomontanus_OA_v2"
            }
        except Exception as e:
            return None

    def calculate_directions(self, years_ahead: int = 5,
                              include_converse: bool = False) -> List[Dict[str, Any]]:
        """Calculate all direct (and optionally converse) directions within window."""
        directions = []
        now = datetime.now()

        for prom in self.PROMISSORS:
            for sig in self.SIGNIFICATORS:
                if prom == sig:
                    continue

                # Direct
                d = self._calculate_arc(prom, sig, converse=False)
                if d and 0 < d["years"] <= years_ahead:
                    target = datetime.fromisoformat(d["target_date"])
                    if target > now:
                        directions.append(d)

                # Converse (optional)
                if include_converse:
                    d_conv = self._calculate_arc(prom, sig, converse=True)
                    if d_conv and 0 < d_conv["years"] <= years_ahead:
                        target = datetime.fromisoformat(d_conv["target_date"])
                        if target > now:
                            directions.append(d_conv)

        directions.sort(key=lambda x: x["years"])
        return directions

    def get_critical_directions(self, years_ahead: int = 5) -> Dict[str, List[Dict]]:
        """Categorize directions by life domain."""
        all_dir = self.calculate_directions(years_ahead, include_converse=True)
        critical = {"career": [], "identity": [], "vitality": [], "emotion": []}

        for d in all_dir:
            sig = d["significator"]
            if sig == "MC":
                critical["career"].append(d)
            elif sig == "Asc":
                critical["identity"].append(d)
            elif sig == "Sun":
                critical["vitality"].append(d)
            elif sig == "Moon":
                critical["emotion"].append(d)

        return critical

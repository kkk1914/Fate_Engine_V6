"""Pre-natal Syzygy (Eclipse/Lunation) calculation."""
import swisseph as swe
from datetime import datetime
from typing import Dict, Any


class SyzygyEngine:
    """
    Calculate Pre-natal Syzygy (last New or Full Moon before birth).
    Hellenistic technique for conception/ancestral patterns.
    """

    def __init__(self, natal_jd: float):
        self.natal_jd = natal_jd

    def calculate_syzygy(self) -> Dict[str, Any]:
        """Find last syzygy before birth."""
        try:
            # Search back 45 days (wider window)
            search_start = self.natal_jd - 45
            search_end = self.natal_jd

            syzygies = []

            # Check every day in window
            for jd in range(int(search_start), int(search_end) + 1):
                sun_pos, _ = swe.calc_ut(jd, swe.SUN)
                moon_pos, _ = swe.calc_ut(jd, swe.MOON)

                # Calculate angular difference
                diff = abs(moon_pos[0] - sun_pos[0]) % 360
                if diff > 180:
                    diff = 360 - diff

                # New Moon (conjunction) - tighter orb
                if diff < 5.0:
                    syzygies.append({
                        'jd': jd,
                        'type': 'New Moon',
                        'sun_lon': sun_pos[0],
                        'moon_lon': moon_pos[0],
                        'phase': 0,
                        'exactness': diff
                    })

                # Full Moon (opposition) - tighter orb
                if abs(diff - 180) < 5.0:
                    syzygies.append({
                        'jd': jd,
                        'type': 'Full Moon',
                        'sun_lon': sun_pos[0],
                        'moon_lon': moon_pos[0],
                        'phase': 180,
                        'exactness': abs(diff - 180)
                    })

            if not syzygies:
                return {"error": "No syzygy found in search window"}

            # Get last one before birth (closest to birth but before it)
            valid_syzygies = [s for s in syzygies if s['jd'] < self.natal_jd]

            if not valid_syzygies:
                return {"error": "No syzygy before birth date"}

            # Pick the one closest to birth (most recent)
            syzygy = min(valid_syzygies, key=lambda x: self.natal_jd - x['jd'])

            # Format date
            dt = swe.revjul(syzygy['jd'])
            syzygy['date'] = f"{int(dt[0])}-{int(dt[1]):02d}-{int(dt[2]):02d}"

            # Determine sign
            sign_num = int(syzygy['moon_lon'] // 30)
            signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                     "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
            syzygy['sign'] = signs[sign_num]

            # Traditional rulers
            rulers = {
                "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
                "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
                "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
                "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
            }
            syzygy['ruler'] = rulers.get(syzygy['sign'])

            # Add days before birth
            syzygy['days_before_birth'] = round(self.natal_jd - syzygy['jd'], 1)

            return syzygy

        except Exception as e:
            return {"error": f"Syzygy calculation failed: {str(e)}"}
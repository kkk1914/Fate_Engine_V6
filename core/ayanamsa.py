"""Sidereal calculations manager."""
import swisseph as swe
from typing import Literal

class AyanamsaManager:
    """Manage various ayanamsa calculations."""

    MODES = {
        "lahiri": swe.SIDM_LAHIRI,
        "raman": swe.SIDM_RAMAN,
        "krishnamurti": swe.SIDM_KRISHNAMURTI,
        "de_luce": swe.SIDM_DELUCE,  # Fixed: was SIDM_DE_LUCE
        "yukteswar": swe.SIDM_YUKTESHWAR,  # Fixed spelling
    }

    @classmethod
    def set_ayanamsa(cls, mode: str = "lahiri"):
        """Set the sidereal mode."""
        if mode in cls.MODES:
            swe.set_sid_mode(cls.MODES[mode])

    @classmethod
    def get_ayanamsa_value(cls, jd: float) -> float:
        """Get the ayanamsa value for a given Julian Day."""
        return swe.get_ayanamsa_ex_ut(jd, swe.FLG_SWIEPH)[1]
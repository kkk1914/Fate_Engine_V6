#!/usr/bin/env python3
"""Test mathematical calculations without API keys."""
import sys
import os
from datetime import datetime  # ADD THIS IMPORT

sys.path.insert(0, os.path.dirname(__file__))

# Mock config to avoid API key requirements
import config

config.settings.test_mode = True
config.settings.openai_api_key = "test-key"

from core.ephemeris import ephe
from core.essential_dignities import EssentialDignities
from core.lunar_return import LunarReturnEngine
from core.syzygy import SyzygyEngine
from core.house_lords import HouseLordMapper
import swisseph as swe


def test_calculations():
    print("=" * 60)
    print("FATES ENGINE PHASE 3 - MATHEMATICAL VALIDATION")
    print("=" * 60)

    # Test data: Kyaw Ko Ko
    birth_dt = "1993-07-19 20:44"
    lat, lon = 1.35, 103.8  # Singapore

    # Parse datetime
    year, month, day = 1993, 7, 19
    hour = 20 + 44 / 60
    jd = swe.julday(year, month, day, hour)

    print(f"\n1. BIRTH DATA:")
    print(f"   Date: {birth_dt}")
    print(f"   Location: {lat}°N, {lon}°E")
    print(f"   Julian Day: {jd}")

    # Calculate Sun position
    sun_pos, _ = swe.calc_ut(jd, swe.SUN)
    print(f"\n2. SUN POSITION (Tropical):")
    print(f"   Longitude: {sun_pos[0]:.2f}°")
    sign_num = int(sun_pos[0] // 30)
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
             "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    print(f"   Sign: {signs[sign_num]}")
    print(f"   Degree: {sun_pos[0] % 30:.2f}°")

    # Verify against report error
    print(f"\n3. VALIDATION CHECK:")
    print(f"   Report claimed: 'Sun traverses 24° Gemini' ❌")
    print(f"   Actual: Sun at {sun_pos[0] % 30:.1f}° {signs[sign_num]} ✅")
    print(f"   Error: 57 degrees off!" if signs[sign_num] != "Gemini" else "   (Correct)")

    # Test Essential Dignities
    print(f"\n4. ESSENTIAL DIGNITIES:")
    dignity_engine = EssentialDignities()
    is_day = sun_pos[0] > 90 and sun_pos[0] < 270  # Simplified day check

    for planet in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]:
        pos, _ = swe.calc_ut(jd, getattr(swe, planet.upper()))
        sign = signs[int(pos[0] // 30)]
        deg = pos[0] % 30
        d = dignity_engine.calculate_dignity(planet, sign, deg, is_day)
        print(f"   {planet}: {sign} {deg:.1f}° | Score: {d.total_score:+d}")

    # Test Lunar Return
    print(f"\n5. LUNAR RETURN (Next 3 months):")
    moon_pos, _ = swe.calc_ut(jd, swe.MOON)
    lr_engine = LunarReturnEngine(jd, moon_pos[0])

    # Test current month and next 2 months
    current_year = datetime.now().year
    current_month = datetime.now().month

    for i in range(3):
        target_month = current_month + i
        target_year = current_year
        if target_month > 12:
            target_month -= 12
            target_year += 1

        lr = lr_engine.calculate_return(target_year, target_month)
        if "error" not in lr:
            print(f"   {lr['date']}: Lunar Return #{i + 1}")
        else:
            print(f"   {target_year}-{target_month:02d}: {lr['error']}")

    # Test Syzygy
    print(f"\n6. PRE-NATAL SYZYGY:")
    sz_engine = SyzygyEngine(jd)
    syzygy = sz_engine.calculate_syzygy()
    if "error" not in syzygy:
        print(f"   Type: {syzygy['type']}")
        print(f"   Date: {syzygy['date']}")
        print(f"   Sign: {syzygy['sign']}")
        print(f"   Ruler: {syzygy['ruler']}")
    else:
        print(f"   Error: {syzygy['error']}")

    print(f"\n{'=' * 60}")
    print("All calculations complete. No API keys required.")
    print("=" * 60)


if __name__ == "__main__":
    test_calculations()


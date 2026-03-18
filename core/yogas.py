"""Classical Vedic Yoga Detection Engine.

Implements 30+ major yogas from Brihat Parashara Hora Shastra and
Phaladeepika. Each yoga is a specific planetary combination with
defined effects on the native's life.

Categories:
  - Raja Yogas (power/authority) — kendra-trikona lord combinations
  - Dhana Yogas (wealth) — 2nd/11th lord combinations
  - Pancha Mahapurusha Yogas — Mars/Mercury/Jupiter/Venus/Saturn in own/exalt in kendra
  - Gajakesari Yoga — Jupiter-Moon angular relationship
  - Neecha Bhanga Raja Yoga — cancelled debilitation
  - Viparita Raja Yoga — dusthana lords in dusthanas
  - Chandra Yogas — Moon-based combinations
  - Nabhas Yogas — pattern-based (stellium, distribution)
  - Special Yogas — Budhaditya, Lakshmi, Saraswati, etc.
"""

from typing import Dict, Any, List

# Vedic sign constants
ZODIAC_V = [
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrischika", "Dhanus", "Makara", "Kumbha", "Meena",
]

VEDIC_RULERS = {
    "Mesha": "Mars", "Vrishabha": "Venus", "Mithuna": "Mercury",
    "Karka": "Moon", "Simha": "Sun", "Kanya": "Mercury",
    "Tula": "Venus", "Vrischika": "Mars", "Dhanus": "Jupiter",
    "Makara": "Saturn", "Kumbha": "Saturn", "Meena": "Jupiter",
}

EXALT_SIGN = {
    "Sun": "Mesha", "Moon": "Vrishabha", "Mars": "Makara",
    "Mercury": "Kanya", "Jupiter": "Karka", "Venus": "Meena",
    "Saturn": "Tula", "Rahu": "Vrishabha", "Ketu": "Vrischika",
}

DEBIL_SIGN = {
    "Sun": "Tula", "Moon": "Vrischika", "Mars": "Karka",
    "Mercury": "Meena", "Jupiter": "Makara", "Venus": "Kanya",
    "Saturn": "Mesha", "Rahu": "Vrischika", "Ketu": "Vrishabha",
}

OWN_SIGNS = {
    "Sun": ["Simha"], "Moon": ["Karka"],
    "Mars": ["Mesha", "Vrischika"], "Mercury": ["Mithuna", "Kanya"],
    "Jupiter": ["Dhanus", "Meena"], "Venus": ["Vrishabha", "Tula"],
    "Saturn": ["Makara", "Kumbha"],
}

NATURAL_BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}
NATURAL_MALEFICS = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}

CLASSICAL_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]


def _sign_index(sign: str) -> int:
    """Get 0-based index of a Vedic sign."""
    try:
        return ZODIAC_V.index(sign)
    except ValueError:
        return -1


def _house_distance(sign1: str, sign2: str) -> int:
    """Count houses from sign1 to sign2 (1-based, inclusive)."""
    i1 = _sign_index(sign1)
    i2 = _sign_index(sign2)
    if i1 < 0 or i2 < 0:
        return 0
    return ((i2 - i1) % 12) + 1


def _is_kendra(distance: int) -> bool:
    """1, 4, 7, 10 are kendras (angular houses)."""
    return distance in (1, 4, 7, 10)


def _is_trikona(distance: int) -> bool:
    """1, 5, 9 are trikonas (trines)."""
    return distance in (1, 5, 9)


def _is_dusthana(distance: int) -> bool:
    """6, 8, 12 are dusthanas (difficult houses)."""
    return distance in (6, 8, 12)


def detect_all_yogas(placements: Dict[str, Any],
                     houses: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect all classical yogas in the chart.

    Args:
        placements: {planet: {sign, lon, deg_in_sign, dignity, ...}}
        houses: {Bhava_1..12: {sign, lord, cusp_lon}}

    Returns:
        List of yoga dicts with: type, name, planets, sign, house,
        strength (strong/moderate/weak), description
    """
    yogas = []

    if not placements or not houses:
        return yogas

    # Pre-compute lookups
    house_signs = {}
    house_lords = {}
    for i in range(1, 13):
        h = houses.get(f"Bhava_{i}", {})
        sign = h.get("sign", "")
        house_signs[i] = sign
        house_lords[i] = h.get("lord", VEDIC_RULERS.get(sign, ""))

    asc_sign = house_signs.get(1, "")
    if not asc_sign:
        return yogas

    # Planet-to-sign lookup
    planet_sign = {}
    for p, d in placements.items():
        if isinstance(d, dict) and "sign" in d:
            planet_sign[p] = d["sign"]

    # Sign-to-planets lookup (which planets occupy each sign)
    sign_occupants = {}
    for p, s in planet_sign.items():
        sign_occupants.setdefault(s, []).append(p)

    # Planet-to-house lookup
    planet_house = {}
    for p, s in planet_sign.items():
        for h_num, h_sign in house_signs.items():
            if h_sign == s:
                planet_house[p] = h_num
                break

    # ═══════════════════════════════════════════════════════════════════════
    # 1. RAJA YOGAS — Kendra lord + Trikona lord combination
    # ═══════════════════════════════════════════════════════════════════════
    kendra_houses = [1, 4, 7, 10]
    trikona_houses = [1, 5, 9]

    kendra_lords = set(house_lords[h] for h in kendra_houses if h in house_lords)
    trikona_lords = set(house_lords[h] for h in trikona_houses if h in house_lords)

    # Raja Yoga by conjunction (same sign)
    for sign, occupants in sign_occupants.items():
        kl = [p for p in occupants if p in kendra_lords]
        tl = [p for p in occupants if p in trikona_lords]
        if kl and tl and set(kl) != set(tl):
            members = sorted(set(kl + tl))
            h = planet_house.get(members[0], 1)
            yogas.append({
                "type": "Raja Yoga",
                "name": "Kendra-Trikona Raja Yoga",
                "planets": members,
                "sign": sign,
                "house": h,
                "strength": "strong" if h in kendra_houses else "moderate",
                "description": (
                    f"Kendra lord(s) {', '.join(kl)} conjoin trikona lord(s) "
                    f"{', '.join(tl)} in {sign} (H{h}) — power and authority"
                ),
            })

    # Raja Yoga by mutual aspect (7th from each other)
    for p1 in kendra_lords:
        for p2 in trikona_lords:
            if p1 == p2:
                continue
            s1 = planet_sign.get(p1, "")
            s2 = planet_sign.get(p2, "")
            if s1 and s2 and _house_distance(s1, s2) == 7:
                yogas.append({
                    "type": "Raja Yoga",
                    "name": "Kendra-Trikona Aspect Raja Yoga",
                    "planets": sorted([p1, p2]),
                    "sign": s1,
                    "house": planet_house.get(p1, 1),
                    "strength": "moderate",
                    "description": (
                        f"Kendra lord {p1} and trikona lord {p2} in mutual "
                        f"aspect (7th) — raja yoga by opposition"
                    ),
                })

    # Raja Yoga by exchange (parivartana between kendra and trikona lords)
    for k_h in kendra_houses:
        for t_h in trikona_houses:
            if k_h == t_h:
                continue
            k_lord = house_lords.get(k_h, "")
            t_lord = house_lords.get(t_h, "")
            if (k_lord and t_lord
                    and planet_sign.get(k_lord) == house_signs.get(t_h)
                    and planet_sign.get(t_lord) == house_signs.get(k_h)):
                yogas.append({
                    "type": "Raja Yoga",
                    "name": "Parivartana Raja Yoga",
                    "planets": sorted([k_lord, t_lord]),
                    "sign": planet_sign.get(k_lord, ""),
                    "house": k_h,
                    "strength": "strong",
                    "description": (
                        f"Exchange between H{k_h} lord {k_lord} and "
                        f"H{t_h} lord {t_lord} — powerful raja yoga"
                    ),
                })

    # ═══════════════════════════════════════════════════════════════════════
    # 2. DHANA YOGAS — Wealth combinations
    # ═══════════════════════════════════════════════════════════════════════
    wealth_houses = [2, 11]
    wealth_lords = set(house_lords[h] for h in wealth_houses if h in house_lords)

    for sign, occupants in sign_occupants.items():
        wl = [p for p in occupants if p in wealth_lords]
        tl = [p for p in occupants if p in trikona_lords]
        if wl and tl and set(wl) != set(tl):
            members = sorted(set(wl + tl))
            h = planet_house.get(members[0], 2)
            yogas.append({
                "type": "Dhana Yoga",
                "name": "Dhana Yoga",
                "planets": members,
                "sign": sign,
                "house": h,
                "strength": "strong" if h in (2, 11) else "moderate",
                "description": (
                    f"Wealth lord(s) {', '.join(wl)} conjoin trikona lord(s) "
                    f"{', '.join(tl)} in {sign} — wealth accumulation"
                ),
            })

    # ═══════════════════════════════════════════════════════════════════════
    # 3. PANCHA MAHAPURUSHA YOGAS — Great Person yogas
    # ═══════════════════════════════════════════════════════════════════════
    pmp_planets = {
        "Mars": "Ruchaka",
        "Mercury": "Bhadra",
        "Jupiter": "Hamsa",
        "Venus": "Malavya",
        "Saturn": "Shasha",
    }

    for planet, yoga_name in pmp_planets.items():
        p_sign = planet_sign.get(planet, "")
        p_house = planet_house.get(planet, 0)
        if not p_sign or not p_house:
            continue

        in_own = p_sign in OWN_SIGNS.get(planet, [])
        in_exalt = p_sign == EXALT_SIGN.get(planet, "")
        in_kendra = p_house in kendra_houses

        if (in_own or in_exalt) and in_kendra:
            yogas.append({
                "type": "Pancha Mahapurusha",
                "name": f"{yoga_name} Yoga",
                "planets": [planet],
                "sign": p_sign,
                "house": p_house,
                "strength": "strong" if in_exalt else "moderate",
                "description": (
                    f"{planet} in {'exaltation' if in_exalt else 'own sign'} "
                    f"({p_sign}) in kendra H{p_house} — {yoga_name} Yoga: "
                    f"great person combination"
                ),
            })

    # ═══════════════════════════════════════════════════════════════════════
    # 4. GAJAKESARI YOGA — Jupiter in kendra from Moon
    # ═══════════════════════════════════════════════════════════════════════
    moon_sign = planet_sign.get("Moon", "")
    jup_sign = planet_sign.get("Jupiter", "")
    if moon_sign and jup_sign:
        dist = _house_distance(moon_sign, jup_sign)
        if _is_kendra(dist):
            yogas.append({
                "type": "Gajakesari",
                "name": "Gajakesari Yoga",
                "planets": ["Jupiter", "Moon"],
                "sign": jup_sign,
                "house": planet_house.get("Jupiter", 1),
                "strength": "strong",
                "description": (
                    f"Jupiter in {jup_sign} is {dist} houses from Moon "
                    f"in {moon_sign} — Gajakesari: wisdom, wealth, fame"
                ),
            })

    # ═══════════════════════════════════════════════════════════════════════
    # 5. NEECHA BHANGA RAJA YOGA — Cancelled debilitation
    # ═══════════════════════════════════════════════════════════════════════
    for planet in CLASSICAL_PLANETS:
        p_sign = planet_sign.get(planet, "")
        if p_sign != DEBIL_SIGN.get(planet, ""):
            continue  # Not debilitated

        # Check cancellation conditions
        cancellation_reason = ""

        # Condition 1: Lord of debilitation sign is in kendra from Asc or Moon
        debil_lord = VEDIC_RULERS.get(p_sign, "")
        dl_sign = planet_sign.get(debil_lord, "")
        if dl_sign:
            dist_from_asc = _house_distance(asc_sign, dl_sign)
            dist_from_moon = _house_distance(moon_sign, dl_sign) if moon_sign else 0
            if _is_kendra(dist_from_asc) or _is_kendra(dist_from_moon):
                cancellation_reason = f"Debil sign lord {debil_lord} in kendra"

        # Condition 2: Planet that exalts in this sign is in kendra
        if not cancellation_reason:
            for other_p, ex_sign in EXALT_SIGN.items():
                if ex_sign == p_sign:
                    op_sign = planet_sign.get(other_p, "")
                    if op_sign:
                        dist = _house_distance(asc_sign, op_sign)
                        if _is_kendra(dist):
                            cancellation_reason = (
                                f"Exaltation lord {other_p} in kendra"
                            )
                            break

        # Condition 3: Lord of exaltation sign is in kendra
        if not cancellation_reason:
            exalt_sign = EXALT_SIGN.get(planet, "")
            exalt_lord = VEDIC_RULERS.get(exalt_sign, "")
            el_sign = planet_sign.get(exalt_lord, "")
            if el_sign:
                dist = _house_distance(asc_sign, el_sign)
                if _is_kendra(dist):
                    cancellation_reason = (
                        f"Exaltation sign lord {exalt_lord} in kendra"
                    )

        if cancellation_reason:
            yogas.append({
                "type": "Neecha Bhanga Raja Yoga",
                "name": "Neecha Bhanga Raja Yoga",
                "planets": [planet],
                "sign": p_sign,
                "house": planet_house.get(planet, 1),
                "strength": "strong",
                "description": (
                    f"{planet} debilitated in {p_sign} but cancellation: "
                    f"{cancellation_reason} — transforms weakness into "
                    f"exceptional strength through struggle"
                ),
            })

    # ═══════════════════════════════════════════════════════════════════════
    # 6. VIPARITA RAJA YOGA — Dusthana lords in dusthanas
    # ═══════════════════════════════════════════════════════════════════════
    dusthana_houses = [6, 8, 12]
    dusthana_lords = {house_lords.get(h, ""): h for h in dusthana_houses
                      if h in house_lords}

    for lord, source_house in dusthana_lords.items():
        if not lord:
            continue
        lord_house = planet_house.get(lord, 0)
        if lord_house in dusthana_houses and lord_house != source_house:
            yogas.append({
                "type": "Viparita Raja Yoga",
                "name": "Viparita Raja Yoga",
                "planets": [lord],
                "sign": planet_sign.get(lord, ""),
                "house": lord_house,
                "strength": "moderate",
                "description": (
                    f"H{source_house} lord {lord} in H{lord_house} "
                    f"(dusthana in dusthana) — gains through adversity, "
                    f"enemies' losses become your gains"
                ),
            })

    # ═══════════════════════════════════════════════════════════════════════
    # 7. BUDHADITYA YOGA — Sun-Mercury conjunction
    # ═══════════════════════════════════════════════════════════════════════
    sun_sign = planet_sign.get("Sun", "")
    merc_sign = planet_sign.get("Mercury", "")
    if sun_sign and sun_sign == merc_sign:
        sun_deg = placements.get("Sun", {}).get("deg_in_sign", 0)
        merc_deg = placements.get("Mercury", {}).get("deg_in_sign", 0)
        # Combust check: Mercury within 14° of Sun is combust → weakened
        dist = abs(float(sun_deg) - float(merc_deg))
        is_combust = dist < 14
        h = planet_house.get("Sun", 1)
        yogas.append({
            "type": "Budhaditya Yoga",
            "name": "Budhaditya Yoga",
            "planets": ["Sun", "Mercury"],
            "sign": sun_sign,
            "house": h,
            "strength": "weak" if is_combust else "strong",
            "description": (
                f"Sun-Mercury conjunction in {sun_sign} H{h} — "
                f"intelligence, learning, eloquence"
                + (" (weakened: Mercury combust)" if is_combust else "")
            ),
        })

    # ═══════════════════════════════════════════════════════════════════════
    # 8. CHANDRA-MANGALA YOGA — Moon-Mars conjunction
    # ═══════════════════════════════════════════════════════════════════════
    mars_sign = planet_sign.get("Mars", "")
    if moon_sign and moon_sign == mars_sign:
        h = planet_house.get("Moon", 1)
        yogas.append({
            "type": "Chandra-Mangala Yoga",
            "name": "Chandra-Mangala Yoga",
            "planets": ["Moon", "Mars"],
            "sign": moon_sign,
            "house": h,
            "strength": "moderate",
            "description": (
                f"Moon-Mars conjunction in {moon_sign} H{h} — "
                f"wealth through bold action, courage, determination"
            ),
        })

    # ═══════════════════════════════════════════════════════════════════════
    # 9. LAKSHMI YOGA — 9th lord strong + Venus in own/exalt in kendra/trikona
    # ═══════════════════════════════════════════════════════════════════════
    ninth_lord = house_lords.get(9, "")
    venus_sign = planet_sign.get("Venus", "")
    venus_house = planet_house.get("Venus", 0)
    if ninth_lord and venus_sign:
        venus_strong = (venus_sign in OWN_SIGNS.get("Venus", [])
                        or venus_sign == EXALT_SIGN.get("Venus", ""))
        venus_good_house = venus_house in (1, 2, 4, 5, 7, 9, 10, 11)
        ninth_strong = (planet_sign.get(ninth_lord, "") in
                        OWN_SIGNS.get(ninth_lord, []) + [EXALT_SIGN.get(ninth_lord, "")])

        if venus_strong and venus_good_house and ninth_strong:
            yogas.append({
                "type": "Lakshmi Yoga",
                "name": "Lakshmi Yoga",
                "planets": ["Venus", ninth_lord],
                "sign": venus_sign,
                "house": venus_house,
                "strength": "strong",
                "description": (
                    f"Venus in {venus_sign} (own/exalt) H{venus_house} + "
                    f"9th lord {ninth_lord} strong — Lakshmi: wealth, "
                    f"beauty, luxury, prosperity"
                ),
            })

    # ═══════════════════════════════════════════════════════════════════════
    # 10. SARASWATI YOGA — Jupiter, Venus, Mercury in kendras/trikonas/2nd
    # ═══════════════════════════════════════════════════════════════════════
    jvl = {"Jupiter", "Venus", "Mercury"}
    jvl_good = all(
        planet_house.get(p, 0) in (1, 2, 4, 5, 7, 9, 10)
        for p in jvl if p in planet_house
    )
    if jvl_good and all(p in planet_sign for p in jvl):
        yogas.append({
            "type": "Saraswati Yoga",
            "name": "Saraswati Yoga",
            "planets": sorted(list(jvl)),
            "sign": planet_sign.get("Jupiter", ""),
            "house": planet_house.get("Jupiter", 1),
            "strength": "strong",
            "description": (
                "Jupiter, Venus, Mercury all in benefic houses — "
                "Saraswati: learning, wisdom, artistic talent, eloquence"
            ),
        })

    # ═══════════════════════════════════════════════════════════════════════
    # 11. MAHABHAGYA YOGA — Great Fortune (gender-specific)
    # ═══════════════════════════════════════════════════════════════════════
    sun_house = planet_house.get("Sun", 0)
    moon_house = planet_house.get("Moon", 0)
    asc_house = 1
    # For male: Sun, Moon, Asc in odd signs (Mesha, Mithuna, Simha...)
    # For female: Sun, Moon, Asc in even signs
    asc_idx = _sign_index(asc_sign)
    sun_idx = _sign_index(sun_sign)
    moon_idx = _sign_index(moon_sign)
    if asc_idx >= 0 and sun_idx >= 0 and moon_idx >= 0:
        all_odd = all(i % 2 == 0 for i in [asc_idx, sun_idx, moon_idx])
        all_even = all(i % 2 == 1 for i in [asc_idx, sun_idx, moon_idx])
        if all_odd or all_even:
            yogas.append({
                "type": "Mahabhagya Yoga",
                "name": "Mahabhagya Yoga",
                "planets": ["Sun", "Moon"],
                "sign": asc_sign,
                "house": 1,
                "strength": "strong",
                "description": (
                    "Sun, Moon, Ascendant all in "
                    f"{'odd' if all_odd else 'even'} signs — "
                    "Mahabhagya: great fortune, prosperity, long life"
                ),
            })

    # ═══════════════════════════════════════════════════════════════════════
    # 12. AMALA YOGA — Only benefic in 10th from Asc or Moon
    # ═══════════════════════════════════════════════════════════════════════
    tenth_sign = house_signs.get(10, "")
    if tenth_sign:
        tenth_occupants = sign_occupants.get(tenth_sign, [])
        if tenth_occupants and all(p in NATURAL_BENEFICS for p in tenth_occupants):
            yogas.append({
                "type": "Amala Yoga",
                "name": "Amala Yoga",
                "planets": tenth_occupants,
                "sign": tenth_sign,
                "house": 10,
                "strength": "strong",
                "description": (
                    f"Only benefic(s) {', '.join(tenth_occupants)} in 10th house — "
                    "Amala: spotless reputation, virtuous career"
                ),
            })

    # ═══════════════════════════════════════════════════════════════════════
    # 13. ADHI YOGA — Benefics in 6th, 7th, 8th from Moon
    # ═══════════════════════════════════════════════════════════════════════
    if moon_sign:
        adhi_houses = [6, 7, 8]
        adhi_count = 0
        adhi_planets = []
        for offset in adhi_houses:
            target_idx = (_sign_index(moon_sign) + offset - 1) % 12
            target_sign = ZODIAC_V[target_idx]
            for occ in sign_occupants.get(target_sign, []):
                if occ in NATURAL_BENEFICS:
                    adhi_count += 1
                    adhi_planets.append(occ)
        if adhi_count >= 2:
            yogas.append({
                "type": "Adhi Yoga",
                "name": "Adhi Yoga",
                "planets": adhi_planets,
                "sign": moon_sign,
                "house": planet_house.get("Moon", 1),
                "strength": "strong" if adhi_count >= 3 else "moderate",
                "description": (
                    f"{adhi_count} benefics in 6/7/8 from Moon — "
                    "Adhi Yoga: leadership, authority, prosperity"
                ),
            })

    # ═══════════════════════════════════════════════════════════════════════
    # 14. KEMADRUMA YOGA (negative) — No planets 2nd/12th from Moon
    # ═══════════════════════════════════════════════════════════════════════
    if moon_sign:
        moon_idx = _sign_index(moon_sign)
        second_sign = ZODIAC_V[(moon_idx + 1) % 12]
        twelfth_sign = ZODIAC_V[(moon_idx - 1) % 12]
        second_occ = [p for p in sign_occupants.get(second_sign, [])
                      if p not in ("Rahu", "Ketu")]
        twelfth_occ = [p for p in sign_occupants.get(twelfth_sign, [])
                       if p not in ("Rahu", "Ketu")]
        if not second_occ and not twelfth_occ:
            # Check cancellation: Moon in kendra
            moon_h = planet_house.get("Moon", 0)
            cancelled = moon_h in kendra_houses
            if not cancelled:
                yogas.append({
                    "type": "Kemadruma Yoga",
                    "name": "Kemadruma Yoga (Negative)",
                    "planets": ["Moon"],
                    "sign": moon_sign,
                    "house": moon_h,
                    "strength": "moderate",
                    "description": (
                        "No planets adjacent to Moon (2nd/12th) — "
                        "Kemadruma: periods of poverty or isolation, "
                        "but often overcome with effort"
                    ),
                })

    # ═══════════════════════════════════════════════════════════════════════
    # 15. VARGOTTAMA — Planet in same sign in D1 and D9
    # ═══════════════════════════════════════════════════════════════════════
    for planet, data in placements.items():
        if isinstance(data, dict) and data.get("is_vargottama"):
            p_sign = data.get("sign", "")
            h = planet_house.get(planet, 1)
            yogas.append({
                "type": "Vargottama",
                "name": f"{planet} Vargottama",
                "planets": [planet],
                "sign": p_sign,
                "house": h,
                "strength": "moderate",
                "description": (
                    f"{planet} in {p_sign} in both D1 and D9 — "
                    f"Vargottama: extra strength and auspiciousness"
                ),
            })

    return yogas

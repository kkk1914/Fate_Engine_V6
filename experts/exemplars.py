"""Few-Shot Exemplar Knowledge Base.

Curated interpretation examples from classical astrological texts,
organized by system and configuration. Injected into expert prompts
to give the LLM "experienced astrologer" interpretation patterns.

Instead of fine-tuning (expensive, inflexible), we inject 2-3 relevant
exemplars into each expert call based on keyword matching against the
chart data. This dramatically improves interpretation quality for ~200
tokens of extra prompt per expert.

Exemplars are organized by:
  - System (Western, Vedic, Saju, Hellenistic)
  - Configuration type (planet-in-sign, aspect, dasha, transit, yoga, etc.)
  - Keywords that trigger selection
"""

from typing import List, Dict, Any

# ═══════════════════════════════════════════════════════════════════════════
# WESTERN EXEMPLARS
# ═══════════════════════════════════════════════════════════════════════════

WESTERN_EXEMPLARS = [
    {
        "keywords": ["Saturn", "conjunct", "Midheaven", "MC", "career", "10th"],
        "title": "Saturn conjunct MC — Career Restructuring",
        "text": (
            "When transiting Saturn conjoins the natal Midheaven, the native faces "
            "a defining career moment: either a promotion earned through years of "
            "discipline, or a forced restructuring that strips away false ambitions. "
            "This is NOT a crisis — it is Saturn's gift of clarity. The native must "
            "ask: 'Is this my true vocation?' If yes, authority consolidates. If no, "
            "the structure crumbles so something authentic can replace it. "
            "Timing: exact conjunction ± 2 months is the pivot. The 6 months before "
            "are pressure-building; the 6 months after are implementation."
        ),
    },
    {
        "keywords": ["Jupiter", "transit", "4th", "home", "property", "real estate"],
        "title": "Jupiter transiting 4th House — Home Expansion",
        "text": (
            "Jupiter's transit through the 4th house is the classical indicator of "
            "property acquisition. The native feels an expansive pull toward roots: "
            "buying a home, upgrading living space, or resolving family matters. "
            "The effect is strongest when Jupiter also aspects the natal Moon or "
            "4th house ruler. When combined with a favorable Solar Return showing "
            "4th house emphasis, property purchase becomes highly probable. "
            "Key: Jupiter here does not guarantee purchase — it opens the door. "
            "Saturn's concurrent position determines whether the native CAN act."
        ),
    },
    {
        "keywords": ["Pluto", "transit", "Ascendant", "transformation", "identity"],
        "title": "Pluto transit to Ascendant — Identity Metamorphosis",
        "text": (
            "Pluto's transit over the Ascendant is one of the most profound "
            "experiences in Western astrology. The native undergoes a complete "
            "identity transformation — not cosmetic, but cellular. Physical "
            "appearance often changes. The persona the native has maintained "
            "since youth dissolves, and what emerges is rawer and more authentic. "
            "This transit often coincides with a health crisis, power struggle, "
            "or confrontation with mortality that catalyzes the transformation. "
            "Duration: the approach phase (2° applying) can last 1-2 years."
        ),
    },
    {
        "keywords": ["Solar Arc", "Venus", "relationship", "marriage", "partnership"],
        "title": "Solar Arc Venus to Angle — Relationship Milestone",
        "text": (
            "When Solar Arc Venus reaches a conjunction, square, or opposition "
            "to a natal angle (Asc, MC, Dsc, IC), a relationship milestone is "
            "almost certain within ± 6 months of exact. SA Venus to Dsc = "
            "marriage or committed partnership. SA Venus to MC = career benefit "
            "through relationships or artistic success. SA Venus to Asc = "
            "personal magnetism peak, often coinciding with physical enhancement. "
            "This is one of the most reliable timing techniques for love events."
        ),
    },
    {
        "keywords": ["progressed", "Moon", "sign", "change", "phase"],
        "title": "Progressed Moon Sign Change — Emotional Chapter Shift",
        "text": (
            "Every ~2.5 years the progressed Moon changes sign, marking a "
            "distinct emotional chapter. The sign it enters colors the native's "
            "emotional needs, domestic focus, and instinctive responses for the "
            "next 2.5 years. Progressed Moon entering Cancer = nesting, family "
            "focus, possible pregnancy. Entering Capricorn = emotional discipline, "
            "career ambition overtakes personal life. The month of the sign "
            "change itself is often marked by a notable emotional event or shift."
        ),
    },
    {
        "keywords": ["Grand Trine", "pattern", "talent", "ease"],
        "title": "Grand Trine — Natural Talent Configuration",
        "text": (
            "The Grand Trine represents an area of natural, effortless talent — "
            "but also potential complacency. Fire Grand Trine: leadership, vision, "
            "inspiration. Earth: practical mastery, material talent. Air: intellectual "
            "brilliance, social grace. Water: emotional intelligence, healing gift. "
            "The trine MUST be activated by transit or progression to a trine planet "
            "for the talent to manifest as achievement rather than wasted potential."
        ),
    },
]

# ═══════════════════════════════════════════════════════════════════════════
# VEDIC EXEMPLARS
# ═══════════════════════════════════════════════════════════════════════════

VEDIC_EXEMPLARS = [
    {
        "keywords": ["Jupiter", "Mahadasha", "Dasha", "benefic", "expansion"],
        "title": "Jupiter Mahadasha — 16-Year Expansion Cycle",
        "text": (
            "Jupiter Mahadasha (16 years) activates wisdom, dharma, children, "
            "and spiritual growth. Its effects depend entirely on Jupiter's natal "
            "position: in Karka (exalted) = maximum auspiciousness; in Makara "
            "(debilitated) = false promises and overextension. The antardasha "
            "sequence matters: Jupiter/Jupiter (first sub) = initial expansion; "
            "Jupiter/Saturn = reality check and consolidation; Jupiter/Mercury = "
            "learning and communication emphasis. Jupiter dasha ALWAYS brings "
            "at least one teacher, guru, or mentor into the native's life."
        ),
    },
    {
        "keywords": ["Saturn", "Mahadasha", "Dasha", "karma", "discipline"],
        "title": "Saturn Mahadasha — 19-Year Karmic Reckoning",
        "text": (
            "Saturn Mahadasha (19 years) is feared but misunderstood. It rewards "
            "discipline and punishes shortcuts. For charts where Saturn is yogakaraka "
            "(rules both a kendra and trikona), this is the BEST dasha — bringing "
            "authority, land, and institutional power. For charts where Saturn is a "
            "functional malefic, expect career restructuring, health challenges "
            "(bones, joints, teeth), and relationship tests in the first 5 years. "
            "Saturn/Venus antardasha is often the best sub-period — luxury earned "
            "through hard work. Saturn/Mars is the most difficult — conflict, "
            "surgery risk, energy depletion."
        ),
    },
    {
        "keywords": ["Rahu", "Dasha", "obsession", "foreign", "unconventional"],
        "title": "Rahu Mahadasha — 18-Year Transformation Cycle",
        "text": (
            "Rahu Mahadasha (18 years) brings intense worldly ambition, foreign "
            "connections, unconventional paths, and often a complete break from "
            "tradition. Rahu amplifies the house it occupies: Rahu in 10th = "
            "meteoric career rise (but potentially through deception or shortcuts). "
            "Rahu in 7th = foreign spouse or unconventional partnership. "
            "The native MUST guard against: obsessive behavior, substance abuse, "
            "and ethical shortcuts. Rahu/Jupiter antardasha often brings the "
            "biggest opportunities but also the biggest ethical tests."
        ),
    },
    {
        "keywords": ["Raja", "Yoga", "kendra", "trikona", "power"],
        "title": "Raja Yoga — Power and Authority Combination",
        "text": (
            "Raja Yoga forms when lords of kendras (1,4,7,10) and trikonas (1,5,9) "
            "are conjoined, in mutual aspect, or in exchange. The yoga only manifests "
            "during the dasha/antardasha of the participating planets. A dormant "
            "Raja Yoga gives potential; activation gives results. The strongest "
            "Raja Yogas involve the 9th and 10th lords together — this is the "
            "Dharma-Karma Adhipati Yoga, the king of Raja Yogas, bringing authority "
            "that comes with genuine merit and public recognition."
        ),
    },
    {
        "keywords": ["Gajakesari", "Jupiter", "Moon", "fame", "wisdom"],
        "title": "Gajakesari Yoga — Elephant-Lion Combination",
        "text": (
            "Gajakesari Yoga (Jupiter in kendra from Moon) gives intelligence, "
            "wealth, fame, and lasting reputation. Its strength depends on: "
            "1) Jupiter's dignity — exalted Jupiter in Cancer from Moon = maximum; "
            "2) Moon's strength — waxing Moon amplifies, waning Moon weakens; "
            "3) Whether either planet is combust, retrograde, or aspected by malefics. "
            "A strong Gajakesari ensures the native's name endures beyond their lifetime."
        ),
    },
    {
        "keywords": ["Navamsa", "D9", "marriage", "spouse", "dharma"],
        "title": "Navamsa (D9) — Marriage and Dharmic Path",
        "text": (
            "The D9 chart reveals: 1) The nature and quality of marriage/partnership, "
            "2) The native's dharmic (spiritual) path in the second half of life, "
            "3) The true strength of planets (vargottama = planet in same sign D1 & D9 = "
            "extra strength). Venus in D9 shows spouse's nature. 7th lord in D9 shows "
            "marriage quality. Planets debilitated in D1 but exalted in D9 = late bloomer."
        ),
    },
    {
        "keywords": ["Ashtakavarga", "transit", "bindu", "SAV"],
        "title": "Ashtakavarga Transit Quality — Bindu-Based Timing",
        "text": (
            "When Saturn transits a sign with high SAV bindus (28+), that transit "
            "period brings consolidation and reward. Low SAV (below 25) = that "
            "transit brings restriction and loss. This technique refines gross "
            "transit predictions: Saturn in 7th is not automatically bad if "
            "the 7th house has 30+ SAV bindus — it means the relationship "
            "testing will end in strengthened commitment, not dissolution."
        ),
    },
]

# ═══════════════════════════════════════════════════════════════════════════
# SAJU/BAZI EXEMPLARS
# ═══════════════════════════════════════════════════════════════════════════

SAJU_EXEMPLARS = [
    {
        "keywords": ["Da Yun", "luck", "pillar", "decade", "10-year"],
        "title": "Da Yun Transition — Decade Luck Shift",
        "text": (
            "When the Da Yun (10-year luck pillar) changes, the native's life "
            "context shifts dramatically — like changing seasons. The transition "
            "year (±1 year from the start of a new pillar) is the most turbulent. "
            "If the new pillar's element supports the Day Master's useful god, "
            "the decade brings opportunity. If it controls or drains the Day Master, "
            "the decade requires defensive strategy. The STEM of the pillar "
            "governs the first 5 years; the BRANCH governs the second 5 years."
        ),
    },
    {
        "keywords": ["clash", "Chong", "opposition", "conflict"],
        "title": "Branch Clash (Chong) — Disruption and Change",
        "text": (
            "When a Liu Nian (annual branch) clashes with a natal branch, "
            "that year brings disruption in the pillar's domain. Year pillar "
            "clash = family/ancestral disruption. Month pillar clash = career "
            "change or authority conflict. Day pillar clash = marriage/relationship "
            "upheaval. Hour pillar clash = children issues or late-life change. "
            "Clashes are not inherently negative — they FORCE change, which can be "
            "liberation from stagnation. If the useful god is involved, the clash "
            "removes obstacles rather than creating them."
        ),
    },
    {
        "keywords": ["Day Master", "strength", "strong", "weak", "balance"],
        "title": "Day Master Strength — Foundation of All Analysis",
        "text": (
            "The Day Master's strength determines which elements are favorable: "
            "Strong DM (score > 60): needs Wealth (element it controls), Output "
            "(element it produces), and Power (element that controls it) to drain "
            "excess energy into productive channels. Weak DM (score < 40): needs "
            "Resource (element that produces it) and Companion (same element) "
            "for support. A balanced DM (40-60) adapts to annual flows. "
            "The useful god is the SINGLE most important element for the chart."
        ),
    },
    {
        "keywords": ["Peach Blossom", "romance", "relationship", "attraction"],
        "title": "Peach Blossom Star — Romance and Attraction",
        "text": (
            "Peach Blossom (桃花) activates when its branch appears in a Da Yun "
            "or Liu Nian pillar. For a chart with Peach Blossom on 酉 (Rooster): "
            "any year or decade with 酉 in its branch triggers romantic opportunity. "
            "If the native is single, expect a significant meeting. If partnered, "
            "expect renewed attraction or — if other indicators are malefic — "
            "a temptation. Peach Blossom is amplified if Venus or Moon aspects "
            "are simultaneously active in Western/Vedic systems."
        ),
    },
]

# ═══════════════════════════════════════════════════════════════════════════
# HELLENISTIC EXEMPLARS
# ═══════════════════════════════════════════════════════════════════════════

HELLENISTIC_EXEMPLARS = [
    {
        "keywords": ["Zodiacal Releasing", "ZR", "Fortune", "L2", "career"],
        "title": "Zodiacal Releasing L2 Peak — Career Culmination",
        "text": (
            "When the ZR L2 period reaches the sign opposite its starting sign "
            "(the 'Loosing of the Bond'), the native hits a peak or crisis in "
            "the lot's domain. For Fortune: career/material peak — this is when "
            "promotions, windfalls, or major acquisitions occur. The peak lasts "
            "for the duration of that L2 sub-period (typically 1-5 years). "
            "After the peak, the next L2 period begins the descent — which is "
            "not decline but consolidation of what was gained at the peak."
        ),
    },
    {
        "keywords": ["Profection", "time lord", "annual", "activated"],
        "title": "Annual Profection — Year Lord Activation",
        "text": (
            "The profected year lord is the MOST IMPORTANT planet for that year. "
            "Whatever house that planet rules natally, whatever aspects it makes "
            "natally, whatever transits it receives that year — all of these are "
            "amplified. Example: 4th house profection year (age 27, 39, 51) "
            "with Moon as time lord and Saturn transiting natal Moon = a year "
            "of domestic restructuring (moving, renovation, family crisis). "
            "The profection tells you WHICH planet to watch; transits tell you WHEN."
        ),
    },
    {
        "keywords": ["Sect", "day", "night", "benefic", "malefic"],
        "title": "Sect — The Foundation of Hellenistic Analysis",
        "text": (
            "Sect determines which planets are most beneficial or harmful. "
            "In a day chart: Jupiter is the most powerful benefic (it is both "
            "naturally benefic AND in sect), while Mars is the most problematic "
            "(naturally malefic AND contrary to sect). In a night chart: Venus "
            "replaces Jupiter as the greatest benefic, and Saturn becomes the "
            "most difficult planet. The sect malefic's house placement shows "
            "where the native will face their greatest challenges in life."
        ),
    },
    {
        "keywords": ["Firdaria", "firdar", "time lord", "Persian"],
        "title": "Firdaria — Persian Time Lord System",
        "text": (
            "Firdaria divides life into planetary periods (7-12 years each). "
            "The firdar lord's natal condition determines the quality of that "
            "life chapter. A firdar ruled by a well-placed Jupiter in a night "
            "chart (where Jupiter is contrary to sect) will bring expansion "
            "but with unexpected complications. The most powerful prediction "
            "combines firdar lord + profection lord + ZR period: when all three "
            "point to the same house or planet, events are virtually certain."
        ),
    },
]


def select_exemplars(system: str, chart_data: dict,
                     max_exemplars: int = 3) -> str:
    """Select the most relevant exemplars for a given expert based on chart data.

    Uses keyword matching against the chart data to find the most relevant
    exemplar interpretations.

    Args:
        system: "Western", "Vedic", "Saju", "Hellenistic"
        chart_data: Full chart data dict
        max_exemplars: Maximum exemplars to return (default 3)

    Returns:
        Formatted string block to inject into expert prompt
    """
    exemplar_bank = {
        "Western": WESTERN_EXEMPLARS,
        "Vedic": VEDIC_EXEMPLARS,
        "Saju": SAJU_EXEMPLARS,
        "Hellenistic": HELLENISTIC_EXEMPLARS,
    }

    bank = exemplar_bank.get(system, [])
    if not bank:
        return ""

    # Build a keyword set from the chart data
    chart_keywords = _extract_chart_keywords(system, chart_data)

    # Score each exemplar by keyword overlap
    scored = []
    for ex in bank:
        score = sum(1 for kw in ex["keywords"]
                    if any(kw.lower() in ck.lower() for ck in chart_keywords))
        if score > 0:
            scored.append((score, ex))

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [ex for _, ex in scored[:max_exemplars]]

    if not selected:
        # Fallback: always include at least 1 exemplar (the most general one)
        selected = bank[:1]

    # Format as prompt injection
    lines = [
        "═══ INTERPRETATION EXEMPLARS (use these as quality benchmarks) ═══",
        "The following are examples of how a master astrologer interprets ",
        "similar configurations. Match this level of specificity and depth.",
        "",
    ]
    for i, ex in enumerate(selected, 1):
        lines.append(f"Example {i}: {ex['title']}")
        lines.append(ex["text"])
        lines.append("")

    lines.append("═══ END EXEMPLARS ═══")
    return "\n".join(lines)


def _extract_chart_keywords(system: str, chart_data: dict) -> set:
    """Extract relevant keywords from chart data for exemplar matching."""
    keywords = set()

    if system == "Western":
        w = chart_data.get("western", {})
        # Add planet names from aspects
        for asp in w.get("natal", {}).get("aspects", []):
            keywords.add(asp.get("p1", ""))
            keywords.add(asp.get("p2", ""))
            keywords.add(asp.get("type", ""))
        # Add pattern names
        patterns = w.get("natal", {}).get("patterns", {})
        if patterns.get("grand_trines"):
            keywords.add("Grand Trine")
        if patterns.get("t_squares"):
            keywords.add("T-Square")
        # Add transit planets
        for hit in w.get("predictive", {}).get("outer_transit_aspects", {}).get("all_hits", []):
            keywords.add(hit.get("transiting", ""))
            keywords.add(hit.get("natal_point", ""))
            keywords.add(hit.get("aspect", ""))
        # Progression info
        progs = w.get("predictive", {}).get("progressions", {})
        if progs.get("lunar_phase", {}).get("phase"):
            keywords.add("progressed")
            keywords.add("Moon")
            keywords.add("phase")
        for pa in progs.get("prog_natal_aspects", []):
            keywords.add(pa.get("progressed", ""))
            keywords.add(pa.get("natal", ""))
        # Solar Arc
        if w.get("predictive", {}).get("solar_arc_degrees", 0) > 0:
            keywords.add("Solar Arc")

    elif system == "Vedic":
        v = chart_data.get("vedic", {})
        # Dasha lord
        dasha = v.get("predictive", {}).get("vimshottari", {})
        if dasha.get("maha_lord"):
            keywords.add(dasha["maha_lord"])
            keywords.add("Mahadasha")
            keywords.add("Dasha")
        if dasha.get("antar_lord"):
            keywords.add(dasha["antar_lord"])
        # Yogas
        for yoga in v.get("natal", {}).get("yogas", []):
            keywords.add(yoga.get("type", ""))
            keywords.add(yoga.get("name", ""))
            for p in yoga.get("planets", yoga.get("members", [])):
                keywords.add(p)
        # Dignities
        for p, d in v.get("natal", {}).get("placements", {}).items():
            if isinstance(d, dict):
                if d.get("dignity") in ("Exalted", "Debilitated"):
                    keywords.add(d["dignity"])
                    keywords.add(p)
                if d.get("is_vargottama"):
                    keywords.add("Navamsa")
                    keywords.add("D9")
        # Ashtakavarga
        if v.get("strength", {}).get("ashtakavarga_full", {}).get("sarva"):
            keywords.add("Ashtakavarga")
            keywords.add("bindu")
            keywords.add("SAV")

    elif system == "Saju":
        s = chart_data.get("bazi", {})
        # Day Master element
        strength = s.get("strength", {})
        if strength.get("dm_element"):
            keywords.add("Day Master")
            keywords.add(strength["dm_element"])
            keywords.add(strength.get("tier", ""))
        if strength.get("useful_god"):
            keywords.add(strength["useful_god"])
        # Da Yun
        keywords.add("Da Yun")
        keywords.add("luck")
        keywords.add("pillar")
        # Interactions
        inter = s.get("natal", {}).get("interactions", {})
        if inter.get("clashes"):
            keywords.add("clash")
            keywords.add("Chong")
        # Spirit stars
        for star in s.get("natal", {}).get("shensha", []):
            if star.get("activated_in_chart"):
                keywords.add(star.get("type", "").split("(")[0].strip())
                keywords.add(star.get("domain", ""))

    elif system == "Hellenistic":
        h = chart_data.get("hellenistic", {})
        # ZR
        if h.get("zodiacal_releasing"):
            keywords.add("Zodiacal Releasing")
            keywords.add("ZR")
            keywords.add("Fortune")
        # Profections
        if h.get("annual_profections"):
            keywords.add("Profection")
            keywords.add("time lord")
        # Sect
        if h.get("sect"):
            keywords.add("Sect")
            keywords.add("day" if h["sect"].get("is_day_chart") else "night")
        # Firdaria
        if h.get("firdaria"):
            keywords.add("Firdaria")
            keywords.add("firdar")

    # Remove empty strings
    keywords.discard("")
    return keywords

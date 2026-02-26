# =========================================
# seed_vedic.py
# =========================================
# Seeds Vedic_engine (Jyotish) rules into Neo4j using your current graph model:
# (System {name})-[:USES]->(Placement {name})-[:IN_SIGN {meaning,themes,chapter}]->(Sign {name})
# =========================================
import os
from neo4j import GraphDatabase

def get_db_driver():
    """Neo4j driver (env-configured)."""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD")
    if not uri or not pwd:
        raise ValueError("Missing Neo4j credentials. Set NEO4J_URI and NEO4J_PASSWORD (and optionally NEO4J_USER).")
    return GraphDatabase.driver(uri, auth=(user, pwd))

# Remove these lines that cause errors:
# NEO4J_URI = os.getenv("NEO4J_URI").strip()
# NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
# NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD").strip()

def ensure_constraints(driver):
    constraints = [
        "CREATE CONSTRAINT system_name IF NOT EXISTS FOR (s:System) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT placement_name IF NOT EXISTS FOR (p:Placement) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT sign_name IF NOT EXISTS FOR (z:Sign) REQUIRE z.name IS UNIQUE",
        "CREATE CONSTRAINT rule_key IF NOT EXISTS FOR (r:Rule) REQUIRE (r.system, r.placement, r.sign, r.chapter) IS UNIQUE",
    ]
    with driver.session() as session:
        for c in constraints:
            session.run(c)


# --------------------------
# Core Vedic_engine zodiac (Rasi)
# --------------------------

RASI = {
    "Mesha": {
        "themes": ["Fire", "Action", "Initiative"],
        "flavor": "acts fast and directly, prioritizing courage, competition, and decisive movement."
    },
    "Vrishabha": {
        "themes": ["Earth", "Stability", "Comfort"],
        "flavor": "builds slowly and securely, prioritizing material stability, beauty, and consistency."
    },
    "Mithuna": {
        "themes": ["Air", "Intellect", "Duality"],
        "flavor": "operates through mental agility, trade-offs, learning, and flexible social intelligence."
    },
    "Karka": {
        "themes": ["Water", "Emotion", "Nurturing"],
        "flavor": "moves by feeling, prioritizing belonging, protection, and emotional security."
    },
    "Simha": {
        "themes": ["Fire", "Leadership", "Dharma"],
        "flavor": "seeks honor and recognition, expressing confidence, loyalty, and authority."
    },
    "Kanya": {
        "themes": ["Earth", "Service", "Purity"],
        "flavor": "refines and improves, prioritizing systems, detail, health, and practical solutions."
    },
    "Tula": {
        "themes": ["Air", "Balance", "Diplomacy"],
        "flavor": "seeks harmony and fairness, prioritizing partnership, aesthetics, and negotiation."
    },
    "Vrischika": {
        "themes": ["Water", "Intensity", "Occult"],
        "flavor": "goes deep and does not compromise, prioritizing truth, control, and transformation."
    },
    "Dhanus": {
        "themes": ["Fire", "Wisdom", "Grace"],
        "flavor": "expands outward, prioritizing meaning, ethics, teachers, and higher learning."
    },
    "Makara": {
        "themes": ["Earth", "Karma", "Effort"],
        "flavor": "builds through pressure and time, prioritizing mastery, structure, and long-term achievement."
    },
    "Kumbha": {
        "themes": ["Air", "Society", "Detachment"],
        "flavor": "thinks in systems and collectives, prioritizing reform, innovation, and group outcomes."
    },
    "Meena": {
        "themes": ["Water", "Moksha", "Surrender"],
        "flavor": "dissolves boundaries, prioritizing compassion, imagination, spirituality, and release."
    }
}


# --------------------------
# Seed rule generators
# --------------------------

def generate_rasi_rules_for_placements(placements, system_name="Vedic_engine"):
    """
    placements: list of dicts: {name, chapter, desc}
    Seeds: Placement x Rasi -> meaning/themes/chapter
    """
    rules = []
    for pl in placements:
        for rasi_name, rasi_data in RASI.items():
            rules.append({
                "system": system_name,
                "planet": pl["name"],
                "sign": rasi_name,
                "chapter": pl["chapter"],
                "themes": rasi_data["themes"],
                "meaning": f"{pl['desc']}. In {rasi_name}, it {rasi_data['flavor']}"
            })
    return rules


def vedic_d1_core_placements():
    """
    These align with your current math output style where:
      results["Vedic_engine"]["Placements"][planet]["sign"] = rasi
      results["Vedic_engine"]["Houses"]["Bhava_1"]["sign"] = rasi
    """
    return [
        # Identity
        {"name": "Sun", "chapter": "Identity", "desc": "Soul (Atma), vitality, authority and confidence"},
        {"name": "Moon", "chapter": "Identity", "desc": "Mind (Manas), emotional patterns, comfort needs"},
        {"name": "Ascendant", "chapter": "Identity", "desc": "Body, life direction, and how life meets you"},
        {"name": "Mercury", "chapter": "Identity", "desc": "Intellect, speech, learning loops, nervous system"},
        {"name": "Venus", "chapter": "Relationships", "desc": "Romance, bonding, pleasure, values and attraction"},
        {"name": "Mars", "chapter": "Relationships", "desc": "Drive, courage, conflict style, heat and ambition"},
        {"name": "Jupiter", "chapter": "Finances", "desc": "Wisdom, expansion, wealth-building, mentors and ethics"},
        {"name": "Saturn", "chapter": "Career", "desc": "Discipline, duty, delay, pressure and long-term results"},
        {"name": "Rahu", "chapter": "Destiny", "desc": "Desire, obsession, foreign influence, ambition and hunger"},
        {"name": "Ketu", "chapter": "Destiny", "desc": "Detachment, liberation, sharp insight and past-life residue"},

        # Bhavas as “placements” (your DB fetch passes Bhava_# as planet)
        {"name": "Bhava_1", "chapter": "Identity", "desc": "Self, constitution, and baseline life conditions"},
        {"name": "Bhava_2", "chapter": "Finances", "desc": "Money, family assets, speech and accumulated resources"},
        {"name": "Bhava_3", "chapter": "Health", "desc": "Courage, effort, stamina and short journeys"},
        {"name": "Bhava_4", "chapter": "Destiny", "desc": "Home, mother, inner peace and property"},
        {"name": "Bhava_5", "chapter": "Destiny", "desc": "Merit, creativity, children, intelligence"},
        {"name": "Bhava_6", "chapter": "Health", "desc": "Illness, debt, enemies, routines and service"},
        {"name": "Bhava_7", "chapter": "Relationships", "desc": "Marriage, contracts, partners and open enemies"},
        {"name": "Bhava_8", "chapter": "Destiny", "desc": "Transformations, secrets, longevity, inheritance"},
        {"name": "Bhava_9", "chapter": "Destiny", "desc": "Dharma, teachers, higher meaning and fortune"},
        {"name": "Bhava_10", "chapter": "Career", "desc": "Work, status, public actions and legacy"},
        {"name": "Bhava_11", "chapter": "Finances", "desc": "Gains, networks, audience and desires"},
        {"name": "Bhava_12", "chapter": "Destiny", "desc": "Loss, isolation, foreign lands and liberation"},
    ]


def generate_dignity_rules():
    """
    Your math engine may output:
      results["Vedic_engine"]["Placements"][planet]["dignity"] = Exalted/Debilitated/Own Sign/Neutral
    Oracle can query: planet="Dignity", sign=<tier>.
    """
    meanings = {
        "Exalted": "Peak expression. The planet’s agenda is strongly supported and tends to show clear results.",
        "Debilitated": "Strained expression. Results require more strategy, time, and corrective effort.",
        "Own_Sign": "Stable expression. The planet functions with comfort and protects its outcomes.",
        "Neutral": "Standard expression. Results depend mainly on context, aspects, and timing."
    }
    rules = []
    for tier, meaning in meanings.items():
        rules.append({
            "system": "Vedic_engine",
            "planet": "Dignity",
            "sign": tier,
            "chapter": "Identity",
            "themes": ["Strength", "Karma", "Results"],
            "meaning": f"Dignity = {tier}. {meaning}"
        })
    return rules


def generate_atmakaraka_rules():
    """
    For Jaimini Atmakaraka:
      - Planet acting as AK: results["Vedic_engine"]["Atmakaraka"] = "Saturn"
      - AK sign (optional): results["Vedic_engine"]["Jaimini"]["AK_Sign"] = "Makara"
    Oracle queries:
      planet="Atmakaraka_Planet", sign=<planet>
      planet="Atmakaraka_Sign", sign=<rasi>
    """
    planet_meanings = {
        "Sun": "Soul lesson: authority, integrity, leadership without ego collapse.",
        "Moon": "Soul lesson: emotional mastery, security, intuition without dependency.",
        "Mars": "Soul lesson: courage, control of anger, decisive action without destruction.",
        "Mercury": "Soul lesson: skill, communication, strategy without manipulation or anxiety loops.",
        "Jupiter": "Soul lesson: wisdom, ethics, prosperity without hypocrisy or complacency.",
        "Venus": "Soul lesson: love, pleasure, values without addiction or avoidance.",
        "Saturn": "Soul lesson: duty, patience, endurance without bitterness or fear."
    }

    rules = []
    for pl, meaning in planet_meanings.items():
        rules.append({
            "system": "Vedic_engine",
            "planet": "Atmakaraka_Planet",
            "sign": pl,
            "chapter": "Destiny",
            "themes": ["Soul", "Karma", "Lesson"],
            "meaning": f"This planet is the Atmakaraka (Jaimini soul planet). {meaning}"
        })

    # AK sign uses Rasi flavors
    for rasi_name, rasi_data in RASI.items():
        rules.append({
            "system": "Vedic_engine",
            "planet": "Atmakaraka_Sign",
            "sign": rasi_name,
            "chapter": "Destiny",
            "themes": ["Soul", "Lesson"] + rasi_data["themes"],
            "meaning": f"Atmakaraka in {rasi_name}: the soul lesson expresses through this archetype. It {rasi_data['flavor']}"
        })

    return rules


def generate_vargottama_rules():
    """
    If a planet is Vargottama (same sign in D1 and D9):
      results["Vedic_engine"]["Placements"][planet]["is_vargottama"] = True
    Oracle queries:
      planet="Vargottama", sign=<planet> (e.g., 'Venus')
    """
    planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
    rules = []
    for p in planets:
        rules.append({
            "system": "Vedic_engine",
            "planet": "Vargottama",
            "sign": p,
            "chapter": "Destiny",
            "themes": ["Power", "Purity", "Inevitability"],
            "meaning": f"{p} is Vargottama (same sign in D1 and D9). This amplifies results and makes its themes hard to avoid over time."
        })
    return rules


def generate_shadbala_tier_rules():
    """
    Shadbala is heavy; seed tier meanings so oracle can flag:
      planet=f"Shadbala_{planet}", sign=<tier>
    tiers are consistent across planets.
    """
    tiers = {
        "Very_Strong": "High capacity: results tend to be reliable, visible, and repeatable.",
        "Strong": "Good capacity: results come with reasonable effort and consistency.",
        "Average": "Mixed capacity: results depend on timing, support, and choices.",
        "Weak": "Low capacity: results require strategy, support, and patience.",
        "Very_Weak": "Strained capacity: results are delayed; needs careful structure and remediation."
    }
    planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
    rules = []
    for p in planets:
        for tier, meaning in tiers.items():
            rules.append({
                "system": "Vedic_engine",
                "planet": f"Shadbala_{p}",
                "sign": tier,
                "chapter": "Identity",
                "themes": ["Strength", "Results", "Capacity"],
                "meaning": f"Shadbala tier for {p} = {tier}. {meaning}"
            })
    return rules


def generate_ashtakavarga_sav_rules():
    """
    Minimal Ashtakavarga: Sarva Ashtakavarga (SAV) per sign tier.
    Oracle queries:
      planet=f"SAV_{rasi}", sign=<tier>
    """
    tiers = {
        "High": "This sign carries supportive bindus: outcomes here tend to feel smoother and more protected.",
        "Above_Average": "This sign is supportive: opportunities arise with effort and correct timing.",
        "Average": "This sign is neutral: results depend on other chart factors and timing.",
        "Low": "This sign is strained: results require strategy and patience.",
        "Very_Low": "This sign is depleted: expect delays, friction, or higher effort costs."
    }

    rules = []
    for rasi_name, rasi_data in RASI.items():
        for tier, meaning in tiers.items():
            rules.append({
                "system": "Vedic_engine",
                "planet": f"SAV_{rasi_name}",
                "sign": tier,
                "chapter": "Predictive",
                "themes": ["Timing", "Support"] + rasi_data["themes"],
                "meaning": f"Sarva Ashtakavarga for {rasi_name} = {tier}. {meaning}"
            })
    return rules


def generate_vedic_dataset_part1():
    """
    Part 1: core D1, dignity, AK/vargottama, shadbala tiers, SAV tiers.
    """
    rules = []
    rules.extend(generate_rasi_rules_for_placements(vedic_d1_core_placements(), system_name="Vedic_engine"))
    rules.extend(generate_dignity_rules())
    rules.extend(generate_atmakaraka_rules())
    rules.extend(generate_vargottama_rules())
    rules.extend(generate_shadbala_tier_rules())
    rules.extend(generate_ashtakavarga_sav_rules())
    return rules


def generate_vimshottari_rules():
    """
    Oracle should query:
      planet="Maha_Dasha", sign=<lord>
      planet="Antar_Dasha", sign=<lord>
    (You can add Pratyantar similarly later.)
    """
    dashas = {
        "Ketu": "Detachment, sudden breakshall, spiritual sharpenings, cutting illusions.",
        "Venus": "Comfort, relationships, art, luxuries, attraction, social leverage.",
        "Sun": "Visibility, authority tests, father/boss themes, identity pressure and confidence growth.",
        "Moon": "Home/emotions, public connection, nurture themes, psychological shifts.",
        "Mars": "Action, conflict, property/effort, ambition spikes, heat and courage.",
        "Rahu": "Obsession, foreign influence, acceleration, unusual opportunities, illusion-risk.",
        "Jupiter": "Wisdom, mentors, children, prosperity, expansion through ethics.",
        "Saturn": "Duty, delays, pressure, career building, karmic maturity and endurance.",
        "Mercury": "Learning, trade, communication, networking, skills, movement."
    }

    rules = []
    for lord, meaning in dashas.items():
        rules.append({
            "system": "Vedic_engine",
            "planet": "Maha_Dasha",
            "sign": lord,
            "chapter": "Predictive",
            "themes": ["Timeline", "Focus", "Karma"],
            "meaning": f"Current Maha Dasha lord = {lord}. Themes: {meaning}"
        })
        rules.append({
            "system": "Vedic_engine",
            "planet": "Antar_Dasha",
            "sign": lord,
            "chapter": "Predictive",
            "themes": ["Timeline", "Trigger", "Karma"],
            "meaning": f"Current Antar Dasha lord = {lord}. Sub-period themes: {meaning}"
        })
    return rules


def generate_yoga_rules():
    """
    Oracle should query: planet="Yoga", sign=<YogaName>
    """
    yogas = [
        {
            "name": "Raja_Yoga",
            "chapter": "Career",
            "themes": ["Power", "Status", "Authority"],
            "meaning": "Raja Yoga indicates elevation in status and authority when activated by timing. It rewards disciplined action and strategic alliances."
        },
        {
            "name": "Dhana_Yoga",
            "chapter": "Finances",
            "themes": ["Wealth", "Assets", "Prosperity"],
            "meaning": "Dhana Yoga supports money accumulation and asset-building when activated. It still requires execution and good financial behavior."
        },
        {
            "name": "Viparita_Raja_Yoga",
            "chapter": "Destiny",
            "themes": ["Reversal", "Survival", "Resilience"],
            "meaning": "Viparita Raja Yoga: strength through adversity. Difficult conditions flip into advantage when handled with strategy and endurance."
        },
        {
            "name": "Gaja_Kesari_Yoga",
            "chapter": "Identity",
            "themes": ["Respect", "Wisdom", "Protection"],
            "meaning": "Gaja Kesari Yoga supports dignity, social respect, and wise judgment. It improves outcomes through mentors and reputation."
        },
        {
            "name": "Neecha_Bhanga_Raja_Yoga",
            "chapter": "Destiny",
            "themes": ["Recovery", "Rise", "Redemption"],
            "meaning": "Neecha Bhanga Raja Yoga indicates recovery from weakness: setbacks become fuel for a later rise when timing activates the correction."
        },
    ]

    rules = []
    for y in yogas:
        rules.append({
            "system": "Vedic_engine",
            "planet": "Yoga",
            "sign": y["name"],
            "chapter": y["chapter"],
            "themes": y["themes"],
            "meaning": y["meaning"]
        })
    return rules


def generate_nakshatra_pada_rules():
    """
    Seeds 27 x 4 = 108 Nakshatra Pada rules.
    Oracle should query:
      planet="Nakshatra_Pada", sign="Ashwini_P1" (etc)
    """
    nakshatras = [
        "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha",
        "Magha", "Purva_Phalguni", "Uttara_Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
        "Jyeshtha", "Mula", "Purva_Ashadha", "Uttara_Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
        "Purva_Bhadrapada", "Uttara_Bhadrapada", "Revati"
    ]

    # Generic pada flavor (works as a “layer” on top of your existing Nakshatra rules)
    pada_meanings = {
        1: ("Dharma/Identity", "Pushes identity-building, status, initiation, and leadership lessons."),
        2: ("Resources/Values", "Pushes money, skill monetization, stability, and value-structure lessons."),
        3: ("Craft/Relationships", "Pushes social leverage, skill refinement, communication and partnership lessons."),
        4: ("Moksha/Inner Life", "Pushes emotional processing, detachment, intuition, and inner transformation lessons.")
    }

    rules = []
    for star in nakshatras:
        for p in [1, 2, 3, 4]:
            label, desc = pada_meanings[p]
            # Identity + Destiny are the most universal for padas
            for chapter in ["Identity", "Destiny"]:
                rules.append({
                    "system": "Vedic_engine",
                    "planet": "Nakshatra_Pada",
                    "sign": f"{star}_P{p}",
                    "chapter": chapter,
                    "themes": ["Nakshatra", "Pada", label],
                    "meaning": f"{star} Pada {p} emphasizes {label}. {desc}"
                })
    return rules


def generate_d10_rules():
    """
    D10 (Dasamsa) is career-focused.
    Oracle should query:
      planet="D10_Sun", sign=<rasi>
    """
    planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
    placements = [{
        "name": f"D10_{p}",
        "chapter": "Career",
        "desc": f"D10 (Dasamsa) placement for {p}: career expression, public role, and professional strengths/risks"
    } for p in planets]

    return generate_rasi_rules_for_placements(placements, system_name="Vedic_engine")


def generate_bhava_chalit_rules():
    """
    Bhava Chalit assigns planets to houses (Bhava_1..Bhava_12).
    In your current graph model we use Sign node to store "Bhava_#".
    Oracle queries:
      planet="Chalit_Sun", sign="Bhava_10"
    """
    bhava_meanings = {
        "Bhava_1": ("Identity", ["Self", "Body", "Direction"], "The planet strongly imprints identity, temperament, and life direction."),
        "Bhava_2": ("Finances", ["Money", "Speech", "Family"], "The planet strongly affects wealth, resources, speech, and family patterns."),
        "Bhava_3": ("Health", ["Effort", "Courage", "Skills"], "The planet amplifies effort, drive, communication loops, and stamina."),
        "Bhava_4": ("Destiny", ["Home", "Peace", "Property"], "The planet affects home life, emotional foundation, property and inner peace."),
        "Bhava_5": ("Destiny", ["Merit", "Creativity", "Children"], "The planet affects creativity, intelligence, romance/children themes and merit."),
        "Bhava_6": ("Health", ["Illness", "Debt", "Enemies"], "The planet activates routines, conflict, debts, health-maintenance and service."),
        "Bhava_7": ("Relationships", ["Marriage", "Contracts", "Partners"], "The planet affects partners, marriage dynamics, public interactions and agreements."),
        "Bhava_8": ("Destiny", ["Transformation", "Secrets", "Longevity"], "The planet triggers deep transformations, crises, occult and inheritance themes."),
        "Bhava_9": ("Destiny", ["Dharma", "Teachers", "Luck"], "The planet affects teachers, beliefs, fortune and meaning-making."),
        "Bhava_10": ("Career", ["Status", "Work", "Authority"], "The planet affects career outcomes, authority and visible results."),
        "Bhava_11": ("Finances", ["Gains", "Networks", "Audience"], "The planet affects gains, networks, fulfilment of desires and social leverage."),
        "Bhava_12": ("Destiny", ["Loss", "Foreign", "Liberation"], "The planet affects isolation, foreign lands, expenditure and spiritual release."),
    }

    planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
    rules = []
    for p in planets:
        for bhava, (chapter, themes, meaning) in bhava_meanings.items():
            rules.append({
                "system": "Vedic_engine",
                "planet": f"Chalit_{p}",
                "sign": bhava,
                "chapter": chapter,
                "themes": themes,
                "meaning": f"Bhava Chalit: {p} is placed in {bhava}. {meaning}"
            })
    return rules


def generate_vedic_dataset_part2():
    """
    Part 2: Vimshottari, Yogas, Nakshatra Padas, D10, Bhava Chalit.
    """
    rules = []
    rules.extend(generate_vimshottari_rules())
    rules.extend(generate_yoga_rules())
    rules.extend(generate_nakshatra_pada_rules())
    rules.extend(generate_d10_rules())
    rules.extend(generate_bhava_chalit_rules())
    return rules


def bulk_load_vedic(rules):
    driver = get_db_driver()
    query = """
        UNWIND $rules AS rule
        WITH rule, coalesce(rule.planet, rule.placement) AS placement
        MERGE (r:Rule {
          system: rule.system,
          placement: placement,
          sign: rule.sign,
          chapter: rule.chapter
        })
        ON CREATE SET 
          r.created_at = datetime()
        SET
          r.meaning = rule.meaning,
          r.themes  = coalesce(rule.themes, []),
          r.updated_at = datetime()
        """
    with driver.session() as session:
        session.execute_write(lambda tx: tx.run(query, rules=rules))
    driver.close()


if __name__ == "__main__":
    print("Generating Vedic_engine Master Dataset (Part 1 + Part 2)...")

    # If you're stitching into a single file, just call the two functions directly:
    dataset = []
    dataset.extend(generate_vedic_dataset_part1())
    dataset.extend(generate_vedic_dataset_part2())

    print(f"Uploading to Neo4j... ({len(dataset)} rules)")
    driver = get_db_driver()
    ensure_constraints(driver)
    driver.close()

    bulk_load_vedic(dataset)
    print(f"✅ Successfully seeded {len(dataset)} Vedic_engine rules into Neo4j!")


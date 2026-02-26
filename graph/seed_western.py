# =========================================
# seed_western.py
# =========================================
# Seeds Western Tropical rules into Neo4j
#
# Graph model (compatible with your current setup):
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


def ensure_constraints(driver):
    """
    Optional but recommended: ensures uniqueness for node keys.
    Neo4j constraint syntax differs slightly by version; this works for modern Neo4j.
    """
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
# Core data
# --------------------------

ZODIAC = {
    "Aries": {
        "themes": ["Fire", "Action", "Initiative", "Independence"],
        "flavor": "takes the direct route: fast decisions, bold moves, and a strong need to act first."
    },
    "Taurus": {
        "themes": ["Earth", "Stability", "Sensuality", "Patience"],
        "flavor": "builds slowly and solidly: consistency, comfort, and a refusal to be rushed."
    },
    "Gemini": {
        "themes": ["Air", "Intellect", "Communication", "Curiosity"],
        "flavor": "works through the mind: questions, trade-offs, learning, and fast social feedback loops."
    },
    "Cancer": {
        "themes": ["Water", "Emotion", "Nurturing", "Protection"],
        "flavor": "moves by feeling: emotional security, loyalty, and protective instincts."
    },
    "Leo": {
        "themes": ["Fire", "Leadership", "Expression", "Pride"],
        "flavor": "wants visibility: creativity, loyalty, honor, and a strong drive to be recognized."
    },
    "Virgo": {
        "themes": ["Earth", "Service", "Analysis", "Perfection"],
        "flavor": "improves everything: detail, refinement, systems, and practical fixes."
    },
    "Libra": {
        "themes": ["Air", "Balance", "Diplomacy", "Harmony"],
        "flavor": "seeks fairness: partnership, aesthetics, compromise, and social intelligence."
    },
    "Scorpio": {
        "themes": ["Water", "Intensity", "Transformation", "Depth"],
        "flavor": "goes all-in: obsession, psychological depth, trust tests, and power dynamics."
    },
    "Sagittarius": {
        "themes": ["Fire", "Exploration", "Philosophy", "Optimism"],
        "flavor": "expands outward: travel, meaning, risk-taking, and truth-seeking."
    },
    "Capricorn": {
        "themes": ["Earth", "Discipline", "Ambition", "Structure"],
        "flavor": "climbs steadily: responsibility, long-term plans, and status through competence."
    },
    "Aquarius": {
        "themes": ["Air", "Innovation", "Rebellion", "Community"],
        "flavor": "breaks the mold: unconventional thinking, systems reform, and group impact."
    },
    "Pisces": {
        "themes": ["Water", "Empathy", "Mysticism", "Surrender"],
        "flavor": "dissolves boundaries: intuition, compassion, imagination, and spiritual sensitivity."
    },
}


def base_placements():
    """
    These are seeded as: Placement x Sign -> meaning/themes/chapter
    Keep this list tight and meaningful; the LLM will synthesize across systems later.
    """
    return [
        # ---- Identity
        {"name": "Sun", "chapter": "Identity", "desc": "Core ego, vitality, willpower, and conscious life direction"},
        {"name": "Moon", "chapter": "Identity", "desc": "Emotional baseline, needs, habits, and instinctive responses"},
        {"name": "Ascendant", "chapter": "Identity", "desc": "Outward persona, first impressions, body language, and approach to life"},
        {"name": "North Node", "chapter": "Destiny", "desc": "Growth edge: uncomfortable development that pushes the life forward"},
        {"name": "South Node", "chapter": "Destiny", "desc": "Comfort zone: ingrained habits/talents that can become a trap"},

        # ---- Career
        {"name": "Midheaven", "chapter": "Career", "desc": "Public identity, reputation, and long-term professional trajectory"},
        {"name": "Saturn", "chapter": "Career", "desc": "Discipline, delay, duty, long-term mastery, and karmic responsibility"},
        {"name": "House_10", "chapter": "Career", "desc": "Career arena: authority, achievement, and visible results"},
        {"name": "House_11", "chapter": "Career", "desc": "Networks, audience, gains, and long-term goals"},

        # ---- Finances
        {"name": "Jupiter", "chapter": "Finances", "desc": "Expansion, luck, wisdom, and wealth-building through growth"},
        {"name": "House_2", "chapter": "Finances", "desc": "Income, savings, possessions, and self-worth"},
        {"name": "House_8", "chapter": "Finances", "desc": "Shared resources, investments, debt, inheritance, and deep merging"},

        # ---- Relationships
        {"name": "Venus", "chapter": "Relationships", "desc": "Love style, attraction patterns, aesthetics, and bonding"},
        {"name": "Mars", "chapter": "Relationships", "desc": "Desire, conflict style, pursuit, libido, and assertion"},
        {"name": "House_5", "chapter": "Relationships", "desc": "Romance, dating, pleasure, creativity, and joy"},
        {"name": "House_7", "chapter": "Relationships", "desc": "Committed partnership, projection, and marriage themes"},

        # ---- Health
        {"name": "Mercury", "chapter": "Health", "desc": "Mind, nerves, daily cognition, stress response, and communication"},
        {"name": "House_6", "chapter": "Health", "desc": "Health routines, daily work, diet patterns, and maintenance"},
        {"name": "House_3", "chapter": "Health", "desc": "Mental load, local movement, learning loops, and environment stress"},

        # ---- Outer planets (Destiny flavor)
        {"name": "Uranus", "chapter": "Destiny", "desc": "Disruption, liberation, innovation, and sudden change"},
        {"name": "Neptune", "chapter": "Destiny", "desc": "Inspiration, confusion, ideals, and boundary dissolution"},
        {"name": "Pluto", "chapter": "Destiny", "desc": "Power, transformation, obsession, and total rebirth dynamics"},

        # ---- Arabic Parts
        {"name": "Lot_of_Fortune", "chapter": "Destiny", "desc": "Material flow: ease, circumstance, worldly outcomes (Fortune lot)"},
        {"name": "Lot_of_Spirit", "chapter": "Destiny", "desc": "Agency and calling: deliberate direction, craft, purpose (Spirit lot)"},

        # ---- Midpoints (Cosmobiology)
        {"name": "Sun_Moon_Midpoint", "chapter": "Identity", "desc": "Core integration point between will and emotion; public/private synthesis"},
        {"name": "ASC_MC_Midpoint", "chapter": "Career", "desc": "Interface between personal presence and public role; how you 'show up' professionally"},

        # ---- Predictive placements (sign-based outputs)
        {"name": "Progressed_Sun", "chapter": "Predictive", "desc": "Secondary progression: evolving identity theme of this life chapter"},
        {"name": "Progressed_Moon", "chapter": "Predictive", "desc": "Secondary progression: emotional focus and short-term internal cycle"},
        {"name": "Solar_Arc_Sun", "chapter": "Predictive", "desc": "Solar arc: external-event timing that pushes identity direction"},
        {"name": "Solar_Arc_Moon", "chapter": "Predictive", "desc": "Solar arc: external-event timing that pushes emotional/home direction"},

        # ---- Annual Profections
        {"name": "Profection_Sign", "chapter": "Predictive", "desc": "Annual theme sign for the year; what becomes loud and activated"},
    ]


def generate_sign_rules():
    """
    Generates Placement x Sign rules.
    """
    rules = []
    for placement in base_placements():
        for sign_name, sign_data in ZODIAC.items():
            rules.append({
                "system": "Western",
                "planet": placement["name"],
                "sign": sign_name,
                "chapter": placement["chapter"],
                "themes": sign_data["themes"],
                "meaning": f"{placement['desc']}. In {sign_name}, it {sign_data['flavor']}"
            })
    return rules


def generate_oob_rules():
    """
    Out of Bounds (declination) treats OOB as a special 'sign' value in the existing graph model.
    Oracle should pass planet=Venus, sign=Out_of_Bounds when applicable.
    """
    oob_meanings = {
        "Moon": "Emotions operate outside normal bounds: extreme sensitivity, genius empathy, or volatility.",
        "Mercury": "Thinking is unconventional: non-linear logic, radical ideas, and unusual speech patterns.",
        "Venus": "Values/love break norms: intense tastes, taboo attraction patterns, or unusual relationship rules.",
        "Mars": "Drive runs hot: huge ambition, sharp anger spikes, or fearless risk-taking.",
        "Jupiter": "Beliefs/expansion amplify: big luck or overreach; strong missionary energy.",
        "Saturn": "Authority/duty extremes: isolation, hardening, or exceptional mastery through pressure.",
        "Uranus": "Wild-card rebellion: disruptive innovation, shocks, and non-negotiable freedom.",
        "Neptune": "Bottomless imagination/spirit: transcendence or escapism; blurred boundaries.",
        "Pluto": "Power/transformation at extreme depth: intense control themes and irreversible changes."
    }

    rules = []
    for planet, meaning in oob_meanings.items():
        rules.append({
            "system": "Western",
            "planet": planet,
            "sign": "Out_of_Bounds",
            "chapter": "Identity",
            "themes": ["Extremes", "Genius", "Volatility"],
            "meaning": f"This planet is Out of Bounds (high declination). {meaning}"
        })
    return rules


def generate_time_lord_rules():
    """
    Profection Time Lord rules.
    In the existing graph model, we store sign=planetname (e.g., sign="Mars").
    Oracle will query: planet="Time_Lord", sign=<time_lord_planet>.
    """
    time_lords = {
        "Sun": "Visibility, authority, father/boss dynamics, identity pressure and leadership.",
        "Moon": "Home/family, body/emotions, caregiving, belonging, and security themes.",
        "Mercury": "Learning, writing, deals, networking, movement, and skill-building.",
        "Venus": "Relationships, harmony, money/pleasure, aesthetics, and social leverage.",
        "Mars": "Hard work, conflict, courage, cutting ties, asserting independence.",
        "Jupiter": "Expansion, travel, education, mentors, opportunity and big-picture growth.",
        "Saturn": "Responsibility, delays, boundaries, discipline, and long-term construction."
    }

    rules = []
    for lord, meaning in time_lords.items():
        rules.append({
            "system": "Western",
            "planet": "Time_Lord",
            "sign": lord,
            "chapter": "Predictive",
            "themes": ["Annual Theme", "Activation", "Focus"],
            "meaning": f"The annual Time Lord is {lord}. Themes: {meaning}"
        })
    return rules



def generate_fixed_star_rules():
    """
    Royal Fixed Stars (plus optional extras).
    Store planet="Fixed_Star" and sign=<star_name>.
    Oracle should pass: planet="Fixed_Star", sign="Regulus" etc,
    but can still embed which natal planet conjuncts the star in the final prompt/evidence.
    """
    stars = [
        {
            "name": "Regulus",
            "themes": ["Royalty", "Rise", "Honour"],
            "meaning": "Regulus amplifies prominence, ambition, and leadership. Rewards integrity; punishes arrogance or shortcuts."
        },
        {
            "name": "Spica",
            "themes": ["Gifts", "Protection", "Talent"],
            "meaning": "Spica supports blessings, artistry, refined intelligence, and protection during critical moments."
        },
        {
            "name": "Aldebaran",
            "themes": ["Success", "Warrior", "Truth"],
            "meaning": "Aldebaran drives achievement through courage and directness. Success rises with ethics and consistency."
        },
        {
            "name": "Antares",
            "themes": ["Intensity", "Power", "Obsession"],
            "meaning": "Antares magnifies passion and high-stakes ambition. Can bring victories or destructive rivalries if unchecked."
        },
        # Optional extra (you listed it earlier; not one of the four royals but commonly used)
        {
            "name": "Fomalhaut",
            "themes": ["Vision", "Purity", "Mysticism"],
            "meaning": "Fomalhaut enhances idealism and spiritual vision. Requires clean motives; illusions collapse quickly."
        },
    ]

    rules = []
    for s in stars:
        # Identity + Destiny are the most relevant chapters for fixed stars
        for chapter in ["Identity", "Destiny"]:
            rules.append({
                "system": "Western",
                "planet": "Fixed_Star",
                "sign": s["name"],
                "chapter": chapter,
                "themes": s["themes"],
                "meaning": f"Royal Fixed Star influence: {s['meaning']}"
            })
    return rules


def generate_zodiacal_releasing_rules():
    """
    Zodiacal Releasing: we seed sign-based meanings for Fortune and Spirit periods (Level 1).
    - Fortune = circumstances / material flow
    - Spirit  = agency / career / intentional direction
    Oracle should pass placement like:
        planet="ZR_Fortune_L1", sign="Aries"
        planet="ZR_Spirit_L1",  sign="Capricorn"
    """
    rules = []
    for sign_name, sign_data in ZODIAC.items():
        rules.append({
            "system": "Western",
            "planet": "ZR_Fortune_L1",
            "sign": sign_name,
            "chapter": "Predictive",
            "themes": ["Timing", "Circumstance"] + sign_data["themes"],
            "meaning": (
                f"Zodiacal Releasing (Fortune) period in {sign_name}: external circumstances and material events "
                f"tend to express through this archetype. In {sign_name}, it {sign_data['flavor']}"
            )
        })
        rules.append({
            "system": "Western",
            "planet": "ZR_Spirit_L1",
            "sign": sign_name,
            "chapter": "Predictive",
            "themes": ["Timing", "Agency"] + sign_data["themes"],
            "meaning": (
                f"Zodiacal Releasing (Spirit) period in {sign_name}: intentional direction, career choices, and agency "
                f"tend to express through this archetype. In {sign_name}, it {sign_data['flavor']}"
            )
        })
    return rules


def generate_dataset():
    """
    Aggregates all Western rule sets.
    """
    rules = []
    rules.extend(generate_sign_rules())
    rules.extend(generate_oob_rules())
    rules.extend(generate_time_lord_rules())
    rules.extend(generate_fixed_star_rules())
    rules.extend(generate_zodiacal_releasing_rules())
    return rules


def bulk_load_western(rules):
    driver = get_db_driver()

    # This keeps your existing graph model.
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
    print("Generating Western Master Dataset...")
    dataset = generate_dataset()
    print(f"Uploading to Neo4j... ({len(dataset)} rules)")

    driver = get_db_driver()
    ensure_constraints(driver)
    driver.close()

    bulk_load_western(dataset)
    print(f"✅ Successfully seeded {len(dataset)} Western rules into Neo4j!")

import os
from neo4j import GraphDatabase


def get_db_driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD")
    if not uri or not pwd:
        raise ValueError("Missing Neo4j credentials")
    return GraphDatabase.driver(uri, auth=(user, pwd))


def generate_dignity_rules():
    """Generate rules for essential dignity states with proper weights."""
    rules = []

    # Exaltations (Critical priority +4)
    exaltations = [
        ("Sun", "Aries", 19, "Peak solar authority. Honor, leadership clarity, vital force."),
        ("Moon", "Taurus", 3, "Emotional stability. Fertility, steady mind, material comfort."),
        ("Mercury", "Virgo", 15, "Intellectual precision. Analysis, skill, discrimination."),
        ("Venus", "Pisces", 27, "Universal love. Spiritual beauty, artistic genius, compassion."),
        ("Mars", "Capricorn", 28, "Disciplined action. Strategic power, endurance, controlled force."),
        ("Jupiter", "Cancer", 15, "Benevolent protection. Wisdom, generosity, ethical expansion."),
        ("Saturn", "Libra", 21, "Justice and order. Fair authority, structured harmony, maturity.")
    ]

    for planet, sign, deg, meaning in exaltations:
        for chapter in ["Identity", "Career", "Finances"]:
            rules.append({
                "system": "Western",
                "placement": f"Dignity_{planet}",
                "sign": f"Exalted_{sign}",
                "chapter": chapter,
                "themes": ["Essential Dignity", "Exaltation", planet, sign],
                "meaning": f"{planet} exalted in {sign} ({deg}°): {meaning}",
                "weight": 0.90
            })

    # Falls (Critical debility -4)
    falls = [
        ("Sun", "Libra"), ("Moon", "Scorpio"), ("Mercury", "Pisces"),
        ("Venus", "Virgo"), ("Mars", "Cancer"), ("Jupiter", "Capricorn"), ("Saturn", "Aries")
    ]

    for planet, sign in falls:
        for chapter in ["Identity", "Health"]:
            rules.append({
                "system": "Western",
                "placement": f"Dignity_{planet}",
                "sign": f"Fall_{sign}",
                "chapter": chapter,
                "themes": ["Essential Dignity", "Fall", planet, sign],
                "meaning": f"{planet} in fall in {sign}: Strained expression, requires compensation through effort and awareness.",
                "weight": 0.85
            })

    # Rulerships (+5)
    rulers = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
        "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
        "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
        "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
    }

    for sign, planet in rulers.items():
        for chapter in ["Identity", "Career"]:
            rules.append({
                "system": "Western",
                "placement": f"Dignity_{planet}",
                "sign": f"Ruler_{sign}",
                "chapter": chapter,
                "themes": ["Essential Dignity", "Rulership", planet, sign],
                "meaning": f"{planet} rules {sign}: Strong essential dignity, natural authority in this domain.",
                "weight": 0.95
            })

    return rules


def bulk_load():
    driver = get_db_driver()
    query = """
    UNWIND $rules AS rule
    MERGE (r:Rule {
        system: rule.system,
        placement: rule.placement,
        sign: rule.sign,
        chapter: rule.chapter
    })
    SET r.meaning = rule.meaning,
        r.themes = rule.themes,
        r.weight = rule.weight,
        r.updated_at = datetime()
    """

    try:
        with driver.session() as session:
            rules = generate_dignity_rules()
            session.run(query, rules=rules)
            print(f"✅ Seeded {len(rules)} dignity rules")
    finally:
        driver.close()


if __name__ == "__main__":
    bulk_load()
"""Seed Shadbala (Six-Source Strength) rules into Neo4j."""
import os
from neo4j import GraphDatabase


def get_db_driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD")
    if not uri or not pwd:
        raise ValueError("Missing Neo4j credentials")
    return GraphDatabase.driver(uri, auth=(user, pwd))


SHADBALA_TIERS = {
    "DOMINANT": {
        "meaning": "Planet at or above 1.5× minimum Rupas. Functions at peak capacity — its domain of life is activated, energized, and productive. Its significations manifest strongly and repeatedly.",
        "chapters": ["Identity", "Career", "Finances", "Destiny"],
        "confidence": 0.88,
        "priority": 9
    },
    "ADEQUATE": {
        "meaning": "Planet meets minimum Rupas threshold. Functional but not exceptional — the planetary signification is present and delivers results when activated by Dasha or transit.",
        "chapters": ["Identity", "Career"],
        "confidence": 0.80,
        "priority": 6
    },
    "WEAKENED": {
        "meaning": "Planet below minimum Rupas threshold. Delivers results with effort and delay. The native must compensate consciously in this planet's domain — remedial action (upaya) is indicated.",
        "chapters": ["Health", "Identity", "Destiny"],
        "confidence": 0.82,
        "priority": 8
    },
    "SEVERELY WEAKENED": {
        "meaning": "Planet critically below minimum Rupas. This is a core vulnerability of the chart. The planet's significations face repeated obstruction, frustration, or abnormal expression. Requires sustained remedial attention and realistic expectation management.",
        "chapters": ["Health", "Destiny", "Identity"],
        "confidence": 0.85,
        "priority": 9
    },
}

PLANETS_SH = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]


def generate_shadbala_rules():
    rules = []
    for planet in PLANETS_SH:
        for tier, data in SHADBALA_TIERS.items():
            for chapter in data["chapters"]:
                rules.append({
                    "system": "Vedic_engine",
                    "placement": f"Shadbala_{planet}",
                    "sign": tier,
                    "chapter": chapter,
                    "themes": ["Shadbala", "Planetary Strength", planet, tier],
                    "meaning": f"{planet} Shadbala tier {tier}: {data['meaning']}",
                    "confidence": data["confidence"],
                    "priority": data["priority"],
                    "technique": "Shadbala",
                })
    return rules


def bulk_load():
    driver = get_db_driver()
    rules = generate_shadbala_rules()

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
        r.confidence = rule.confidence,
        r.priority = rule.priority,
        r.technique = rule.technique,
        r.updated_at = datetime()
    """
    try:
        with driver.session() as session:
            session.run(query, rules=rules)
        print(f"✅ Seeded {len(rules)} Shadbala rules")
    finally:
        driver.close()


if __name__ == "__main__":
    bulk_load()
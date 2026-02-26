"""Seed essential dignity and reception rules."""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def generate_dignity_rules():
    """Generate rules for essential dignity states."""
    rules = []

    # Exaltation rules (high priority)
    exaltations = [
        ("Sun", "Aries", 19, "Exaltation", "Solar power at peak. Authority, honor, clear vision."),
        ("Moon", "Taurus", 3, "Exaltation", "Emotional stability. Fertility, abundance, steady mind."),
        ("Mercury", "Virgo", 15, "Exaltation", "Intellectual precision. Analysis, discrimination, skill."),
        ("Venus", "Pisces", 27, "Exaltation", "Spiritual love. Universal compassion, artistic genius."),
        ("Mars", "Capricorn", 28, "Exaltation", "Disciplined action. Strategic power, endurance."),
        ("Jupiter", "Cancer", 15, "Exaltation", "Benevolent expansion. Protection, wisdom, generosity."),
        ("Saturn", "Libra", 21, "Exaltation", "Justice and order. Fair authority, structured harmony.")
    ]

    for planet, sign, deg, status, meaning in exaltations:
        for chapter in ["Identity", "Career", "Finances", "Destiny"]:
            rules.append({
                "system": "Western",
                "placement": f"Dignity_{planet}",
                "sign": f"{status}_{sign}_{deg}",
                "chapter": chapter,
                "themes": ["Essential Dignity", "Power", planet],
                "meaning": f"{planet} in {status} at {sign} {deg}°: {meaning}",
                "priority": 10
            })

    return rules

def bulk_load(rules):
    uri = os.getenv("NEO4J_URI", "").strip()
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD", "")

    if not uri or not pwd:
        print("Error: NEO4J_URI and NEO4J_PASSWORD must be set in environment")
        print(f"Current URI: '{uri}'")
        print("Create .env file with:")
        print("NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io")
        print("NEO4J_PASSWORD=your-password")
        return

    try:
        driver = GraphDatabase.driver(uri, auth=(user, pwd))

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
            r.priority = coalesce(rule.priority, 5),
            r.updated_at = datetime()
        """

        with driver.session() as session:
            session.run(query, rules=rules)
        driver.close()
        print(f"✅ Seeded {len(rules)} dignity rules")

    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        print(f"URI used: {uri}")
        print("Check that NEO4J_URI starts with neo4j:// or neo4j+s://")

if __name__ == "__main__":
    bulk_load(generate_dignity_rules())
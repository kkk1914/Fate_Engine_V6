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

def generate_nakshatra_dataset():
    stars = [
        {"name": "Ashwini", "themes": ["Healing", "Speed", "Initiative"], "desc": "Physician star: quick recovery, fast decisions, pioneering instinct."},
        {"name": "Bharani", "themes": ["Transformation", "Burden", "Creation"], "desc": "Containment + creation: transformation through responsibility, intense creative pressure."},
        {"name": "Krittika", "themes": ["Fire", "Purification", "Cutting"], "desc": "Cleansing fire: sharp discernment, cuts what is false, purifies through intensity."},
        {"name": "Rohini", "themes": ["Beauty", "Growth", "Attraction"], "desc": "Growth + charm: magnetism, fertility, artistic taste, comfort seeking."},
        {"name": "Mrigashira", "themes": ["Searching", "Curiosity", "Restlessness"], "desc": "Seeker: curiosity, gentle probing, restless mind searching for the 'real thing'."},
        {"name": "Ardra", "themes": ["Storm", "Intellect", "Rebuild"], "desc": "Storm: insight forged through disruption; emotional rain that reforms the psyche."},
        {"name": "Punarvasu", "themes": ["Renewal", "Return", "Safety"], "desc": "Return to light: optimism, recovery cycles, protection through faith."},
        {"name": "Pushya", "themes": ["Nourishment", "Duty", "Auspicious"], "desc": "Nourisher: duty-driven care, tradition, mentoring energy."},
        {"name": "Ashlesha", "themes": ["Serpent", "Mystic", "Bind"], "desc": "Serpent: hypnotic perception, binding psychology, secret intelligence."},
        {"name": "Magha", "themes": ["Ancestors", "Throne", "Status"], "desc": "Royal lineage: ancestral pride, authority themes, demand for respect."},
        {"name": "Purva Phalguni", "themes": ["Pleasure", "Romance", "Rest"], "desc": "Pleasure: romance, aesthetics, enjoyment, reward cycles."},
        {"name": "Uttara Phalguni", "themes": ["Contracts", "Reliability", "Support"], "desc": "Steady patronage: alliances, reliability, social duty."},
        {"name": "Hasta", "themes": ["Hands", "Skill", "Craft"], "desc": "Hands: technical skill, healing craft, capacity to 'shape' outcomes."},
        {"name": "Chitra", "themes": ["Design", "Brilliance", "Illusion"], "desc": "Architect: dazzling presentation, design mind, illusion mastery."},
        {"name": "Swati", "themes": ["Wind", "Independence", "Trade"], "desc": "Wind: independence, adaptability, business instincts, freedom priority."},
        {"name": "Vishakha", "themes": ["Goal", "Triumph", "Fixation"], "desc": "Goal-spear: ambition, victory through fixation, intense pursuit."},
        {"name": "Anuradha", "themes": ["Devotion", "Friendship", "Travel"], "desc": "Devotion: loyal friendships, success via alliances, travel expansion."},
        {"name": "Jyeshtha", "themes": ["Eldest", "Protection", "Authority"], "desc": "Chief: protector role, authority, internal battles, responsibility pressure."},
        {"name": "Mula", "themes": ["Root", "Truth", "Destruction"], "desc": "Root: destroys to expose truth; deep investigation and healing."},
        {"name": "Purva Ashadha", "themes": ["Invincible", "Water", "Patience"], "desc": "Invincible: persistence, fluid power, resilience through time."},
        {"name": "Uttara Ashadha", "themes": ["Victory", "Integrity", "Endurance"], "desc": "Enduring victory: integrity-based wins, slow guaranteed success."},
        {"name": "Shravana", "themes": ["Listening", "Learning", "Silence"], "desc": "Listener: absorbs knowledge, needs quiet, learns from tradition."},
        {"name": "Dhanishta", "themes": ["Wealth", "Rhythm", "Group"], "desc": "Rhythm: timing talent, wealth signals, thrives in teams/music."},
        {"name": "Shatabhisha", "themes": ["Healing", "Secrets", "Science"], "desc": "Healer-scientist: secrecy, analytics, medicine/astrology affinity."},
        {"name": "Purva Bhadrapada", "themes": ["Penance", "Fire", "Intensity"], "desc": "Penance: intensity, reform, spiritual fire, dual presentation risk."},
        {"name": "Uttara Bhadrapada", "themes": ["Depth", "Wisdom", "Control"], "desc": "Depth: emotional control, mature wisdom, endurance."},
        {"name": "Revati", "themes": ["Journeys", "Care", "Completion"], "desc": "Completion: protection in travel, caretaking, final transition energy."}
    ]

    rules = []
    for star in stars:
        for chapter in ["Identity", "Destiny", "Predictive", "Global"]:
            rules.append({
                "system": "Vedic_engine",
                "placement": "Nakshatra",
                "sign": star["name"].replace(" ", "_"),
                "chapter": chapter,
                "meaning": star["desc"],
                "themes": star["themes"]
            })


    return rules


def bulk_load(rules):
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
        print(f"✅ Seeded {len(rules)} nakshatra rules.")
    driver.close()


if __name__ == "__main__":
    bulk_load(generate_nakshatra_dataset())

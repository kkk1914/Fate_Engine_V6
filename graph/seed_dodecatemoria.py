"""Seed Dodecatemoria (12th parts) rules into Neo4j.

Dodecatemoria rules cover the deeper sub-sign resonance of each sign.
When a planet's dodecatemoria falls in a particular sign, these rules
are activated as additional interpretive context.

Chapters: Identity, Career, Relationships, Destiny, Finances, Health
Authority: Vettius Valens (Anthologies I.3), Ptolemy (Tetrabiblos I.22)
"""
import os
from neo4j import GraphDatabase


def get_db_driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD")
    if not uri or not pwd:
        raise ValueError("Missing Neo4j credentials: NEO4J_URI and NEO4J_PASSWORD")
    return GraphDatabase.driver(uri, auth=(user, pwd))


# Core meaning for each sign as a dodecatemoria destination
# These describe the sub-sign quality activated when any planet's
# dodecatemoria falls in this sign.
DODEC_SIGN_MEANINGS = {
    "Aries": {
        "ruler": "Mars",
        "quality": "Initiative and force. The dodecatemoria in Aries activates the assertive, pioneering dimension of any planet. "
                   "Quick starts, competitive drive, impatience. The planet's expression becomes faster, more direct, more combative. "
                   "Its gifts are decisive action; its blindspot is acting before thinking.",
        "chapters": ["Identity", "Career", "Health"],
        "themes": ["Assertion", "Pioneer", "Mars quality", "Speed"]
    },
    "Taurus": {
        "ruler": "Venus",
        "quality": "Material consolidation and pleasure. The dodecatemoria in Taurus activates the sensory, resource-accumulating dimension. "
                   "Endurance, aesthetic sense, attachment to stability. The planet's expression becomes slower, more deliberate, more focused on tangible results. "
                   "Its gifts are reliability and material mastery; its blindspot is stubbornness.",
        "chapters": ["Finances", "Relationships", "Health"],
        "themes": ["Stability", "Sensory", "Venus quality", "Resources"]
    },
    "Gemini": {
        "ruler": "Mercury",
        "quality": "Duality and communication. The dodecatemoria in Gemini activates the mercurial, dual, intellectually restless dimension. "
                   "Curiosity, adaptability, skill with language and connection. The planet's expression becomes more verbal, more changeable, less fixed. "
                   "Its gifts are versatility and connection; its blindspot is scattered focus.",
        "chapters": ["Identity", "Career", "Relationships"],
        "themes": ["Duality", "Communication", "Mercury quality", "Adaptability"]
    },
    "Cancer": {
        "ruler": "Moon",
        "quality": "Emotional memory and protection. The dodecatemoria in Cancer activates the lunar, nurturing, defensive dimension. "
                   "Sensitivity, attachment, protective instinct, memory of the past. The planet's expression becomes more emotional, more private, more driven by feeling. "
                   "Its gifts are empathy and loyalty; its blindspot is excessive caution and emotional reactivity.",
        "chapters": ["Identity", "Relationships", "Health"],
        "themes": ["Emotion", "Protection", "Lunar quality", "Memory"]
    },
    "Leo": {
        "ruler": "Sun",
        "quality": "Solar authority and self-expression. The dodecatemoria in Leo activates the regal, creative, performative dimension. "
                   "Pride, generosity, the need to be seen and honored. The planet's expression becomes more dramatic, more ego-centered, more invested in recognition. "
                   "Its gifts are confidence and creative leadership; its blindspot is pride and the need for constant affirmation.",
        "chapters": ["Identity", "Career", "Relationships"],
        "themes": ["Authority", "Performance", "Solar quality", "Recognition"]
    },
    "Virgo": {
        "ruler": "Mercury",
        "quality": "Analysis and discrimination. The dodecatemoria in Virgo activates the critical, methodical, detail-oriented dimension. "
                   "Service drive, precision, health consciousness, tendency toward self-criticism. "
                   "The planet's expression becomes more analytical, more careful, more focused on correctness. "
                   "Its gifts are skill and discernment; its blindspot is perfectionism and self-doubt.",
        "chapters": ["Health", "Career", "Finances"],
        "themes": ["Analysis", "Service", "Mercury quality", "Precision"]
    },
    "Libra": {
        "ruler": "Venus",
        "quality": "Balance and relational diplomacy. The dodecatemoria in Libra activates the harmonizing, justice-seeking, partnership dimension. "
                   "Aesthetic judgment, need for fairness, conflict avoidance. The planet's expression becomes more relational, more oriented toward balance and beauty. "
                   "Its gifts are diplomacy and grace; its blindspot is indecisiveness and people-pleasing.",
        "chapters": ["Relationships", "Career", "Identity"],
        "themes": ["Balance", "Diplomacy", "Venus quality", "Justice"]
    },
    "Scorpio": {
        "ruler": "Mars",
        "quality": "Depth, transformation, and power. The dodecatemoria in Scorpio activates the investigative, intense, crisis-oriented dimension. "
                   "The planet's expression becomes more secretive, more penetrating, more concerned with what lies beneath the surface. "
                   "Its gifts are psychological depth and regenerative power; its blindspot is obsession, control, and difficulty releasing.",
        "chapters": ["Destiny", "Relationships", "Health"],
        "themes": ["Transformation", "Depth", "Mars quality", "Intensity"]
    },
    "Sagittarius": {
        "ruler": "Jupiter",
        "quality": "Expansion and philosophical vision. The dodecatemoria in Sagittarius activates the optimistic, freedom-seeking, wisdom-oriented dimension. "
                   "The planet's expression becomes more expansive, more idealistic, more concerned with meaning and far horizons. "
                   "Its gifts are vision and philosophical breadth; its blindspot is overreach and avoidance of limitation.",
        "chapters": ["Destiny", "Career", "Identity"],
        "themes": ["Expansion", "Philosophy", "Jupiter quality", "Freedom"]
    },
    "Capricorn": {
        "ruler": "Saturn",
        "quality": "Structure and long-term mastery. The dodecatemoria in Capricorn activates the disciplined, ambitious, responsibility-bearing dimension. "
                   "The planet's expression becomes more serious, more focused on achievement over time, more aware of consequences. "
                   "Its gifts are endurance and authority; its blindspot is rigidity and excessive self-denial.",
        "chapters": ["Career", "Finances", "Health"],
        "themes": ["Discipline", "Authority", "Saturn quality", "Mastery"]
    },
    "Aquarius": {
        "ruler": "Saturn",
        "quality": "Innovation and collective consciousness. The dodecatemoria in Aquarius activates the reforming, detached, future-oriented dimension. "
                   "The planet's expression becomes more unconventional, more oriented toward groups and principles rather than personal warmth. "
                   "Its gifts are originality and humanitarian vision; its blindspot is emotional detachment and contrarianism.",
        "chapters": ["Identity", "Destiny", "Career"],
        "themes": ["Innovation", "Detachment", "Saturn quality", "Reform"]
    },
    "Pisces": {
        "ruler": "Jupiter",
        "quality": "Dissolution and mystical sensitivity. The dodecatemoria in Pisces activates the boundaryless, intuitive, self-transcending dimension. "
                   "The planet's expression becomes more fluid, more surrendered, more connected to the invisible or unconscious. "
                   "Its gifts are compassion and spiritual depth; its blindspot is escapism and difficulty with boundaries.",
        "chapters": ["Destiny", "Health", "Relationships"],
        "themes": ["Dissolution", "Mysticism", "Jupiter quality", "Compassion"]
    }
}

# Meanings for planets in their own dodecatemoria (double emphasis)
OWN_DODEC_MEANINGS = {
    "Sun": "Sun in its own dodecatemoria: the solar identity is doubly reinforced — exceptional clarity of purpose, but also risk of fixed ego-centricity. The core myth written twice into the chart.",
    "Moon": "Moon in its own dodecatemoria: emotional patterns are amplified and deeply habitual. The ancestral script is written at every level of the chart. Exceptional empathy or emotional reactivity.",
    "Mercury": "Mercury in its own dodecatemoria: intellectual gifts are doubled. Unusual verbal or analytical capacity. The mind reinforces itself — watch for overthinking.",
    "Venus": "Venus in its own dodecatemoria: relational and aesthetic values are doubled. Extraordinary charm and beauty-sensitivity. Watch for attachment to pleasure.",
    "Mars": "Mars in its own dodecatemoria: drive and assertiveness are doubled. High energy, competitive force, difficulty moderating impulse.",
    "Jupiter": "Jupiter in its own dodecatemoria: wisdom and expansive luck are doubled. Unusual philosophical vision, but risk of overreach.",
    "Saturn": "Saturn in its own dodecatemoria: discipline and structural mastery are doubled. Exceptional endurance, but also potential for excessive contraction and limitation.",
}


def generate_dodecatemoria_rules():
    """Generate Neo4j rules for all 12 signs × relevant chapters."""
    rules = []

    for sign, data in DODEC_SIGN_MEANINGS.items():
        for chapter in data["chapters"]:
            rules.append({
                "system": "Hellenistic",
                "placement": "Dodecatemoria",
                "sign": sign,
                "chapter": chapter,
                "themes": data["themes"],
                "meaning": (
                    f"Dodecatemoria in {sign} (ruler: {data['ruler']}): {data['quality']}"
                ),
                "confidence": 0.80,
                "priority": 7,
                "technique": "Dodecatemoria",
                "ruler": data["ruler"],
            })

    # Own-dodecatemoria rules (high priority — double sign emphasis)
    for planet, meaning in OWN_DODEC_MEANINGS.items():
        for chapter in ["Identity", "Destiny"]:
            rules.append({
                "system": "Hellenistic",
                "placement": f"OwnDodec_{planet}",
                "sign": "Self_Reinforced",
                "chapter": chapter,
                "themes": ["Dodecatemoria", "Double Emphasis", planet],
                "meaning": meaning,
                "confidence": 0.85,
                "priority": 8,
                "technique": "Dodecatemoria_OwnSign",
            })

    return rules


def bulk_load():
    driver = get_db_driver()
    rules = generate_dodecatemoria_rules()

    query = """
    UNWIND $rules AS rule
    MERGE (r:Rule {
        system:    rule.system,
        placement: rule.placement,
        sign:      rule.sign,
        chapter:   rule.chapter
    })
    SET
        r.meaning     = rule.meaning,
        r.themes      = rule.themes,
        r.confidence  = rule.confidence,
        r.priority    = rule.priority,
        r.technique   = rule.technique,
        r.updated_at  = datetime()
    """

    try:
        with driver.session() as session:
            session.run(query, rules=rules)
        print(f"✅ Seeded {len(rules)} dodecatemoria rules")
    finally:
        driver.close()


if __name__ == "__main__":
    bulk_load()

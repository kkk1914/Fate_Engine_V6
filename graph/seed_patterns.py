"""Seed geometric pattern rules into Neo4j (Phase 4)."""
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


def generate_pattern_rules():
    """Generate rules for geometric planetary patterns."""
    patterns = [
        {
            "name": "Grand Trine",
            "modality_variants": ["Fire", "Earth", "Air", "Water"],
            "confidence": 0.80,
            "themes_base": ["Harmony", "Talent", "Ease"],
            "meanings": {
                "Fire": ("Fire Grand Trine: enormous vitality, natural leadership, "
                         "spiritual confidence. Risk: arrogance and avoidance of challenge. "
                         "Gift: inspirational force that uplifts others."),
                "Earth": ("Earth Grand Trine: material talent, practical mastery, "
                          "financial gifts. Risk: laziness, stagnation in comfort. "
                          "Gift: the ability to build lasting structures."),
                "Air": ("Air Grand Trine: intellectual brilliance, communication mastery, "
                        "social intelligence. Risk: living entirely in the mind, "
                        "emotional disconnection. Gift: ability to synthesize complex ideas."),
                "Water": ("Water Grand Trine: psychic sensitivity, emotional depth, "
                          "artistic genius. Risk: withdrawal, victim patterns, "
                          "boundary dissolution. Gift: profound empathy and healing capacity."),
            }
        },
        {
            "name": "T-Square",
            "modality_variants": ["Cardinal", "Fixed", "Mutable"],
            "confidence": 0.82,
            "themes_base": ["Tension", "Achievement", "Drive"],
            "meanings": {
                "Cardinal": ("Cardinal T-Square: explosive ambition. Initiates compulsively, "
                             "leaves projects unfinished. The apex planet holds the key to "
                             "resolution—mastering its domain releases the entire pattern's power."),
                "Fixed": ("Fixed T-Square: immovable determination. Extremely stubborn but "
                          "capable of extraordinary endurance. The missing leg of the cross "
                          "is the blind spot and the relief valve."),
                "Mutable": ("Mutable T-Square: restless adaptability turning to nervous "
                            "scattering. Brilliant at improvising but struggles to commit. "
                            "The apex planet demands repeated adjustments."),
            }
        },
        {
            "name": "Grand Cross",
            "modality_variants": ["Cardinal", "Fixed", "Mutable"],
            "confidence": 0.85,
            "themes_base": ["Maximum Tension", "Mastery", "Crucible"],
            "meanings": {
                "Cardinal": ("Cardinal Grand Cross: perpetual crisis-initiation. "
                             "Life feels like constant emergencies requiring action. "
                             "When integrated: extraordinary executive force."),
                "Fixed": ("Fixed Grand Cross: iron will tested by unmovable circumstances. "
                          "Four-way impasse that demands internal transformation, not external action. "
                          "When integrated: unbreakable resilience."),
                "Mutable": ("Mutable Grand Cross: existential uncertainty made permanent. "
                            "Identity scattered across possibilities. "
                            "When integrated: supreme adaptability and multi-domain mastery."),
            }
        },
        {
            "name": "Yod",
            "modality_variants": ["General"],
            "confidence": 0.78,
            "themes_base": ["Fate", "Compulsion", "Mission"],
            "meanings": {
                "General": ("Yod (Finger of God): the apex planet carries a fated, "
                            "compulsive quality that cannot be avoided or redirected. "
                            "The base planets (sextile) represent talents that are always "
                            "being pointed toward the apex's domain. "
                            "The native often feels driven by forces beyond conscious choice. "
                            "Resolution requires accepting the apex's mission consciously."),
            }
        },
        {
            "name": "Stellium",
            "modality_variants": ["General"],
            "confidence": 0.75,
            "themes_base": ["Concentration", "Obsession", "Gift"],
            "meanings": {
                "General": ("Stellium: life force is massively concentrated. "
                            "The sign/house of the stellium becomes the defining arena—"
                            "its gifts are enormous, its blindspots equally large. "
                            "Other life areas may be underdeveloped relative to the stellium's pull. "
                            "The stellium's dispositor (sign ruler) is a key chart power broker."),
            }
        },
        {
            "name": "Kite",
            "modality_variants": ["General"],
            "confidence": 0.77,
            "themes_base": ["Directed Talent", "Purpose", "Rare Gift"],
            "meanings": {
                "General": ("Kite: the rarest benefic pattern—Grand Trine made actionable. "
                            "The 'tail' planet opposite the apex transforms passive talent "
                            "into directed ambition. "
                            "This person has both natural gifts AND the drive to use them. "
                            "The tail planet is the engine; the trine provides the fuel."),
            }
        },
        {
            "name": "Mystic Rectangle",
            "modality_variants": ["General"],
            "confidence": 0.72,
            "themes_base": ["Integration", "Spiritual-Material Bridge", "Balance"],
            "meanings": {
                "General": ("Mystic Rectangle: practical mysticism in geometric form. "
                            "Two oppositions create tension; two trines and sextiles provide ease. "
                            "The native has unusual capacity to bridge spiritual awareness "
                            "with practical effectiveness. "
                            "All four planets must be consciously engaged."),
            }
        },
    ]

    rules = []
    for p in patterns:
        for variant in p["modality_variants"]:
            meaning = p["meanings"].get(variant, p["meanings"].get("General", ""))
            themes = p["themes_base"] + ([variant] if variant != "General" else [])

            for chapter in ["Identity", "Career", "Destiny", "Predictive"]:
                rules.append({
                    "system": "Western",
                    "placement": f"Pattern_{p['name'].replace(' ', '_')}",
                    "sign": variant,
                    "chapter": chapter,
                    "themes": themes,
                    "meaning": f"{p['name']} ({variant}): {meaning}",
                    "confidence": p["confidence"],
                    "priority": 9,
                    "pattern_name": p["name"],
                    "modality_or_element": variant,
                })

    return rules


def bulk_load():
    driver = get_db_driver()
    rules = generate_pattern_rules()

    query = """
    UNWIND $rules AS rule
    MERGE (r:Rule {
        system:    rule.system,
        placement: rule.placement,
        sign:      rule.sign,
        chapter:   rule.chapter
    })
    SET
        r.meaning             = rule.meaning,
        r.themes              = rule.themes,
        r.confidence          = rule.confidence,
        r.priority            = rule.priority,
        r.pattern_name        = rule.pattern_name,
        r.modality_or_element = rule.modality_or_element,
        r.updated_at          = datetime()
    """

    try:
        with driver.session() as session:
            session.run(query, rules=rules)
        print(f"✅ Seeded {len(rules)} pattern rules")
    finally:
        driver.close()


if __name__ == "__main__":
    bulk_load()

"""Seed Fixed Star Parans rules into Neo4j.

Seeds rules for all 26 catalogue stars × 7 planets × 4 chapters.
Includes both conjunction and paran rules.
"""
import os
from neo4j import GraphDatabase


def get_db_driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD")
    if not uri or not pwd:
        raise ValueError("Missing Neo4j credentials")
    return GraphDatabase.driver(uri, auth=(user, pwd))


# Full star meanings per chapter domain
STAR_CHAPTER_MEANINGS = {
    "Regulus": {
        "Identity":      "Regulus (α Leonis, 0° Virgo) conjunct or in paran: natal royalty signature. Success comes only through absolute refusal to seek revenge — one act of retaliation collapses the throne. Authority is given; humiliation destroys it.",
        "Career":        "Regulus activation in career domain: sudden ascent, high public visibility, and the possibility of spectacular fall if integrity is abandoned. Best vocations: military, governance, executive leadership.",
        "Finances":      "Regulus financial activation: wealth through authority, status, and decisive action. Risk: fortune won in haste can be lost through pride.",
        "Destiny":       "Regulus karmic signature: born to lead publicly, but must choose service over glory. The star tests whether power is worn or wielded.",
    },
    "Aldebaran": {
        "Identity":      "Aldebaran (α Tauri, 10° Gemini) contact: integrity as the core identity theme. Honor, courage, and word-as-bond are the psychological foundation. The wound is self-betrayal; the gift is unimpeachable reliability.",
        "Career":        "Aldebaran career activation: success through honesty and clear statement. The professional trap is diplomacy that becomes dishonesty. Favors law, medicine, architecture.",
        "Finances":      "Aldebaran financial activation: wealth through trust. Client and partner relationships built on integrity outperform those built on charm.",
        "Destiny":       "Aldebaran karmic signature: must choose truth over comfort, especially when the honest answer is costly.",
    },
    "Antares": {
        "Identity":      "Antares (α Scorpii, 10° Sagittarius) contact: obsessive, all-or-nothing intensity. The core compulsion is total commitment — to cause, person, or mission. The wound is self-destruction through excess.",
        "Career":        "Antares career activation: exceptional competence alongside extreme risk-taking. Favors military, emergency medicine, investigative journalism, deep strategy.",
        "Health":        "Antares health activation: inflammatory patterns, intense physical reactions, and the body as a mirror for suppressed intensity. The prescription is controlled discharge.",
        "Destiny":       "Antares karmic signature: must learn that survival is not the same as wisdom. The test is whether intensity becomes mastery or destruction.",
    },
    "Fomalhaut": {
        "Identity":      "Fomalhaut (α Piscis Austrini, 4° Pisces) contact: idealism as the central myth. The soul craves a pure, uncorrupted vision of what life could be. The trap is disillusionment when the world fails to match the dream.",
        "Career":        "Fomalhaut career activation: artistic, spiritual, or healing vocations. Best outcomes when the work serves a non-commercial ideal. Corruption of ideals = professional collapse.",
        "Finances":      "Fomalhaut financial activation: money through art, spirituality, or vision-based work. The financial trap is misplaced faith — investing in beautiful lies.",
        "Destiny":       "Fomalhaut karmic signature: the dreamer sent to purify. Must learn to hold vision without becoming lost in it.",
    },
    "Spica": {
        "Identity":      "Spica (α Virginis, 24° Libra) contact: natural gifts and protected status. Spica confers brilliance that looks effortless. The shadow is dependency on gifting — failing to work for what arrives easily.",
        "Career":        "Spica career activation: exceptional aptitude recognized by others. Favors science, arts, law. Often associated with mentors and patrons.",
        "Finances":      "Spica financial activation: abundance comes through skill and elegance. Not through brute force. The financial medicine is sustained refinement.",
        "Destiny":       "Spica karmic signature: born with advantages. The karmic debt is to steward gifts for the benefit of many, not consume them privately.",
    },
    "Algol": {
        "Identity":      "Algol (β Persei, 26° Taurus) contact: the capacity to look directly into what destroys. Algol is the Medusa's head — intense focus on danger, death, power, or extremes. The gift is unflinching sight; the trap is becoming what you face.",
        "Career":        "Algol career activation: investigative, forensic, therapeutic, or crisis-response roles. Best outcomes when Algol energy is channeled into protection rather than dominance.",
        "Health":        "Algol health activation: head and neck vulnerabilities. Accidents, headaches, and throat conditions possible. The body stores what the mind refuses to process.",
        "Destiny":       "Algol karmic signature: must master the gorgon reflex — the impulse to turn threatening things to stone (control) rather than transforming them.",
    },
    "Sirius": {
        "Identity":      "Sirius (α Canis Majoris, 14° Cancer) contact: devotion, ambition, and the hunger for immortal achievement. Sirius confers brightness and dedication but can become workaholism.",
        "Career":        "Sirius career activation: success through singleminded application. Favors military, government, or any role requiring sustained excellence. The trap is sacrificing family and health for achievement.",
        "Finances":      "Sirius financial activation: prosperity through relentless drive. The financial wound is confusing wealth with worth.",
        "Destiny":       "Sirius karmic signature: built to achieve; tested on whether achievement becomes service.",
    },
    "Vega": {
        "Identity":      "Vega (α Lyrae, 15° Capricorn) contact: charisma, artistry, and the magnetic pull of idealized beauty. The gift is the ability to enchant; the shadow is using enchantment as manipulation.",
        "Career":        "Vega career activation: arts, performance, diplomacy, or any role where presence and beauty matter. The professional trap is using charm instead of building substance.",
        "Relationships": "Vega relationship activation: magnetic attraction, idealized love, and the danger of pedestalization. The medicine is choosing people for character, not glamour.",
        "Destiny":       "Vega karmic signature: must transmute attraction into wisdom.",
    },
    "Arcturus": {
        "Identity":      "Arcturus (α Bootis, 24° Libra) contact: the guide and pathfinder. Natural authority comes from experience and the refusal to follow convention blindly. The wound is arrogance that comes with being first.",
        "Career":        "Arcturus career activation: innovation, exploration, and setting standards. Favors research, science, navigation, and fields that don't yet have a roadmap.",
        "Destiny":       "Arcturus karmic signature: the pioneer who must also be humble enough to ask for directions.",
    },
    "Pollux": {
        "Identity":      "Pollux (β Geminorum, 23° Cancer) contact: creative intelligence with a dangerous edge. Pollux gives artistry and cunning — can be used for brilliance or cruelty. The wound is using wit as a weapon.",
        "Career":        "Pollux career activation: acting, writing, strategy, martial arts, politics. Excellence is possible; the shadow is ruthlessness.",
        "Health":        "Pollux health activation: eye and head vulnerabilities; psychosomatic responses to repressed aggression.",
        "Destiny":       "Pollux karmic signature: must choose between the twin impulses of creation and destruction.",
    },
    "Regulus": {  # Already defined above — skipped on dedup
        "Identity": "",
    },
}

# Minimal meanings for stars not fully expanded above
DEFAULT_STAR_MEANING = {
    "conjunction": "Fixed star conjunction activates the star's thematic field through this planet's domain.",
    "paran": "Paran contact activates the star's energy through simultaneous horizon/meridian alignment — a permanent signature of the chart.",
}

CHAPTERS = ["Identity", "Career", "Finances", "Health", "Relationships", "Destiny"]
PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]

FULL_STARS = [
    "Regulus", "Aldebaran", "Antares", "Fomalhaut", "Spica", "Algol",
    "Sirius", "Vega", "Arcturus", "Pollux", "Procyon", "Betelgeuse",
    "Rigel", "Capella", "Canopus", "Scheat", "Markab", "Mirach",
    "Alpheratz", "Zuben Elgenubi", "Zuben Eschamali", "Deneb Algedi",
    "Achernar", "Difda", "Menkar", "Alcyone"
]


def generate_rules():
    rules = []
    for star in FULL_STARS:
        star_meanings = STAR_CHAPTER_MEANINGS.get(star, {})
        for planet in PLANETS:
            for chapter in CHAPTERS:
                # Conjunction rule
                meaning = star_meanings.get(chapter, DEFAULT_STAR_MEANING["conjunction"])
                rules.append({
                    "system": "FixedStar",
                    "placement": f"{planet}_conjunct_{star.replace(' ', '_')}",
                    "sign": chapter,
                    "chapter": chapter,
                    "themes": [star, planet, "fixed_star", "conjunction"],
                    "meaning": f"{planet} conjunct {star} [{chapter}]: {meaning}",
                    "confidence": 0.88,
                    "priority": 8 if star in ["Regulus", "Aldebaran", "Antares", "Fomalhaut", "Spica", "Algol"] else 6,
                    "technique": "FixedStar_Conjunction",
                })
                # Paran rule
                rules.append({
                    "system": "FixedStar",
                    "placement": f"{planet}_paran_{star.replace(' ', '_')}",
                    "sign": chapter,
                    "chapter": chapter,
                    "themes": [star, planet, "fixed_star", "paran"],
                    "meaning": f"{planet} paran {star} [{chapter}]: {DEFAULT_STAR_MEANING['paran']} {meaning}",
                    "confidence": 0.82,
                    "priority": 7 if star in ["Regulus", "Aldebaran", "Antares", "Fomalhaut", "Spica", "Algol"] else 5,
                    "technique": "FixedStar_Paran",
                })
    return rules


def bulk_load():
    driver = get_db_driver()
    rules = generate_rules()

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
        print(f"✅ Seeded {len(rules)} Fixed Star Paran rules ({len(FULL_STARS)} stars × {len(PLANETS)} planets × 2 types × {len(CHAPTERS)} chapters)")
    except Exception as e:
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        driver.close()


if __name__ == "__main__":
    bulk_load()

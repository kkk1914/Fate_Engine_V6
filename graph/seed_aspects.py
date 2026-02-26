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

def generate_aspect_dataset():
    aspects = [
        {"name": "Conjunction", "themes": ["Intensity", "Focus", "Blindspot"],
         "desc": "Fusion. The two planetary functions operate as one. High intensity and high reward, but harder to separate psychologically."},
        {"name": "Sextile", "themes": ["Opportunity", "Flow", "Talent"],
         "desc": "Opportunity. The functions cooperate easily; benefits are real but require choice/effort to activate."},
        {"name": "Square", "themes": ["Friction", "Tension", "Action"],
         "desc": "Friction. Internal tension forces action and growth; this is a pressure engine, not a comfort aspect."},
        {"name": "Trine", "themes": ["Harmony", "Luck", "Passivity"],
         "desc": "Harmony. Natural gifts and ease; the risk is complacency because things work without effort."},
        {"name": "Opposition", "themes": ["Projection", "Balance", "Polarity"],
         "desc": "Polarity. Requires balance; often experienced through other people or external events until integrated."}
    ]

    rules = []
    for a in aspects:
        for chapter in ["Identity", "Finances", "Career", "Relationships", "Health", "Destiny", "Predictive", "Global"]:
            rules.append({
                "system": "Western",
                "placement": "Aspects",
                "sign": a["name"],
                "chapter": chapter,
                "meaning": f"{a['desc']}",
                "themes": a["themes"]
            })
    return rules


def bulk_load(rules):
    driver = get_db_driver()
    query = """
    UNWIND $rules AS rule
    MERGE (s:System {name: rule.system})
    MERGE (p:Placement {name: rule.placement})
    MERGE (z:Sign {name: rule.sign})
    MERGE (s)-[:USES]->(p)
    MERGE (p)-[:IN_SIGN {chapter: rule.chapter}]->(z)
    SET  (p)-[:IN_SIGN {chapter: rule.chapter}]->(z)
    """
    # The above "SET on relationship" can't be done directly like that in Cypher without re-binding the rel.
    # So we use a correct version below.

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
        print(f"✅ Seeded {len(rules)} aspect rules.")
    driver.close()


if __name__ == "__main__":
    bulk_load(generate_aspect_dataset())

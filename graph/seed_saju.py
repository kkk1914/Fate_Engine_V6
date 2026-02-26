# =========================================
# seed_saju.py
# =========================================
# Seeds Saju (Bazi) rules into Neo4j using your current graph model:
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
# Core tables
# --------------------------

# 10 Heavenly Stems (Day Masters)
DAY_MASTERS = {
    "甲": {"name": "Jia (Yang Wood)", "element": "Wood", "themes": ["Growth", "Stubbornness", "Protection"],
           "desc": "Like a tall tree: upright, direct, protective, and built for long-term growth. Hates being controlled."},
    "乙": {"name": "Yi (Yin Wood)", "element": "Wood", "themes": ["Adaptability", "Networking", "Strategy"],
           "desc": "Like a vine: flexible, persuasive, survives through relationships and smart positioning."},
    "丙": {"name": "Bing (Yang Fire)", "element": "Fire", "themes": ["Radiance", "Generosity", "Visibility"],
           "desc": "Like the sun: warm, bold, expressive, thrives when seen. Needs purpose to avoid burnout."},
    "丁": {"name": "Ding (Yin Fire)", "element": "Fire", "themes": ["Finesse", "Illumination", "Precision"],
           "desc": "Like a candle: refined, observant, subtle influence. Can become anxious if unstable."},
    "戊": {"name": "Wu (Yang Earth)", "element": "Earth", "themes": ["Stability", "Responsibility", "Reliability"],
           "desc": "Like a mountain: dependable, slow to change, carries burdens. Needs movement to avoid stagnation."},
    "己": {"name": "Ji (Yin Earth)", "element": "Earth", "themes": ["Nurturing", "Resourceful", "Cultivation"],
           "desc": "Like fertile soil: supportive, practical, builds outcomes through steady cultivation."},
    "庚": {"name": "Geng (Yang Metal)", "element": "Metal", "themes": ["Justice", "Endurance", "Directness"],
           "desc": "Like raw steel: blunt, resilient, justice-oriented. Learns through pressure and challenge."},
    "辛": {"name": "Xin (Yin Metal)", "element": "Metal", "themes": ["Elegance", "Value", "Refinement"],
           "desc": "Like jewelry: precise standards, prestige-aware, quietly tough. Needs respect and clean boundaries."},
    "壬": {"name": "Ren (Yang Water)", "element": "Water", "themes": ["Momentum", "Intelligence", "Ambition"],
           "desc": "Like a river: adaptable, fast-thinking, entrepreneurial. Can overwhelm others when unchecked."},
    "癸": {"name": "Gui (Yin Water)", "element": "Water", "themes": ["Intuition", "Fluidity", "Sensitivity"],
           "desc": "Like morning dew: subtle, intuitive, absorbing. Needs emotional hygiene to avoid drift."},
}

# 12 Earthly Branches (Animals + core flavor)
BRANCHES = {
    "子": {"name": "Rat (Zi)", "element": "Water", "themes": ["Resourceful", "Survival", "Charm"],
           "desc": "Sharp instincts, opportunistic intelligence, and fast adaptation to changing conditions."},
    "丑": {"name": "Ox (Chou)", "element": "Earth", "themes": ["Diligence", "Patience", "Conservatism"],
           "desc": "Slow, durable progress through discipline, reliability, and methodical execution."},
    "寅": {"name": "Tiger (Yin)", "element": "Wood", "themes": ["Courage", "Rebellion", "Competition"],
           "desc": "Bold independence, competitive drive, and strong boundary instincts."},
    "卯": {"name": "Rabbit (Mao)", "element": "Wood", "themes": ["Diplomacy", "Caution", "Refinement"],
           "desc": "Social intelligence, tact, and preference for indirect solutions over direct confrontation."},
    "辰": {"name": "Dragon (Chen)", "element": "Earth", "themes": ["Vision", "Confidence", "Potential"],
           "desc": "Big potential and ambition; can oscillate between bursts of power and waiting phases."},
    "巳": {"name": "Snake (Si)", "element": "Fire", "themes": ["Strategy", "Wisdom", "Secrecy"],
           "desc": "Strategic intelligence and guarded presence; excellent at timing and leverage."},
    "午": {"name": "Horse (Wu)", "element": "Fire", "themes": ["Action", "Freedom", "Speed"],
           "desc": "Fast movement, independence, and high drive. Needs autonomy or becomes unstable."},
    "未": {"name": "Goat (Wei)", "element": "Earth", "themes": ["Creativity", "Peace", "Empathy"],
           "desc": "Gentle creativity and emotional attunement; prefers stable, supportive environments."},
    "申": {"name": "Monkey (Shen)", "element": "Metal", "themes": ["Agility", "Cleverness", "Problem-solving"],
           "desc": "High mental agility, improvisation, and tactical thinking. Can get restless if bored."},
    "酉": {"name": "Rooster (You)", "element": "Metal", "themes": ["Observation", "Perfection", "Discipline"],
           "desc": "Precision, standards, and sharp critique. Great for craftsmanship; harsh if insecure."},
    "戌": {"name": "Dog (Xu)", "element": "Earth", "themes": ["Loyalty", "Protection", "Justice"],
           "desc": "Protective loyalty and moral clarity. Needs trust to relax; otherwise becomes defensive."},
    "亥": {"name": "Pig (Hai)", "element": "Water", "themes": ["Generosity", "Enjoyment", "Openness"],
           "desc": "Open-hearted generosity and appetite for life. Needs boundaries to avoid excess."},
}

# Hidden Stems (Cang Gan) mapping per branch
HIDDEN_STEMS = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}

# 10 Gods (generic meanings; oracle decides which god appears where)
TEN_GODS = {
    "Wealth": {
        "chapter": "Finances",
        "themes": ["Money", "Assets", "Control"],
        "desc": "Capacity to capture and control resources. Direct Wealth = stable income; Indirect Wealth = deals, investing, business."
    },
    "Power": {
        "chapter": "Career",
        "themes": ["Authority", "Discipline", "Pressure"],
        "desc": "Rules, responsibility, bosses, legal/structural pressure. Direct Officer = stable authority; Seven Killings = aggressive pressure and risk."
    },
    "Resource": {
        "chapter": "Destiny",
        "themes": ["Support", "Education", "Protection"],
        "desc": "Support systems: education, benefactors, intuition, nourishment. Indirect Resource often points to unconventional/esoteric learning."
    },
    "Output": {
        "chapter": "Identity",
        "themes": ["Creativity", "Expression", "Rebellion"],
        "desc": "What you produce: creativity, voice, charisma, performance. Hurting Officer can clash with authority; Eating God is refined output."
    },
    "Companion": {
        "chapter": "Relationships",
        "themes": ["Peers", "Rivalry", "Teamwork"],
        "desc": "Peers and competitors. Can mean social leverage and alliances or splitting resources with rivals."
    }
}


def generate_day_master_rules():
    """
    Oracle query conventions:
      planet = "Day_Master_Stem", sign = "甲" (etc)
      planet = "Day_Master_Element", sign = "Wood" (etc)  [optional]
    """
    rules = []
    for stem, data in DAY_MASTERS.items():
        for chapter in ["Identity", "Finances", "Destiny"]:
            rules.append({
                "system": "Saju",
                "planet": "Day_Master_Stem",
                "sign": stem,
                "chapter": chapter,
                "themes": [data["element"]] + data["themes"],
                "meaning": f"{data['name']} (Element: {data['element']}): {data['desc']}"
            })

    # Element-only “lens” (useful god & strength modules often speak in elements)
    element_lens = {
        "Wood": "Growth, strategy, flexibility, networking, and expansion through connection.",
        "Fire": "Visibility, momentum, expression, leadership and influence through attention.",
        "Earth": "Stability, structure, management, reliability, and long-term building.",
        "Metal": "Standards, precision, justice, boundaries, discipline and execution.",
        "Water": "Adaptability, intelligence, negotiation, insight and opportunistic timing."
    }
    for element, meaning in element_lens.items():
        for chapter in ["Identity", "Career", "Finances", "Destiny"]:
            rules.append({
                "system": "Saju",
                "planet": "Element_Lens",
                "sign": element,
                "chapter": chapter,
                "themes": [element, "Physics", "Leverage"],
                "meaning": f"Element lens = {element}. {meaning}"
            })

    return rules


def generate_pillar_branch_rules():
    """
    Pillar-specific branch rules (Year/Month/Day/Hour).
    Oracle can build keys like:
      planet="Year_Branch", sign="子"
      planet="Month_Branch", sign="寅"
    """
    pillar_to_chapter = {
        "Year": ("Career", "society / public environment / early conditioning"),
        "Month": ("Career", "career engine / work environment / execution style"),
        "Day": ("Relationships", "intimacy / marriage dynamics / personal boundary field"),
        "Hour": ("Destiny", "subconscious / long-range outcomes / inner drivers"),
    }

    rules = []
    for pillar, (chapter, context) in pillar_to_chapter.items():
        for branch, data in BRANCHES.items():
            rules.append({
                "system": "Saju",
                "planet": f"{pillar}_Branch",
                "sign": branch,
                "chapter": chapter,
                "themes": [data["element"]] + data["themes"],
                "meaning": f"{data['name']} in {pillar} Branch ({context}). {data['desc']}"
            })
    return rules


def generate_pillar_stem_rules():
    """
    Pillar-specific stem rules (Year/Month/Day/Hour).
    Oracle keys:
      planet="Year_Stem", sign="丙"
    """
    pillar_to_chapter = {
        "Year": ("Career", "outer world influence, public identity shaping"),
        "Month": ("Career", "work engine, drive style, sustained execution"),
        "Day": ("Identity", "core operating style, self-management patterns"),
        "Hour": ("Destiny", "late-life momentum, hidden intentions and future focus"),
    }

    rules = []
    for pillar, (chapter, context) in pillar_to_chapter.items():
        for stem, data in DAY_MASTERS.items():
            rules.append({
                "system": "Saju",
                "planet": f"{pillar}_Stem",
                "sign": stem,
                "chapter": chapter,
                "themes": [data["element"]] + data["themes"],
                "meaning": f"{data['name']} in {pillar} Stem ({context}). {data['desc']}"
            })
    return rules


def generate_hidden_stem_rules():
    """
    Oracle can query:
      planet="Hidden_Stems", sign=<branch>
    """
    rules = []
    for branch, stems in HIDDEN_STEMS.items():
        stem_names = [DAY_MASTERS[s]["name"] if s in DAY_MASTERS else s for s in stems]
        elements = [DAY_MASTERS[s]["element"] if s in DAY_MASTERS else "Unknown" for s in stems]
        rules.append({
            "system": "Saju",
            "planet": "Hidden_Stems",
            "sign": branch,
            "chapter": "Destiny",
            "themes": ["Hidden", "Subtext"] + elements,
            "meaning": (
                f"Hidden Stems (Cang Gan) for branch {branch}: {', '.join(stems)}. "
                f"Submerged forces: {', '.join(stem_names)}. Elements: {', '.join(elements)}."
            )
        })
    return rules


def generate_ten_god_rules():
    """
    Oracle query:
      planet="10_God", sign="Wealth" etc
    """
    rules = []
    for god, data in TEN_GODS.items():
        rules.append({
            "system": "Saju",
            "planet": "10_God",
            "sign": god,
            "chapter": data["chapter"],
            "themes": data["themes"] + ["Elemental Dynamics"],
            "meaning": f"10 God = {god}. {data['desc']}"
        })
    return rules


def generate_void_emptiness_rules():
    """
    Two layers:
      1) General rule: planet="Status", sign="Void_Emptiness"
      2) Branch-specific: planet="Void_Branch", sign=<branch>
    """
    rules = [{
        "system": "Saju",
        "planet": "Status",
        "sign": "Void_Emptiness",
        "chapter": "Destiny",
        "themes": ["Karma", "Delay", "Intuition"],
        "meaning": (
            "Void Emptiness (Kong Wang) indicates a temporarily hollowed material channel. "
            "It can show delays, missing support, or effort not matching immediate results. "
            "It also increases intuition and spiritual depth. Results improve when timing 'fills' the void."
        )
    }]

    for branch, data in BRANCHES.items():
        rules.append({
            "system": "Saju",
            "planet": "Void_Branch",
            "sign": branch,
            "chapter": "Destiny",
            "themes": ["Karma", "Delay", data["element"]],
            "meaning": (
                f"Branch {branch} is marked as Void Emptiness for this chart cycle. "
                f"Expect delays or a hollow feeling in themes associated with {data['name']}. "
                "Timing periods can temporarily 'fill' the void and unlock progress."
            )
        })
    return rules


def generate_strength_and_useful_god_rules():
    """
    Oracle will compute:
      - Day Master strength tier: Very_Strong/Strong/Average/Weak/Very_Weak
      - Useful God (Yong Shen): Wood/Fire/Earth/Metal/Water

    Query:
      planet="DM_Strength", sign=<tier>
      planet="Useful_God", sign=<element>
    """
    strength_tiers = {
        "Very_Strong": "Excess power. Wins through control and output discipline. Needs drain/structure to avoid dominance problems.",
        "Strong": "High capacity. Able to execute; needs direction to avoid scattering energy.",
        "Average": "Balanced capacity. Outcomes depend on timing, decisions, and environment selection.",
        "Weak": "Low capacity. Wins through support, systems, mentors, and careful pacing.",
        "Very_Weak": "Strained capacity. Avoid brute force. Focus on stabilizing, support, health, and simple repeatable moves."
    }

    element_use = {
        "Wood": "Useful God = Wood: growth, strategy, relationships, education, and expanding pathways. Build networks and long-term projects.",
        "Fire": "Useful God = Fire: visibility, marketing, performance, leadership, confidence. Get seen; increase momentum.",
        "Earth": "Useful God = Earth: stability, process, budgeting, operations. Build structure; slow, reliable gains.",
        "Metal": "Useful God = Metal: precision, standards, discipline, boundaries, law/finance/engineering thinking. Cut waste; enforce rules.",
        "Water": "Useful God = Water: intelligence, negotiation, dealmaking, adaptability, research. Learn fast; exploit timing."
    }

    rules = []
    for tier, meaning in strength_tiers.items():
        for chapter in ["Identity", "Career", "Finances", "Destiny"]:
            rules.append({
                "system": "Saju",
                "planet": "DM_Strength",
                "sign": tier,
                "chapter": chapter,
                "themes": ["Strength", "Capacity", "Execution"],
                "meaning": f"Day Master Strength = {tier}. {meaning}"
            })

    for element, meaning in element_use.items():
        for chapter in ["Career", "Finances", "Destiny", "Identity"]:
            rules.append({
                "system": "Saju",
                "planet": "Useful_God",
                "sign": element,
                "chapter": chapter,
                "themes": ["CRITICAL LEVERAGE", element, "Strategy"],
                "meaning": meaning
            })

    return rules


def generate_saju_dataset_part1():
    rules = []
    rules.extend(generate_day_master_rules())
    rules.extend(generate_pillar_branch_rules())
    rules.extend(generate_pillar_stem_rules())
    rules.extend(generate_hidden_stem_rules())
    rules.extend(generate_ten_god_rules())
    rules.extend(generate_void_emptiness_rules())
    rules.extend(generate_strength_and_useful_god_rules())
    return rules


def generate_luck_pillar_rules():
    """
    Oracle will output:
      - Current Da Yun stem/branch
      - Current Liu Nian stem/branch

    Query:
      planet="Da_Yun_Stem", sign=<stem>
      planet="Da_Yun_Branch", sign=<branch>
      planet="Liu_Nian_Stem", sign=<stem>
      planet="Liu_Nian_Branch", sign=<branch>
    """
    rules = []

    # Da Yun (10-year) — stems
    for stem, data in DAY_MASTERS.items():
        rules.append({
            "system": "Saju",
            "planet": "Da_Yun_Stem",
            "sign": stem,
            "chapter": "Predictive",
            "themes": ["Decade Cycle", data["element"]] + data["themes"],
            "meaning": (
                f"Da Yun (10-year luck) Stem = {data['name']}. Over this decade, the environment rewards this element/style: "
                f"{data['desc']}"
            )
        })

    # Da Yun (10-year) — branches
    for branch, data in BRANCHES.items():
        rules.append({
            "system": "Saju",
            "planet": "Da_Yun_Branch",
            "sign": branch,
            "chapter": "Predictive",
            "themes": ["Decade Cycle", data["element"]] + data["themes"],
            "meaning": (
                f"Da Yun (10-year luck) Branch = {data['name']}. Over this decade, circumstances tend to express through: "
                f"{data['desc']}"
            )
        })

    # Liu Nian (annual) — stems
    for stem, data in DAY_MASTERS.items():
        rules.append({
            "system": "Saju",
            "planet": "Liu_Nian_Stem",
            "sign": stem,
            "chapter": "Predictive",
            "themes": ["Annual Cycle", data["element"]] + data["themes"],
            "meaning": (
                f"Liu Nian (annual pillar) Stem = {data['name']}. This year pushes themes of {data['element']} with: {data['desc']}"
            )
        })

    # Liu Nian (annual) — branches
    for branch, data in BRANCHES.items():
        rules.append({
            "system": "Saju",
            "planet": "Liu_Nian_Branch",
            "sign": branch,
            "chapter": "Predictive",
            "themes": ["Annual Cycle", data["element"]] + data["themes"],
            "meaning": (
                f"Liu Nian (annual pillar) Branch = {data['name']}. This year’s events tend to express through: {data['desc']}"
            )
        })

    # Generic “what is Da Yun / Liu Nian” rules
    rules.append({
        "system": "Saju",
        "planet": "Predictive",
        "sign": "Da_Yun",
        "chapter": "Predictive",
        "themes": ["Timeline", "Decade Cycle"],
        "meaning": (
            "Da Yun (10-year luck pillars) describe the decade-wide environment that amplifies or weakens certain elements. "
            "It changes the difficulty curve. A good natal chart can underperform in a harsh Da Yun, and a difficult natal chart can rise in a supportive Da Yun."
        )
    })
    rules.append({
        "system": "Saju",
        "planet": "Predictive",
        "sign": "Liu_Nian",
        "chapter": "Predictive",
        "themes": ["Timeline", "Annual Cycle"],
        "meaning": (
            "Liu Nian (annual passing pillar) is the active yearly trigger. It activates hidden stems, completes combinations, "
            "provokes clashes/harms, and can temporarily fill Void Emptiness."
        )
    })

    return rules


def generate_shen_sha_rules():
    """
    Shen Sha are symbolic stars. Oracle will compute which ones apply.
    Query:
      planet="Shen_Sha", sign=<star_name>
    """
    stars = [
        {
            "name": "Peach_Blossom",
            "themes": ["Attraction", "Charisma", "Social"],
            "meaning": "Peach Blossom increases attraction and social pull. Great for sales/romance; risky for distractions and entanglements."
        },
        {
            "name": "Nobleman",
            "themes": ["Help", "Mentors", "Protection"],
            "meaning": "Nobleman star: help arrives through benefactors, mentors, or people with power. Use humility and relationships."
        },
        {
            "name": "Traveling_Horse",
            "themes": ["Movement", "Travel", "Opportunity"],
            "meaning": "Traveling Horse: movement, change, travel, relocations, and sudden opportunity through mobility."
        },
        {
            "name": "Academic_Star",
            "themes": ["Study", "Credentials", "Intellect"],
            "meaning": "Academic star: study and credentials become high-leverage. Great for exams, writing, research and skill stacking."
        },
        {
            "name": "Rob_Wealth",
            "themes": ["Competition", "Loss", "Peers"],
            "meaning": "Rob Wealth star: competitors are active. Great for teamwork if managed; risky for financial leakage and rivalry."
        },
        {
            "name": "7_Killings",
            "themes": ["Pressure", "Risk", "Intensity"],
            "meaning": "Seven Killings pressure: decisive action needed. Strong for leadership under pressure; risky for burnout and conflict."
        },
        {
            "name": "Heavenly_Virtue",
            "themes": ["Relief", "Grace", "Recovery"],
            "meaning": "Heavenly Virtue: softens harsh outcomes and increases recovery after mistakes. Still requires correct behavior."
        },
        {
            "name": "Solitary_Star",
            "themes": ["Isolation", "Independence", "Inner Work"],
            "meaning": "Solitary star: independence rises. Great for deep work; risky for relationship distance if overdone."
        },
    ]

    rules = []
    for st in stars:
        for chapter in ["Identity", "Relationships", "Career", "Finances", "Predictive", "Destiny"]:
            rules.append({
                "system": "Saju",
                "planet": "Shen_Sha",
                "sign": st["name"],
                "chapter": "Predictive" if chapter == "Predictive" else chapter,
                "themes": st["themes"],
                "meaning": f"Shen Sha = {st['name']}. {st['meaning']}"
            })
    return rules


def generate_qi_phase_rules():
    """
    12 Stages of Life (Qi Phase). Oracle calculates Qi Phase per pillar relative to Day Master.
    Query:
      planet="Qi_Phase", sign=<phase>
    """
    phases = [
        ("Chang_Sheng", "Birth", "New growth, initiation energy, strong momentum for beginnings."),
        ("Mu_Yu", "Bath", "Refinement and sensitivity; protect focus and avoid distraction."),
        ("Guan_Dai", "Crown", "Training and status-building; develop discipline and reputation."),
        ("Lin_Guan", "Officer", "Peak execution; good for responsibility and leadership roles."),
        ("Di_Wang", "Emperor", "Maximum power; great for achievement but ego risk rises."),
        ("Shuai", "Decline", "Energy softens; consolidation beats expansion."),
        ("Bing", "Sickness", "Fragile phase; prioritize health, systems, and recovery."),
        ("Si", "Death", "Endings and letting go; detach from expired strategies."),
        ("Mu", "Tomb", "Storage phase; internalize lessons and build reserves."),
        ("Jue", "Extinction", "Reset; avoid high-risk moves, re-plan carefully."),
        ("Tai", "Conception", "Seed stage; build quietly, learn, prepare."),
        ("Yang", "Nourish", "Nourishment phase; steady growth returns with correct support.")
    ]

    rules = []
    for code, label, meaning in phases:
        for chapter in ["Predictive", "Health", "Career", "Finances", "Destiny"]:
            rules.append({
                "system": "Saju",
                "planet": "Qi_Phase",
                "sign": code,
                "chapter": "Predictive",
                "themes": ["Energy Cycle", label],
                "meaning": f"Qi Phase = {label} ({code}). {meaning}"
            })
    return rules


def generate_interaction_rules():
    """
    Interactions (clashes, harms, destructions, punishments).
    Oracle produces interaction codes/types and queries:
      planet="Interaction", sign=<interaction_type>
    """
    rules = []

    # Clashes (冲)
    clashes = [
        ("Rat-Horse_Clash", "子午冲", "High volatility: movement, conflict, abrupt changes; can also unlock breakthroughs if directed."),
        ("Ox-Goat_Clash", "丑未冲", "Values clash: family/resources conflicts; requires negotiation and boundaries."),
        ("Tiger-Monkey_Clash", "寅申冲", "Competitive clash: authority, risk, speed; avoid impulsive escalation."),
        ("Rabbit-Rooster_Clash", "卯酉冲", "Social/relationship clash: reputation, criticism, image wars; stabilize communication."),
        ("Dragon-Dog_Clash", "辰戌冲", "Power clash: belief systems and status; restructure long-term plans."),
        ("Snake-Pig_Clash", "巳亥冲", "Ideals clash: hidden motives, confusion; verify facts and protect energy."),
    ]

    # Harms (害)
    harms = [
        ("Rat-Goat_Harm", "子未害", "Subtle friction: misunderstandings, hidden resentments; clarify intentions."),
        ("Ox-Horse_Harm", "丑午害", "Slow burn tension: effort not rewarded; adjust strategy and expectations."),
        ("Tiger-Snake_Harm", "寅巳害", "Strategic sabotage risk: protect plans; avoid oversharing."),
        ("Rabbit-Dragon_Harm", "卯辰害", "Unclear agreements: details matter; keep written structure."),
        ("Monkey-Pig_Harm", "申亥害", "Energy leak: distraction and mismatched priorities; simplify."),
        ("Rooster-Dog_Harm", "酉戌害", "Critique loops: relationship strain through standards; soften and negotiate."),
    ]

    # Destructions / Break (破)
    destructions = [
        ("Rat-Rooster_Break", "子酉破", "Sudden disruptions in plans; protect finances and reputation."),
        ("Ox-Dragon_Break", "丑辰破", "Structural cracks: fix foundations and stop patching symptoms."),
        ("Tiger-Pig_Break", "寅亥破", "Ideals vs reality conflict; reset goals and commitments."),
        ("Rabbit-Horse_Break", "卯午破", "Relationship volatility; avoid impulsive exits."),
        ("Snake-Monkey_Break", "巳申破", "Trust issues and reversals; verify information."),
        ("Goat-Dog_Break", "未戌破", "Family/home stress; boundaries and responsibilities must be clarified."),
    ]

    # Punishments (刑)
    punishments = [
        ("Uncivil_Punishment", "子卯刑", "Self-sabotage through agitation or impatience; slow down and stabilize habits."),
        ("Three_Punishment_Fire", "寅巳申刑", "High conflict triangle; avoid ego wars and reckless risk."),
        ("Three_Punishment_Earth", "丑未戌刑", "Obligation pressure; resentment builds if boundaries are weak."),
        ("Self_Punishment_Dragon", "辰辰自刑", "Overthinking and internal loops; simplify and commit."),
        ("Self_Punishment_Horse", "午午自刑", "Burnout risk; reduce intensity, increase recovery."),
        ("Self_Punishment_Rooster", "酉酉自刑", "Perfectionism loop; accept good-enough execution."),
        ("Self_Punishment_Pig", "亥亥自刑", "Emotional overwhelm; tighten routines and reduce chaos."),
    ]

    def add_interactions(items, category):
        for code, hanzi, meaning in items:
            rules.append({
                "system": "Saju",
                "planet": "Interaction",
                "sign": code,
                "chapter": "Predictive",
                "themes": ["Interaction", category],
                "meaning": f"{category}: {hanzi}. {meaning}"
            })

    add_interactions(clashes, "Clash")
    add_interactions(harms, "Harm")
    add_interactions(destructions, "Break")
    add_interactions(punishments, "Punishment")

    return rules


def generate_saju_dataset_part2():
    rules = []
    rules.extend(generate_luck_pillar_rules())
    rules.extend(generate_shen_sha_rules())
    rules.extend(generate_qi_phase_rules())
    rules.extend(generate_interaction_rules())
    return rules


def bulk_load_saju(rules):
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
    print("Generating Saju Master Dataset (Part 1 + Part 2)...")

    # If both parts are pasted into one seed_saju.py file, just call directly:
    dataset = []
    dataset.extend(generate_saju_dataset_part1())
    dataset.extend(generate_saju_dataset_part2())

    print(f"Uploading to Neo4j... ({len(dataset)} rules)")
    driver = get_db_driver()
    ensure_constraints(driver)
    driver.close()

    bulk_load_saju(dataset)
    print(f"✅ Successfully seeded {len(dataset)} Saju rules into Neo4j!")



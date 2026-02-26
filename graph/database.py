# =========================================
# database.py — v2 (Upgraded)
# =========================================
# Goal:
# - Provide fast, bulk Neo4j rule fetching for:
#   - Oracle-driven "keys" (system, placement, sign)
#   - Chapter filtering
# - Return structured JSON-like records (not English sentences)
# - Keep a compatibility wrapper fetch_chapter_rules(...) for your current app.py
#
# Graph model:
# (System {name})-[:USES]->(Placement {name})-[:IN_SIGN {meaning,themes,chapter}]->(Sign {name})
# =========================================

from __future__ import annotations

import os
import threading
import json

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from neo4j import GraphDatabase, Driver



# -------------------------
# Config / Driver singleton
# -------------------------

_DRIVER: Optional[Driver] = None
_DRIVER_LOCK = threading.Lock()


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def get_db_driver() -> Driver:

    global _DRIVER
    if _DRIVER is not None:
        return _DRIVER

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD")

    if not uri or not pwd:
        raise ValueError(
            "Missing Neo4j credentials. Set NEO4J_URI and NEO4J_PASSWORD (and optionally NEO4J_USER)."
        )

    _DRIVER = GraphDatabase.driver(uri, auth=(user, pwd))
    return _DRIVER

def close_db_driver() -> None:
    global _DRIVER
    with _DRIVER_LOCK:
        if _DRIVER is not None:
            _DRIVER.close()
            _DRIVER = None


def ensure_constraints() -> None:
    driver = get_db_driver()
    constraints = [
        "CREATE CONSTRAINT rule_identity IF NOT EXISTS FOR (r:Rule) REQUIRE (r.system, r.placement, r.sign, r.chapter) IS UNIQUE",
    ]
    with driver.session() as session:
        for c in constraints:
            session.run(c)



# -------------------------
# Data types
# -------------------------

@dataclass(frozen=True)
class RuleKey:
    system: str
    placement: str
    sign: str
    meta: Optional[Dict[str, Any]] = None

@dataclass
class RuleHit:
    system: str
    placement: str
    sign: str
    chapter: str
    meaning: str
    themes: List[str]
    meta: Dict[str, Any]

# -------------------------
# Core: Bulk fetch by keys
# -------------------------
def fetch_rules_for_keys(
    keys: List[RuleKey],
    chapters: List[str],
    include_global: bool = True,
    uri: str = None,
    user: str = None,
    password: str = None,
) -> List[RuleHit]:
    if not keys:
        return []

    # include meta so you can label instances (e.g. aspects)
    key_rows = [{
        "system": k.system,
        "placement": k.placement,
        "sign": k.sign,
        "meta": k.meta or {}
    } for k in keys]

    cypher = """
    UNWIND $keys AS k
    MATCH (r:Rule {system: k.system, placement: k.placement, sign: k.sign})
    WHERE toLower(r.chapter) IN [c IN $chapters | toLower(c)]
       OR ($include_global AND toLower(r.chapter) = 'global')
    RETURN
      r.system     AS system,
      r.placement  AS placement,
      r.sign       AS sign,
      r.chapter    AS chapter,
      r.meaning    AS meaning,
      r.themes     AS themes,
      r.meta_json  AS meta_json,
      k.meta       AS request_meta
    ORDER BY system, chapter, placement, sign;
    """

    # Use singleton driver unless explicit creds provided
    driver = get_db_driver() if not uri else GraphDatabase.driver(uri, auth=(user, password))

    try:
        with driver.session() as session:
            rows = session.run(
                cypher,
                keys=key_rows,
                chapters=chapters,
                include_global=include_global
            ).data()

        out: List[RuleHit] = []
        for row in rows:
            # DB meta
            meta: Dict[str, Any] = {}
            mj = row.get("meta_json")
            if mj:
                try:
                    meta = json.loads(mj) if isinstance(mj, str) else dict(mj)
                except Exception:
                    meta = {"_meta_json_raw": mj}

            # Request meta (instance labels etc.)
            req_meta = row.get("request_meta") or {}
            if isinstance(req_meta, dict):
                meta.update(req_meta)

            themes = row.get("themes") or []
            if isinstance(themes, str):
                themes = [t.strip() for t in themes.split(",") if t.strip()]

            out.append(RuleHit(
                system=row["system"],
                placement=row["placement"],
                sign=row["sign"],
                chapter=row["chapter"],
                meaning=row.get("meaning") or "",
                themes=themes,
                meta=meta
            ))

        return out
    finally:
        # Only close if you created an ad-hoc driver
        if uri and driver is not None:
            driver.close()


# ------------------------------------------
# Convenience: Grouped output (oracle-ready)
# ------------------------------------------
def fetch_rules_grouped_by_chapter(
    keys: Sequence[Union[RuleKey, Dict[str, Any]]],
    chapters: Sequence[str],
    include_global: bool = True,
) -> Dict[str, List[RuleHit]]:
    normalized: List[RuleKey] = []
    for k in keys:
        if isinstance(k, RuleKey):
            normalized.append(k)
        elif isinstance(k, dict):
            normalized.append(RuleKey(
                system=k.get("system",""),
                placement=k.get("placement",""),
                sign=k.get("sign",""),
                meta=k.get("meta")
            ))

    hits = fetch_rules_for_keys(normalized, chapters=list(chapters), include_global=include_global)

    grouped: Dict[str, List[RuleHit]] = {c: [] for c in chapters}
    if include_global:
        grouped.setdefault("Global", [])

    for h in hits:
        grouped.setdefault(h.chapter, [])
        grouped[h.chapter].append(h)

    return grouped


# ----------------------------------------------------
# Compatibility: old-style fetch_chapter_rules wrapper
# ----------------------------------------------------
# This lets your current app.py keep working while you move
# logic into oracle.py. It returns the same shape:
#   {"rules": [string...], "all_themes": [string...]}
# But internally it uses the new bulk fetch.
# ----------------------------------------------------

def _normalize_ten_god(raw: str) -> str:
    """
    Your math engine outputs things like:
      "Wealth (Direct/Indirect)"
    but seeds use just:
      "Wealth" / "Power" / "Resource" / "Output" / "Companion"
    """
    if not raw:
        return raw
    raw_low = raw.lower()
    if "wealth" in raw_low:
        return "Wealth"
    if "power" in raw_low or "officer" in raw_low or "killings" in raw_low:
        return "Power"
    if "resource" in raw_low:
        return "Resource"
    if "output" in raw_low or "eating god" in raw_low or "hurting officer" in raw_low:
        return "Output"
    if "companion" in raw_low or "rob wealth" in raw_low or "friend" in raw_low:
        return "Companion"
    return raw


def build_keys_from_calculated_charts(calculated: Dict[str, Any]) -> List[RuleKey]:
    """
    Best-effort extractor from your current math_engine structure.
    This is NOT the final endgame (oracle will generate keys),
    but it keeps your current pipeline functional.

    It extracts the keys that match your seed conventions:
      Western:
        - Placements planet->sign
        - Houses House_# -> sign
        - Aspects list -> ("Aspects", aspect_type)
        - Fixed_Stars list -> ("Fixed_Star", star_name)  [if you seed this later]
        - Predictive time lords etc can become keys later via oracle
      Vedic_engine:
        - Placements planet->sign
        - Dignity tiers -> ("Dignity", tier)
        - Nakshatra+pada -> ("Nakshatra_Pada", f"{nak}_P{pada}")
        - Atmakaraka planet -> ("Atmakaraka_Planet", planet)
        - Atmakaraka sign -> ("Atmakaraka_Sign", sign)
        - Vargottama -> ("Vargottama", planet)
        - Yogas -> ("Yoga", yoga_code) if already code-like
        - D10 placements -> ("D10_<planet>", sign) if present
        - Bhava Chalit -> ("Chalit_<planet>", "Bhava_#") if present
        - Shadbala tiers -> ("Shadbala_<planet>", tier) if present
        - SAV tiers -> ("SAV_<sign>", tier) if present
      Saju:
        - Day master stem -> ("Day_Master_Stem", stem)
        - Pillar stems/branches -> ("Year_Stem"...)
        - Hidden stems by pillar branch -> ("Hidden_Stems", branch)
        - 10 gods -> ("10_God", category)
        - Void -> ("Void_Branch", branch)
        - Useful God -> ("Useful_God", element)
        - DM strength -> ("DM_Strength", tier)
        - Luck pillars -> ("Da_Yun_Stem"...), ("Liu_Nian_Stem"...)
        - Interactions -> ("Interaction", code) if already code-like
        - Shen Sha -> ("Shen_Sha", name)
        - Qi phase -> ("Qi_Phase", code)
    """
    keys: List[RuleKey] = []

    # ---- Western ----
    w = calculated.get("Western") or calculated.get("western", {})
    w_pl = w.get("Placements") or w.get("placements", {})
    for pl_name, obj in w_pl.items():
        if isinstance(obj, dict) and "sign" in obj:
            keys.append(RuleKey("Western", pl_name, obj["sign"]))

    w_houses = w.get("Houses", {})
    for h_name, obj in w_houses.items():
        if isinstance(obj, dict) and "sign" in obj:
            keys.append(RuleKey("Western", h_name, obj["sign"]))

    # Aspects (list)
    w_aspects = w.get("Aspects", [])
    if isinstance(w_aspects, list):
        for a in w_aspects:
            # Expect: {"p1": "Sun", "p2": "Mars", "aspect": "Square"}
            if isinstance(a, dict) and a.get("aspect"):
                aspect_type = str(a["aspect"])
                # Seeded as planet="Aspects", sign=<aspect_type>
                meta = {"instance": f"{a.get('p1','?')} {aspect_type} {a.get('p2','?')}"}
                keys.append(RuleKey("Western", "Aspects", aspect_type, meta=meta))

    # Fixed Stars (optional future seeds)
    w_fs = w.get("Fixed_Stars", [])
    if isinstance(w_fs, list):
        for fs in w_fs:
            if isinstance(fs, dict) and fs.get("star"):
                keys.append(RuleKey("Western", "Fixed_Star", str(fs["star"]), meta={"planet": fs.get("planet")}))

    # ---- Vedic_engine ----
    v = calculated.get("Vedic_engine") or calculated.get("vedic_engine") or calculated.get("vedic", {})
    v_pl = v.get("Placements", {})
    for pl_name, obj in v_pl.items():
        if isinstance(obj, dict):
            if "sign" in obj:
                keys.append(RuleKey("Vedic_engine", pl_name, obj["sign"]))

            # dignity tier
            if obj.get("dignity"):
                keys.append(RuleKey("Vedic_engine", "Dignity", str(obj["dignity"]).replace(" ", "_")))

            # nakshatra+pada
            if obj.get("nakshatra") and obj.get("pada"):
                nak = str(obj["nakshatra"]).replace(" ", "_")
                pada = int(obj["pada"])
                keys.append(RuleKey("Vedic_engine", "Nakshatra_Pada", f"{nak}_P{pada}"))

            # vargottama
            if obj.get("is_vargottama") is True:
                keys.append(RuleKey("Vedic_engine", "Vargottama", pl_name))

    # Vedic_engine houses
    v_houses = v.get("Houses", {})
    for h_name, obj in v_houses.items():
        if isinstance(obj, dict) and "sign" in obj:
            keys.append(RuleKey("Vedic_engine", h_name, obj["sign"]))

    # Atmakaraka
    ak = v.get("Atmakaraka")
    if ak and isinstance(ak, str):
        keys.append(RuleKey("Vedic_engine", "Atmakaraka_Planet", ak))
        # Attempt AK sign if available
        ak_obj = v_pl.get(ak)
        if isinstance(ak_obj, dict) and ak_obj.get("sign"):
            keys.append(RuleKey("Vedic_engine", "Atmakaraka_Sign", str(ak_obj["sign"])))

    # Yogas
    yogas = v.get("Yogas", [])
    if isinstance(yogas, list):
        for y in yogas:
            if isinstance(y, str):
                # If you later standardize to codes like "Raja_Yoga", this will match seeds.
                y_code = y.replace(" ", "_")
                keys.append(RuleKey("Vedic_engine", "Yoga", y_code))

    # Vimshottari (example key)
    v_pred = v.get("Predictive", {})
    if isinstance(v_pred, dict):
        md = v_pred.get("Current_Maha_Dasha_Lord") or v_pred.get("Maha_Dasha")
        if md:
            keys.append(RuleKey("Vedic_engine", "Maha_Dasha", str(md)))

        ad = v_pred.get("Current_Antar_Dasha_Lord") or v_pred.get("Antar_Dasha")
        if ad:
            keys.append(RuleKey("Vedic_engine", "Antar_Dasha", str(ad)))

    # ---- Saju ----
    s = calculated.get("Saju") or calculated.get("saju") or calculated.get("bazi", {})
    dm = s.get("Day_Master", {})
    if isinstance(dm, dict) and dm.get("stem"):
        keys.append(RuleKey("Saju", "Day_Master_Stem", str(dm["stem"])))
    if isinstance(dm, dict) and dm.get("element"):
        keys.append(RuleKey("Saju", "Element_Lens", str(dm["element"])))

    pillars = s.get("Pillars", {})
    if isinstance(pillars, dict):
        for p_name, pdata in pillars.items():
            if not isinstance(pdata, dict):
                continue
            stem = pdata.get("stem")
            br = pdata.get("branch")
            if stem:
                keys.append(RuleKey("Saju", f"{p_name}_Stem", str(stem)))
            if br:
                keys.append(RuleKey("Saju", f"{p_name}_Branch", str(br)))
                # Hidden stems key by branch (seeded)
                keys.append(RuleKey("Saju", "Hidden_Stems", str(br)))

            # 10 gods (normalize)
            sg = pdata.get("stem_10_god")
            bg = pdata.get("branch_10_god")
            if sg:
                keys.append(RuleKey("Saju", "10_God", _normalize_ten_god(str(sg))))
            if bg:
                keys.append(RuleKey("Saju", "10_God", _normalize_ten_god(str(bg))))

    # Void emptiness branches
    voids = s.get("Void_Emptiness", [])
    if isinstance(voids, list):
        for vb in voids:
            keys.append(RuleKey("Saju", "Void_Branch", str(vb)))
        if voids:
            keys.append(RuleKey("Saju", "Status", "Void_Emptiness"))

    # Predictive: annual pillar (example)
    s_pred = s.get("Predictive", {})
    if isinstance(s_pred, dict):
        ap = s_pred.get("Current_Year_Pillar")
        if isinstance(ap, dict):
            if ap.get("stem"):
                keys.append(RuleKey("Saju", "Liu_Nian_Stem", str(ap["stem"])))
            if ap.get("branch"):
                keys.append(RuleKey("Saju", "Liu_Nian_Branch", str(ap["branch"])))

    return keys


def fetch_chapter_rules(calculated_charts: Dict[str, Any], target_chapter: str) -> Dict[str, Any]:
    """
    Compatibility output for your current app.py:
      {
        "rules": [formatted strings...],
        "all_themes": [theme strings...],
        "hits": [structured RuleHit...],   # bonus: for debugging/oracle transition
      }

    NOTE:
      This is a transitional adapter. Once oracle.py exists,
      app.py should call fetch_rules_for_keys(oracle_keys, chapters=...).
    """
    keys = build_keys_from_calculated_charts(calculated_charts)

    hits = fetch_rules_for_keys(
        keys,
        chapters=[target_chapter],
        include_global=True,
    )

    rules_lines: List[str] = []
    all_themes: List[str] = []

    for h in hits:
        # If meta contains an "instance" label (e.g. "Sun Square Mars"), include it
        if h.meta and "instance" in h.meta:
            label = f"{h.meta['instance']}"
            rules_lines.append(f"[{h.system} {label}]: {h.meaning}")
        else:
            rules_lines.append(f"[{h.system} {h.placement} in {h.sign}]: {h.meaning}")

        all_themes.extend(h.themes)

    return {"rules": rules_lines, "all_themes": all_themes, "hits": hits}

# seed_rules.py (or wherever you insert rules)

import json
from neo4j import GraphDatabase

def upsert_rules(uri: str, user: str, password: str, rows: list[dict]) -> None:
    cypher = """
    UNWIND $rows AS row
    MERGE (r:Rule {
      system: row.system,
      placement: row.placement,
      sign: row.sign,
      chapter: row.chapter
    })
    SET
      r.meaning   = row.meaning,
      r.themes    = coalesce(row.themes, []),
      r.meta_json = row.meta_json,
      r.updated_at = datetime()
    ON CREATE SET
      r.created_at = datetime();
    """

    cooked = []
    for row in rows:
        cooked.append({
            "system": row["system"],
            "placement": row["placement"],
            "sign": row["sign"],
            "chapter": row["chapter"],
            "meaning": row.get("meaning", ""),
            "themes": row.get("themes", []),
            "meta_json": json.dumps(row.get("meta", {}), ensure_ascii=False),
        })

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            session.run(cypher, rows=cooked)
    finally:
        driver.close()

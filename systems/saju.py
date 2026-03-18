"""Saju (Bazi) Engine."""
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

# -----------------------------
# Bazi (Saju) Helpers
# -----------------------------
try:
    from lunar_python import Solar
except Exception as e:
    Solar = None

STEMS = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
BRANCHES = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]

STEM_ELEMENT = {"甲":"Wood","乙":"Wood","丙":"Fire","丁":"Fire","戊":"Earth","己":"Earth","庚":"Metal","辛":"Metal","壬":"Water","癸":"Water"}
BRANCH_ELEMENT = {"子":"Water","丑":"Earth","寅":"Wood","卯":"Wood","辰":"Earth","巳":"Fire","午":"Fire","未":"Earth","申":"Metal","酉":"Metal","戌":"Earth","亥":"Water"}

HIDDEN_STEMS = {
    "子":["癸"],
    "丑":["己","癸","辛"],
    "寅":["甲","丙","戊"],
    "卯":["乙"],
    "辰":["戊","乙","癸"],
    "巳":["丙","庚","戊"],
    "午":["丁","己"],
    "未":["己","丁","乙"],
    "申":["庚","壬","戊"],
    "酉":["辛"],
    "戌":["戊","辛","丁"],
    "亥":["壬","甲"]
}

GEN_CYCLE = {"Wood":"Fire","Fire":"Earth","Earth":"Metal","Metal":"Water","Water":"Wood"}
CTRL_CYCLE = {"Wood":"Earth","Earth":"Water","Water":"Fire","Fire":"Metal","Metal":"Wood"}

def ten_god(dm_el: str, target_el: str) -> str:
    if dm_el == target_el:
        return "Companion"
    if GEN_CYCLE[dm_el] == target_el:
        return "Output"
    if CTRL_CYCLE[dm_el] == target_el:
        return "Wealth"
    if CTRL_CYCLE[target_el] == dm_el:
        return "Power"
    if GEN_CYCLE[target_el] == dm_el:
        return "Resource"
    return "Unknown"

# Chang Sheng 12 stages mapping start branch (长生) per stem
# Using common mnemonic: 甲亥 乙午 丙寅 丁酉 戊寅 己酉 庚巳 辛子 壬申 癸卯
CS_START = {
    "甲":"亥","乙":"午","丙":"寅","丁":"酉","戊":"寅","己":"酉","庚":"巳","辛":"子","壬":"申","癸":"卯"
}
CS_STAGES = ["ChangSheng","MuYu","GuanDai","LinGuan","DiWang","Shuai","Bing","Si","Mu","Jue","Tai","Yang"]

def qi_phase(stem: str, branch: str) -> Optional[str]:
    if stem not in CS_START or branch not in BRANCHES:
        return None
    start = CS_START[stem]
    sidx = BRANCHES.index(start)
    bidx = BRANCHES.index(branch)
    # Yang stems forward, Yin stems backward
    is_yang = STEMS.index(stem) % 2 == 0
    if is_yang:
        offset = (bidx - sidx) % 12
    else:
        offset = (sidx - bidx) % 12
    return CS_STAGES[offset]

# ── Full Classical Shen Sha (Spirit Stars) ────────────────────────────────────
# Source: Traditional San Ming Tong Hui & Di Tian Sui
# Organized by lookup key (year branch, day branch, or day stem)

# 桃花 Peach Blossom — relationship star (year branch group)
PEACH_BLOSSOM = {
    frozenset(["申","子","辰"]): "酉",
    frozenset(["亥","卯","未"]): "子",
    frozenset(["寅","午","戌"]): "卯",
    frozenset(["巳","酉","丑"]): "午"
}
# 驿马 Traveling Horse — movement, career change (year branch group)
TRAVEL_HORSE = {
    frozenset(["申","子","辰"]): "寅",
    frozenset(["亥","卯","未"]): "巳",
    frozenset(["寅","午","戌"]): "申",
    frozenset(["巳","酉","丑"]): "亥"
}
# 天乙贵人 TianYi Nobleman — benefactors (day stem)
TIANYI = {
    "甲":["丑","未"], "己":["丑","未"],
    "乙":["子","申"], "庚":["子","申"],
    "丙":["亥","酉"], "辛":["亥","酉"],
    "丁":["酉","亥"], "壬":["酉","亥"],
    "戊":["卯","巳"], "癸":["卯","巳"]
}
# 文昌 Literary Star — intelligence, exams, writing (day stem)
WENCHANG = {
    "甲":"巳", "乙":"午", "丙":"申", "丁":"酉",
    "戊":"申", "己":"酉", "庚":"亥", "辛":"子",
    "壬":"寅", "癸":"卯"
}
# 羊刃 Yang Blade / Sword Edge — aggression, surgery, danger (day stem)
YANG_BLADE = {
    "甲":"卯", "乙":"辰", "丙":"午", "丁":"未",
    "戊":"午", "己":"未", "庚":"酉", "辛":"戌",
    "壬":"子", "癸":"丑"
}
# 天德 Heaven Virtue — protection from disasters (month branch)
HEAVEN_VIRTUE = {
    "寅":"丁", "卯":"申", "辰":"壬", "巳":"辛",
    "午":"亥", "未":"甲", "申":"癸", "酉":"寅",
    "戌":"丙", "亥":"乙", "子":"巳", "丑":"庚"
}
# 月德 Moon Virtue — protection, helpful people (month branch)
MOON_VIRTUE = {
    "寅":"丙", "午":"丙", "戌":"丙",
    "亥":"甲", "卯":"甲", "未":"甲",
    "申":"壬", "子":"壬", "辰":"壬",
    "巳":"庚", "酉":"庚", "丑":"庚"
}
# 红鸾 Red Luan — marriage, romance events (year branch)
RED_LUAN = {
    "子":"卯", "丑":"寅", "寅":"丑", "卯":"子",
    "辰":"亥", "巳":"戌", "午":"酉", "未":"申",
    "申":"未", "酉":"午", "戌":"巳", "亥":"辰"
}
# 天喜 Sky Happiness — joyful events, births, weddings (year branch)
SKY_HAPPINESS = {
    "子":"酉", "丑":"申", "寅":"未", "卯":"午",
    "辰":"巳", "巳":"辰", "午":"卯", "未":"寅",
    "申":"丑", "酉":"子", "戌":"亥", "亥":"戌"
}
# 华盖 Canopy Star — spiritual/artistic gift; isolation from mundane (year branch group)
CANOPY = {
    frozenset(["申","子","辰"]): "辰",
    frozenset(["亥","卯","未"]): "未",
    frozenset(["寅","午","戌"]): "戌",
    frozenset(["巳","酉","丑"]): "丑"
}
# 三煞 Three Killings — the most dangerous annual sha (year branch group → year's 3K direction)
THREE_KILLINGS = {
    frozenset(["申","子","辰"]): ["巳","午","未"],  # South
    frozenset(["亥","卯","未"]): ["申","酉","戌"],  # West
    frozenset(["寅","午","戌"]): ["亥","子","丑"],  # North
    frozenset(["巳","酉","丑"]): ["寅","卯","辰"]   # East
}
# 劫煞 Robbery Sha (year branch group)
ROBBERY_SHA = {
    frozenset(["申","子","辰"]): "巳",
    frozenset(["亥","卯","未"]): "申",
    frozenset(["寅","午","戌"]): "亥",
    frozenset(["巳","酉","丑"]): "寅"
}
# 灾煞 Disaster Sha (year branch group)
DISASTER_SHA = {
    frozenset(["申","子","辰"]): "午",
    frozenset(["亥","卯","未"]): "酉",
    frozenset(["寅","午","戌"]): "子",
    frozenset(["巳","酉","丑"]): "卯"
}
# 孤辰 Solitary God (year branch) — loneliness, separation
SOLITARY = {
    "子":"寅", "丑":"寅", "寅":"巳",
    "卯":"巳", "辰":"巳", "巳":"申",
    "午":"申", "未":"申", "申":"亥",
    "酉":"亥", "戌":"亥", "亥":"寅"
}
# 寡宿 Widow Star (year branch) — emotional isolation
WIDOW = {
    "子":"戌", "丑":"戌", "寅":"丑",
    "卯":"丑", "辰":"丑", "巳":"辰",
    "午":"辰", "未":"辰", "申":"未",
    "酉":"未", "戌":"未", "亥":"戌"
}
# 咸池 Xian Chi / Salt Pool — sensuality, dissolute tendencies (year branch group)
XIAN_CHI = {
    frozenset(["申","子","辰"]): "酉",
    frozenset(["亥","卯","未"]): "子",
    frozenset(["寅","午","戌"]): "卯",
    frozenset(["巳","酉","丑"]): "午"
}

# Harms / Punishments / Destructions
LIU_HAI = [("子","未"),("丑","午"),("寅","巳"),("卯","辰"),("申","亥"),("酉","戌")]
PO = [("子","酉"),("丑","辰"),("寅","亥"),("卯","午"),("巳","申"),("未","戌")]
SAN_XING = [
    ("寅","巳","申"),
    ("丑","未","戌"),
    ("子","卯")
]
CLASHES = [
    ({"子","午"},"Rat-Horse Clash"),
    ({"丑","未"},"Ox-Goat Clash"),
    ({"寅","申"},"Tiger-Monkey Clash"),
    ({"卯","酉"},"Rabbit-Rooster Clash"),
    ({"辰","戌"},"Dragon-Dog Clash"),
    ({"巳","亥"},"Snake-Pig Clash"),
]

def void_emptiness(day_stem: str, day_branch: str) -> List[str]:
    if day_stem not in STEMS or day_branch not in BRANCHES:
        return []
    s = STEMS.index(day_stem)
    b = BRANCHES.index(day_branch)
    v1 = (b - s + 10) % 12
    v2 = (v1 + 1) % 12
    return [BRANCHES[v1], BRANCHES[v2]]

def bazi_interactions(branches_by_pillar: Dict[str, str]) -> Dict[str, Any]:
    brs = list(branches_by_pillar.items())
    out = {"clashes": [], "harms": [], "destructions": [], "punishments": []}

    # clashes
    for i in range(len(brs)):
        for j in range(i+1, len(brs)):
            a = branches_by_pillar[brs[i][0]]
            b = branches_by_pillar[brs[j][0]]
            for pair, name in CLASHES:
                if {a,b} == pair:
                    out["clashes"].append({"p1": brs[i][0], "p2": brs[j][0], "type": name})

            for x,y in LIU_HAI:
                if {a,b} == {x,y}:
                    out["harms"].append({"p1": brs[i][0], "p2": brs[j][0], "type": f"{x}-{y} Harm"})
            for x,y in PO:
                if {a,b} == {x,y}:
                    out["destructions"].append({"p1": brs[i][0], "p2": brs[j][0], "type": f"{x}-{y} Destruction"})

    # punishments
    all_br = set(branches_by_pillar.values())
    for s in SAN_XING:
        if len(s) == 2:
            if set(s).issubset(all_br):
                out["punishments"].append({"type":"Zi-Mao Punishment","branches":list(s)})
        else:
            if set(s).issubset(all_br):
                out["punishments"].append({"type":"Three Penalties","branches":list(s)})

    return out

def dm_strength_and_useful_god(pillars: Dict[str, Any]) -> Dict[str, Any]:
    dm_stem = pillars["Day"]["stem"]
    dm_el = STEM_ELEMENT.get(dm_stem, "Unknown")
    month_branch = pillars["Month"]["branch"]
    season_el = BRANCH_ELEMENT.get(month_branch, "Unknown")

    score = 50.0
    # seasonal support
    if season_el == dm_el:
        score += 12
    if GEN_CYCLE.get(season_el) == dm_el:
        score += 8
    if GEN_CYCLE.get(dm_el) == season_el:
        score -= 6

    # roots: hidden stems containing dm stem element
    root_count = 0
    for p in pillars.values():
        br = p["branch"]
        hs = HIDDEN_STEMS.get(br, [])
        for h in hs:
            if STEM_ELEMENT.get(h) == dm_el:
                root_count += 1
    score += min(18, root_count * 6)

    # supporting vs draining elements in all stems/branches
    sup = 0
    drain = 0
    for p in pillars.values():
        sup += 1 if ten_god(dm_el, STEM_ELEMENT.get(p["stem"],"Unknown")) in ["Companion","Resource"] else 0
        drain += 1 if ten_god(dm_el, STEM_ELEMENT.get(p["stem"],"Unknown")) in ["Wealth","Output","Power"] else 0
        sup += 1 if ten_god(dm_el, BRANCH_ELEMENT.get(p["branch"],"Unknown")) in ["Companion","Resource"] else 0
        drain += 1 if ten_god(dm_el, BRANCH_ELEMENT.get(p["branch"],"Unknown")) in ["Wealth","Output","Power"] else 0

    score += (sup - drain) * 2.5
    score = max(0.0, min(100.0, score))

    tier = "BALANCED"
    if score < 40: tier = "WEAK"
    if score > 60: tier = "STRONG"

    # Useful God heuristic:
    # - if DM is strong -> favor draining/controlling elements (Wealth/Output/Power)
    # - if DM is weak -> favor supporting (Resource/Companion)
    if tier == "STRONG":
        # choose Wealth or Output depending on cycles
        useful = CTRL_CYCLE[dm_el]  # wealth element
        alt = GEN_CYCLE[dm_el]      # output element
        useful_god = useful
        secondary = alt
    elif tier == "WEAK":
        useful = GEN_CYCLE[dm_el]   # resource produces DM? careful: Resource is element that produces DM, which is prev in gen cycle.
        # producer:
        producer = None
        for e, nxt in GEN_CYCLE.items():
            if nxt == dm_el:
                producer = e
        useful_god = producer or "Unknown"
        secondary = dm_el
    else:
        # balanced -> pick element that smooths extremes: often Wealth or Output
        useful_god = CTRL_CYCLE[dm_el]
        secondary = GEN_CYCLE[dm_el]

    return {
        "day_master": {"stem": dm_stem, "element": dm_el},
        "score": round(score, 2),
        "tier": tier,
        "useful_god": useful_god,
        "secondary_support": secondary
    }

def sexagenary_step(stem: str, branch: str, step: int) -> Tuple[str,str]:
    si = STEMS.index(stem)
    bi = BRANCHES.index(branch)
    return STEMS[(si + step) % 10], BRANCHES[(bi + step) % 12]

def sun_lon_tropical(jd: float) -> float:
    import swisseph as swe
    result = swe.calc_ut(jd, swe.SUN, 0)
    # Handle both pyswisseph return formats:
    # v2.10+: (tuple_of_6, retflag)  — result[0] is a tuple
    # older:  flat tuple of 6 floats — result[0] is a float
    if isinstance(result[0], (list, tuple)):
        return float(result[0][0])
    return float(result[0])

def next_jieqi_days(birth_jd: float, forward: bool = True) -> float:
    """
    Bisection-based JieQi finder. Accurate to ~30 seconds.
    FIX: Replaces the old day-by-day scan that had wrap-around bugs and
    ±1 day imprecision (which corrupts Da Yun start age by months).
    """
    lon0 = sun_lon_tropical(birth_jd)

    # Target: next/prev multiple of 15°
    if forward:
        boundary = ((int(lon0 / 15.0) + 1) * 15.0) % 360.0
    else:
        n = int(lon0 / 15.0)
        boundary = (n * 15.0) % 360.0
        if abs(lon0 - boundary) < 0.01:   # already sitting on a boundary
            n -= 1
        boundary = (n * 15.0) % 360.0

    # Angular distance to boundary in the direction of travel (always positive)
    if forward:
        ang_to_boundary = (boundary - lon0) % 360.0
    else:
        ang_to_boundary = (lon0 - boundary) % 360.0

    # Estimate days (Sun moves 0.9856°/day)
    est_days = ang_to_boundary / 0.9856

    # f(jd) = how far the sun has traveled from lon0 toward boundary, minus that distance.
    # Negative = not crossed yet.  Zero = exact crossing.  Positive = past.
    def dist_past(jd: float) -> float:
        lon = sun_lon_tropical(jd)
        if forward:
            traveled = (lon - lon0) % 360.0
        else:
            traveled = (lon0 - lon) % 360.0
        return traveled - ang_to_boundary

    # Set initial bracket ±3 days around estimate
    if forward:
        lo_jd = birth_jd + max(0.1, est_days - 3.0)
        hi_jd = birth_jd + est_days + 3.0
    else:
        lo_jd = birth_jd - (est_days + 3.0)
        hi_jd = birth_jd - max(0.1, est_days - 3.0)

    # Expand bracket until we straddle the zero crossing
    for _ in range(15):
        if dist_past(lo_jd) < 0 < dist_past(hi_jd):
            break
        if dist_past(lo_jd) >= 0:
            lo_jd -= 2.0
        if dist_past(hi_jd) <= 0:
            hi_jd += 2.0
    else:
        return est_days   # fallback

    # Bisection to ~30-second precision
    for _ in range(55):
        mid = (lo_jd + hi_jd) / 2.0
        f_mid = dist_past(mid)
        if abs(f_mid) < 0.00005:
            return abs(mid - birth_jd)
        if f_mid < 0:
            lo_jd = mid
        else:
            hi_jd = mid
        if abs(hi_jd - lo_jd) < (0.5 / 1440.0):   # 30-second convergence
            break

    return abs((lo_jd + hi_jd) / 2.0 - birth_jd)

def da_yun_direction(year_stem: str, gender: str) -> bool:
    """
    forward=True means step forward through sexagenary.
    Rule (common): Yang year stem + male => forward; Yin year stem + male => backward; female opposite.
    """
    is_yang = STEMS.index(year_stem) % 2 == 0
    g = (gender or "male").strip().lower()
    male = g.startswith("m")
    if male:
        return is_yang
    else:
        return not is_yang

def build_da_yun(pillars: Dict[str, Any], birth_jd: float, gender: str) -> Dict[str, Any]:
    year_stem = pillars["Year"]["stem"]
    forward = da_yun_direction(year_stem, gender)
    days = next_jieqi_days(birth_jd, forward=forward)
    start_age = round(days / 3.0, 2)  # days/3 => years (common convention)
    # start from month pillar
    ms, mb = pillars["Month"]["stem"], pillars["Month"]["branch"]
    luck = []
    step = 1 if forward else -1
    cur_s, cur_b = ms, mb
    for i in range(8):
        cur_s, cur_b = sexagenary_step(cur_s, cur_b, step)
        luck.append({
            "index": i+1,
            "stem": cur_s,
            "branch": cur_b,
            "start_age": round(start_age + i*10, 2),
            "end_age": round(start_age + (i+1)*10, 2),
            "stem_element": STEM_ELEMENT.get(cur_s),
            "branch_element": BRANCH_ELEMENT.get(cur_b),
        })
    return {"direction": "forward" if forward else "backward", "start_age": start_age, "pillars": luck}

def shensha(pillars: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Full classical Shen Sha (20 stars).
    Source: San Ming Tong Hui, Di Tian Sui.
    Stars cover: relationships, travel, benefactors, intellect, danger, protection,
    spiritual gifts, marriage events, calamities, isolation.
    """
    year_br  = pillars["Year"]["branch"]
    month_br = pillars["Month"]["branch"]
    day_br   = pillars["Day"]["branch"]
    day_stem = pillars["Day"]["stem"]

    def group_of(branch: str):
        for g in PEACH_BLOSSOM.keys():
            if branch in g:
                return g
        return frozenset()

    yr_group  = group_of(year_br)
    day_group = group_of(day_br)
    all_br    = {v["branch"] for v in pillars.values()}

    out = []

    # ── Benefic Stars ───────────────────────────────────────────────────────
    # 桃花 Peach Blossom (day or year group)
    pb = PEACH_BLOSSOM.get(day_group) or PEACH_BLOSSOM.get(yr_group)
    if pb:
        out.append({"type": "Peach Blossom (桃花)", "branch": pb,
                    "nature": "benefic", "domain": "romance"})

    # 驿马 Traveling Horse
    th = TRAVEL_HORSE.get(day_group) or TRAVEL_HORSE.get(yr_group)
    if th:
        out.append({"type": "Traveling Horse (驿马)", "branch": th,
                    "nature": "benefic", "domain": "travel/career-change"})

    # 天乙贵人 TianYi Nobleman (x2)
    for b in TIANYI.get(day_stem, []):
        out.append({"type": "TianYi Nobleman (天乙贵人)", "branch": b,
                    "nature": "benefic", "domain": "benefactors"})

    # 文昌 Literary Star
    wc = WENCHANG.get(day_stem)
    if wc:
        out.append({"type": "Literary Star (文昌)", "branch": wc,
                    "nature": "benefic", "domain": "intellect/exams/writing"})

    # 天德 Heaven Virtue (protects from disasters in that month pillar)
    hv = HEAVEN_VIRTUE.get(month_br)
    if hv:
        out.append({"type": "Heaven Virtue (天德)", "stem_or_branch": hv,
                    "nature": "benefic", "domain": "protection-from-disasters"})

    # 月德 Moon Virtue
    mv = MOON_VIRTUE.get(month_br)
    if mv:
        out.append({"type": "Moon Virtue (月德)", "stem_or_branch": mv,
                    "nature": "benefic", "domain": "helpful-people"})

    # 红鸾 Red Luan (marriage/romance events keyed to year branch)
    rl = RED_LUAN.get(year_br)
    if rl:
        out.append({"type": "Red Luan (红鸾)", "branch": rl,
                    "nature": "benefic", "domain": "marriage-romance-events"})

    # 天喜 Sky Happiness (joyful events)
    sh = SKY_HAPPINESS.get(year_br)
    if sh:
        out.append({"type": "Sky Happiness (天喜)", "branch": sh,
                    "nature": "benefic", "domain": "joyful-events-births"})

    # 华盖 Canopy Star (spiritual gift / artistic isolation)
    cn = CANOPY.get(yr_group)
    if cn:
        out.append({"type": "Canopy Star (华盖)", "branch": cn,
                    "nature": "mixed", "domain": "spirituality-artistry-isolation"})

    # ── Malefic Stars ────────────────────────────────────────────────────────
    # 羊刃 Yang Blade
    yb = YANG_BLADE.get(day_stem)
    if yb:
        out.append({"type": "Yang Blade (羊刃)", "branch": yb,
                    "nature": "malefic", "domain": "aggression-injury-surgery"})

    # 三煞 Three Killings (year group → list of 3 branches)
    tk = THREE_KILLINGS.get(yr_group)
    if tk:
        for b in tk:
            out.append({"type": "Three Killings (三煞)", "branch": b,
                        "nature": "malefic", "domain": "major-calamity-danger"})

    # 劫煞 Robbery Sha
    rs = ROBBERY_SHA.get(yr_group)
    if rs:
        out.append({"type": "Robbery Sha (劫煞)", "branch": rs,
                    "nature": "malefic", "domain": "theft-financial-loss"})

    # 灾煞 Disaster Sha
    ds = DISASTER_SHA.get(yr_group)
    if ds:
        out.append({"type": "Disaster Sha (灾煞)", "branch": ds,
                    "nature": "malefic", "domain": "sickness-accidents"})

    # 咸池 Xian Chi / Salt Pool
    xc = XIAN_CHI.get(yr_group)
    if xc:
        out.append({"type": "Xian Chi Salt Pool (咸池)", "branch": xc,
                    "nature": "malefic", "domain": "sensuality-dissolution"})

    # ── Social Stars ─────────────────────────────────────────────────────────
    # 孤辰 Solitary God
    sol = SOLITARY.get(year_br)
    if sol:
        out.append({"type": "Solitary God (孤辰)", "branch": sol,
                    "nature": "challenging", "domain": "isolation-loneliness"})

    # 寡宿 Widow Star
    wid = WIDOW.get(year_br)
    if wid:
        out.append({"type": "Widow Star (寡宿)", "branch": wid,
                    "nature": "challenging", "domain": "emotional-isolation"})

    # ── Mark which stars are ACTIVATED (appear in the natal pillars) ─────────
    for star in out:
        branch = star.get("branch") or star.get("stem_or_branch", "")
        if branch:
            # Check if this branch appears in any of the 4 pillars
            activated = branch in all_br
            star["activated_in_chart"] = activated

    return out


def _compute_element_balance(pillars: Dict[str, Any]) -> Dict[str, int]:
    """Tally element counts from all pillar stems and branches."""
    counts: Dict[str, int] = {"Wood": 0, "Fire": 0, "Earth": 0, "Metal": 0, "Water": 0}
    for p in pillars.values():
        if isinstance(p, dict):
            se = p.get("stem_element")
            be = p.get("branch_element")
            if se and se in counts:
                counts[se] += 1
            if be and be in counts:
                counts[be] += 1
    return counts


def calculate_bazi(birth_dt_utc: datetime, time_known: bool, gender: str, birth_jd: float,
                   lon: float = 0.0) -> Dict[str, Any]:
    """
    Calculate Bazi (Four Pillars) chart.

    CRITICAL: Bazi is based on Local Mean Time, not UTC.
    A person born at 20:44 UTC+8 (Singapore, lon=103.82) must be calculated
    for 20:44+6h55m = solar local time, not UTC.

    lon: geographic longitude of birth (+E / -W). Used to derive LMT offset.
    """
    if Solar is None:
        raise ImportError("lunar_python not installed. pip install lunar-python")

    # ── Convert UTC → Local True Solar Time (LTST) ───────────────────────────
    # Step 1: LMT offset (longitude correction)
    # LMT offset = longitude / 15 hours (each 15° = 1 solar hour)
    lmt_offset_hours = lon / 15.0

    # Step 2: Equation of Time (EoT) correction
    # EoT = difference between apparent solar time and mean solar time.
    # Ranges from about -16 min to +14 min throughout the year.
    # Without this, births near JieQi boundaries (within ~16 min of the boundary)
    # can be assigned the wrong pillar — the most common Bazi accuracy failure.
    #
    # Algorithm: EoT = (Mean Sun longitude - Apparent Sun RA) × 4 min/degree
    # Uses Swiss Ephemeris for sub-minute precision.
    eot_hours = 0.0
    try:
        import swisseph as _swe
        jd_birth = _swe.julday(
            birth_dt_utc.year, birth_dt_utc.month, birth_dt_utc.day,
            birth_dt_utc.hour + birth_dt_utc.minute / 60.0 + birth_dt_utc.second / 3600.0
        )
        # Apparent Sun Right Ascension (degrees)
        _eq_result = _swe.calc_ut(jd_birth, _swe.SUN, _swe.FLG_EQUATORIAL)
        sun_ra = float(_eq_result[0][0] if isinstance(_eq_result[0], (list, tuple)) else _eq_result[0])
        # Mean Sun longitude (degrees, J2000 epoch)
        T = (jd_birth - 2451545.0) / 36525.0
        mean_lon = (280.46646 + 36000.76983 * T) % 360.0
        # EoT in degrees (positive = clock ahead of sun = sun arrives late)
        eot_deg = mean_lon - sun_ra
        if eot_deg > 180.0:   eot_deg -= 360.0
        if eot_deg < -180.0:  eot_deg += 360.0
        eot_hours = eot_deg / 15.0   # 15°/hour → hours
    except Exception:
        pass   # fall back to LMT-only if swisseph unavailable

    # LTST = UTC + LMT offset + Equation of Time
    birth_dt_lmt = birth_dt_utc + timedelta(hours=lmt_offset_hours + eot_hours)

    solar = Solar.fromYmdHms(
        birth_dt_lmt.year, birth_dt_lmt.month, birth_dt_lmt.day,
        birth_dt_lmt.hour, birth_dt_lmt.minute, 0
    )

    # Try EightChar API first, fallback to Lunar direct methods
    lunar = solar.getLunar()
    try:
        eight = lunar.getEightChar()
    except AttributeError:
        eight = None

    if eight is not None:
        raw = {
            "Year": {"stem": eight.getYearGan(), "branch": eight.getYearZhi()},
            "Month": {"stem": eight.getMonthGan(), "branch": eight.getMonthZhi()},
            "Day": {"stem": eight.getDayGan(), "branch": eight.getDayZhi()},
        }
        if time_known:
            raw["Hour"] = {"stem": eight.getTimeGan(), "branch": eight.getTimeZhi()}
    else:
        # Direct Lunar methods (works on all lunar_python versions)
        raw = {
            "Year": {"stem": lunar.getYearGan(), "branch": lunar.getYearZhi()},
            "Month": {"stem": lunar.getMonthGan(), "branch": lunar.getMonthZhi()},
            "Day": {"stem": lunar.getDayGan(), "branch": lunar.getDayZhi()},
        }
        if time_known:
            raw["Hour"] = {"stem": lunar.getTimeGan(), "branch": lunar.getTimeZhi()}

    voids = void_emptiness(raw["Day"]["stem"], raw["Day"]["branch"])
    # annotate pillars
    dm_el = STEM_ELEMENT.get(raw["Day"]["stem"], "Unknown")
    annotated = {}
    branch_only = {}
    for k, v in raw.items():
        s_el = STEM_ELEMENT.get(v["stem"], "Unknown")
        b_el = BRANCH_ELEMENT.get(v["branch"], "Unknown")
        branch_only[k] = v["branch"]
        annotated[k] = {
            "stem": v["stem"],
            "stem_element": s_el,
            "stem_10_god": ten_god(dm_el, s_el),
            "branch": v["branch"],
            "branch_element": b_el,
            "branch_10_god": ten_god(dm_el, b_el),
            "hidden_stems": HIDDEN_STEMS.get(v["branch"], []),
            "is_void": v["branch"] in voids,
            "qi_phase": qi_phase(raw["Day"]["stem"], v["branch"])
        }

    strength = dm_strength_and_useful_god(raw)
    luck = build_da_yun(raw, birth_jd, gender)
    inter = bazi_interactions(branch_only)
    ss = shensha(raw)

    # --- BAZI 5-YEAR LIU NIAN TIMELINE ---
    forecast_years = 5
    now = datetime.now(timezone.utc)
    liu_nian_timeline = []

    for y_offset in range(forecast_years):
        target_now = now + timedelta(days=365.25 * y_offset)
        solar_now = Solar.fromYmdHms(target_now.year, target_now.month, target_now.day, target_now.hour,
                                     target_now.minute, 0)
        lunar_now = solar_now.getLunar()
        try:
            eight_now = lunar_now.getEightChar()
            y_gan = eight_now.getYearGan()
            y_zhi = eight_now.getYearZhi()
        except AttributeError:
            y_gan = lunar_now.getYearGan()
            y_zhi = lunar_now.getYearZhi()

        liu_nian_timeline.append({
            "year": target_now.year,
            "stem": y_gan,
            "branch": y_zhi
        })

    # Assemble ten_gods summary dict for saju_expert and archon.
    # saju_expert reads natal['ten_gods'][pillar] = {'stem_god': ..., 'branch_god': ...}
    # archon._build_tier2 reads bazi_nat['ten_gods'] with the same schema.
    # The data already exists in each pillar as stem_10_god/branch_10_god — just reshape.
    ten_gods: dict = {}
    for pillar_name, pillar_data in annotated.items():
        if isinstance(pillar_data, dict):
            ten_gods[pillar_name] = {
                "stem_god":   pillar_data.get("stem_10_god",   "Unknown"),
                "branch_god": pillar_data.get("branch_10_god", "Unknown"),
                "stem":       pillar_data.get("stem",          "?"),
                "branch":     pillar_data.get("branch",        "?"),
            }

    return {
        "natal": {"pillars": annotated, "void_emptiness": voids, "shensha": ss, "interactions": inter,
                  "element_balance": _compute_element_balance(annotated),
                  "ten_gods": ten_gods},
        "strength": strength,
        "predictive": {"da_yun": luck, "liu_nian_timeline": liu_nian_timeline}
    }
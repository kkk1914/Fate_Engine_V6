"""Saju (Bazi) Engine."""
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

# -----------------------------
# Bazi (Saju) Helpers
# -----------------------------
try:
    from lunar_python import Solar, EightChar  # Add EightChar to import
except Exception as e:
    Solar = None
    EightChar = None  # Add this line

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

# Shen Sha (a few high-impact ones)
PEACH_BLOSSOM = {
    frozenset(["申","子","辰"]): "酉",
    frozenset(["亥","卯","未"]): "子",
    frozenset(["寅","午","戌"]): "卯",
    frozenset(["巳","酉","丑"]): "午"
}
TRAVEL_HORSE = {
    frozenset(["申","子","辰"]): "寅",
    frozenset(["亥","卯","未"]): "巳",
    frozenset(["寅","午","戌"]): "申",
    frozenset(["巳","酉","丑"]): "亥"
}
# Tian Yi Nobleman by Day Stem (common table)
TIANYI = {
    "甲":["丑","未"], "己":["丑","未"],
    "乙":["子","申"], "庚":["子","申"],
    "丙":["亥","酉"], "辛":["亥","酉"],
    "丁":["酉","亥"], "壬":["酉","亥"],
    "戊":["卯","巳"], "癸":["卯","巳"]
}

# Harms / Punishments / Destructions
LIU_HAI = [("子","未"),("丑","午"),("寅","巳"),("卯","辰"),("申","亥"),("酉","戌")]
PO = [("子","酉"),("丑","辰"),("寅","亥"),("卯","午"),("巳","申"),("未","戌")]
# Basic "punishments" incl 3-penalties
SAN_XING = [
    ("寅","巳","申"),
    ("丑","未","戌"),
    ("子","卯")  # zi-mao punishment
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
    pos, _ = swe.calc_ut(jd, swe.SUN, 0)
    return float(pos[0])

def next_jieqi_days(birth_jd: float, forward: bool = True) -> float:
    """
    Approx: find next (or prev) 15° solar longitude boundary (JieQi step).
    Used for Da Yun start age: days / 3.
    """
    lon0 = sun_lon_tropical(birth_jd)
    boundary = (math.floor(lon0 / 15.0) + (1 if forward else 0)) * 15.0
    boundary = boundary % 360
    # iterate day by day then refine
    step = 1 if forward else -1
    jd = birth_jd
    for _ in range(90):  # within 3 months window
        jd2 = jd + step
        lon = sun_lon_tropical(jd2)
        # detect crossing
        if forward:
            if (lon0 <= boundary <= lon) or (lon < lon0 and boundary >= lon0):  # wrap guard
                return abs(jd2 - birth_jd)
        else:
            if (lon <= boundary <= lon0) or (lon0 < lon and boundary <= lon0):
                return abs(jd2 - birth_jd)
        jd = jd2
        lon0 = lon
    # fallback
    return 30.0

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
    year_br = pillars["Year"]["branch"]
    day_br = pillars["Day"]["branch"]
    day_stem = pillars["Day"]["stem"]

    def group(branch: str) -> frozenset:
        for g in PEACH_BLOSSOM.keys():
            if branch in g:
                return g
        return frozenset()

    pb = PEACH_BLOSSOM.get(group(day_br)) or PEACH_BLOSSOM.get(group(year_br))
    th = TRAVEL_HORSE.get(group(day_br)) or TRAVEL_HORSE.get(group(year_br))

    out = []
    if pb:
        out.append({"type":"Peach Blossom","branch":pb})
    if th:
        out.append({"type":"Traveling Horse","branch":th})

    nobles = TIANYI.get(day_stem, [])
    for b in nobles:
        out.append({"type":"TianYi Nobleman","branch":b})

    return out


def calculate_bazi(birth_dt_utc: datetime, time_known: bool, gender: str, birth_jd: float,
                   lon: float = 0.0) -> Dict[str, Any]:
    """
    Calculate Bazi (Four Pillars) chart.

    CRITICAL: Bazi is based on Local Mean Time, not UTC.
    A person born at 20:44 UTC+8 (Singapore, lon=103.82) must be calculated
    for 20:44+6h55m = solar local time, not UTC.

    lon: geographic longitude of birth (+E / -W). Used to derive LMT offset.
    """
    if Solar is None or EightChar is None:
        raise ImportError("lunar_python not installed. pip install lunar-python")

    # ── Convert UTC → Local Mean Time (LMT) ──────────────────────────────────
    # LMT offset = longitude / 15 hours (each 15° = 1 solar hour)
    # This is the astronomically correct base before True Solar Time corrections.
    # For premium accuracy one would further apply the Equation of Time (~±16 min),
    # but LMT correction is the dominant fix (up to ±12 hours for extreme longitudes).
    lmt_offset_hours = lon / 15.0
    birth_dt_lmt = birth_dt_utc + timedelta(hours=lmt_offset_hours)

    solar = Solar.fromYmdHms(
        birth_dt_lmt.year, birth_dt_lmt.month, birth_dt_lmt.day,
        birth_dt_lmt.hour, birth_dt_lmt.minute, 0
    )

    # Try both APIs for compatibility
    try:
        eight = solar.getLunar().getEightChar()
    except AttributeError:
        # Fallback to direct EightChar instantiation
        eight = EightChar(solar.getLunar())

    raw = {
        "Year": {"stem": eight.getYearGan(), "branch": eight.getYearZhi()},
        "Month": {"stem": eight.getMonthGan(), "branch": eight.getMonthZhi()},
        "Day": {"stem": eight.getDayGan(), "branch": eight.getDayZhi()},
    }
    if time_known:
        raw["Hour"] = {"stem": eight.getTimeGan(), "branch": eight.getTimeZhi()}

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
        eight_now = solar_now.getLunar().getEightChar()

        liu_nian_timeline.append({
            "year": target_now.year,
            "stem": eight_now.getYearGan(),
            "branch": eight_now.getYearZhi()
        })

    return {
        "natal": {"pillars": annotated, "void_emptiness": voids, "shensha": ss, "interactions": inter},
        "strength": strength,
        "predictive": {"da_yun": luck, "liu_nian_timeline": liu_nian_timeline}
    }
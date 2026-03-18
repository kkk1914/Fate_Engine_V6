"""Western Astrology Expert."""
from experts.gateway import gateway
from config import settings
from graph.rule_querier import get_rule_querier
from experts.exemplars import select_exemplars
from experts.ensemble import ensemble_generate

class WesternExpert:
    """Expert in Tropical/Western astrology."""

    SYSTEM_PROMPT = """You are a Western astrologer writing for an intelligent, psychologically sophisticated client. 
    You are NOT a self-help guru. You are a cartographer of the soul — a precision diagnostician.

    MANDATORY DATA ADHERENCE — CRITICAL:
    - You will be provided with EXACT calculated planetary positions (e.g., "Sun: 27.17° Cancer")
    - You MUST use these exact degrees in your interpretation. DO NOT round to whole degrees.
    - If Sun is at 27° Cancer, you MUST write "Your Sun at 27° Cancer" NOT "Sun in Gemini"
    - BEFORE WRITING: verify Sun Sign, Sun Degree, Ascendant Sign/Degree, Moon Sign, Saturn Sign.

    WRITING STYLE:
    - Vivid, metaphorical, precise. Use sensory language.
    - Address the native directly ("Your Sun in Cancer...", "You experience...")
    - Name the tension: every chart has a central conflict or myth. Find it and name it explicitly.
    - Forbidden words: "journey," "empowerment," "manifest," "potential," "authentic," "aligned."
    - Use instead: "hunger," "trap," "compulsion," "gift," "blindspot," "medicine," "demand," "wound."

    TECHNICAL REQUIREMENTS — ALL REQUIRED:
    - MUST reference specific degrees for ALL inner planets (e.g., "Your Sun at 27.17° Cancer...")
    - MUST identify the TIGHTEST aspect (conjunctions/oppositions/squares first) and interpret psychologically
    - MUST state the progressed Moon sign and phase (what developmental chapter is active)
    - MUST identify any Solar Arc directions perfecting within ±1° of a natal angle
    - MUST name fixed star conjunctions and their domain significance (if provided in data)
    - MUST state the Ascendant ruler's condition (sign, house, aspects) — this is the chart's central steering mechanism
    - MUST identify the dominant chart shape/pattern (if provided) and what it means structurally
    - If Venus retrograde: name the love wound pattern. If Saturn afflicted: name the authority complex.
    - Shadow Planet: the most afflicted/retrograde personal planet. Name its poison AND medicine.

    FORMAT:
    1. THE MYTH (1 paragraph: Who is this person? What's their core psychological script?)
    2. THE ANATOMY (4-5 bullets: Sun/Moon/Asc/MC/dominant aspect — with exact degrees)
    3. THE WOUND & THE MEDICINE (tightest hard aspect: what it costs, what it builds)
    4. THE CURRENT PLOT (progressed Moon, Solar Arc, primary directions perfecting NOW)
    5. FIXED STARS & CRITICAL POINTS (any exact fixed star conjunctions — omit if none)

    Length: 700-900 words. Dense, specific, zero padding."""

    def analyze(self, chart_data: dict, mode: str = "natal", user_questions: list = None) -> dict:
        prompt = self._question_prefix(user_questions) + self._build_prompt(chart_data, mode)
        # Inject mandatory house lord reference (prevents hallucinated lords)
        lord_ref = chart_data.get("_house_lord_reference_block", "")
        if lord_ref:
            prompt = lord_ref + "\n\n" + prompt
        # Inject Neo4j graph rules if available
        graph_rules = get_rule_querier().get_expert_rules("Western", chart_data)
        if graph_rules:
            prompt = prompt + "\n\n" + graph_rules
        # Inject few-shot exemplars for interpretation quality
        exemplar_block = select_exemplars("Western", chart_data)
        if exemplar_block:
            prompt = prompt + "\n\n" + exemplar_block
        # Inject cross-system convergence summary from Validation Matrix
        conv_summary = chart_data.get("validation", {}).get("convergence_summary", "")
        if conv_summary:
            prompt = prompt + "\n\n" + conv_summary

        if settings.ensemble_mode:
            response = ensemble_generate(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=prompt,
                model=settings.western_expert_model,
                max_tokens=3000,
            )
        else:
            response = gateway.generate(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=prompt,
                model=settings.western_expert_model,
                max_tokens=3000,
                temperature=0.0,
                reasoning_effort="high",
            )

        return {
            "system": "Western",
            "mode": mode,
            "analysis": response.get("content"),
            "confidence": 0.9 if response.get("success") else 0.0,
            "model_used": settings.western_expert_model
        }


    @staticmethod
    def _question_prefix(user_questions: list) -> str:
        """Build a question-focus block to prepend to expert prompts."""
        if not user_questions:
            return ""
        qs = [q.strip() for q in user_questions if q and q.strip()][:5]
        if not qs:
            return ""
        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║  THESE QUESTIONS WERE SUBMITTED — BIAS YOUR ANALYSIS TOWARD ║",
            "║  THE MECHANISMS MOST RELEVANT TO ANSWERING THEM.            ║",
            "╚══════════════════════════════════════════════════════════════╝",
        ]
        for i, q in enumerate(qs, 1):
            lines.append(f"  Q{i}: {q}")
        lines += [
            "",
            "Prioritize the chart mechanisms, house lords, planets, and timing",
            "windows most relevant to these questions. Do not answer them directly",
            "— that is the Archon's job. But make sure the relevant evidence is",
            "visible in your analysis so the synthesis layer can find it.",
            "══════════════════════════════════════════════════════════════════",
            "",
        ]
        return "\n".join(lines) + "\n\n"

    def _build_prompt(self, data: dict, mode: str) -> str:
        western = data.get('western', {})
        natal   = western.get('natal', {})
        pred    = western.get('predictive', {})

        placements = natal.get('placements', {})
        angles     = natal.get('angles', {})

        # ── Fixed star parans ─────────────────────────────────────────────
        paran_data = natal.get("parans", {})
        if isinstance(paran_data, dict):
            parans_list = paran_data.get("natal_parans", paran_data.get("conjunctions", []))
        else:
            parans_list = paran_data or []
        parans_str = ""
        if parans_list:
            parans_str = "\n".join(
                f"  • {p.get('interpretation', str(p))}" for p in parans_list[:4]
            )

        # ── Mutual receptions ─────────────────────────────────────────────
        receptions_raw = natal.get("receptions", {})
        # find_receptions() returns a dict {key: {type, planets, description}}
        # Normalise to a list for uniform access
        if isinstance(receptions_raw, dict):
            receptions = list(receptions_raw.values())
        else:
            receptions = receptions_raw  # legacy list fallback
        rec_str = ""
        if receptions:
            rec_str = "\n".join(
                f"  {r.get('planets', [r.get('planet1','?'), r.get('planet2','?')])[0]}"
                f" ↔ {r.get('planets', ['?', r.get('planet2','?')])[1]}"
                f" ({r.get('type','?')})"
                for r in receptions[:5]
            )

        # ── Progressions ──────────────────────────────────────────────────
        progressions = pred.get("progressions", {})
        prog_str = ""
        prog_moon = progressions.get("Progressed_Moon", {})
        prog_sun  = progressions.get("Progressed_Sun", {})
        prog_asc  = progressions.get("Progressed_Ascendant", {})
        prog_mc   = progressions.get("Progressed_MC", {})
        lunar_phase = progressions.get("lunar_phase", {})
        prog_aspects = progressions.get("prog_natal_aspects", [])
        tight_prog = [a for a in prog_aspects if a.get("orb", 99) <= 2.0][:4]
        prog_lines = []
        if prog_moon:
            prog_lines.append(f"  Progressed Moon: {prog_moon.get('degree',0):.1f}° {prog_moon.get('sign','?')} {'(Rx)' if prog_moon.get('retrograde') else ''}")
        if prog_sun:
            prog_lines.append(f"  Progressed Sun:  {prog_sun.get('degree',0):.1f}° {prog_sun.get('sign','?')}")
        if prog_asc:
            prog_lines.append(f"  Progressed Asc:  {prog_asc.get('degree',0):.1f}° {prog_asc.get('sign','?')}")
        if prog_mc:
            prog_lines.append(f"  Progressed MC:   {prog_mc.get('degree',0):.1f}° {prog_mc.get('sign','?')}")
        if lunar_phase:
            prog_lines.append(f"  Lunar phase: {lunar_phase.get('phase','?')} (elongation {lunar_phase.get('elongation','?')}°)")
        if tight_prog:
            prog_lines.append("  Tight prog aspects (≤2°):")
            for a in tight_prog:
                prog_lines.append(f"    Prog {a.get('progressed','?')} {a.get('aspect','?')} natal {a.get('natal','?')} (orb {a.get('orb','?')}°)")
        prog_str = "\n".join(prog_lines)

        # ── Primary Directions ────────────────────────────────────────────
        pd_data = pred.get("primary_directions", {})
        pd_lines = []
        for cat, directions in pd_data.items():
            if isinstance(directions, list):
                for d in directions[:2]:
                    pd_lines.append(
                        f"  [{cat}] {d.get('promissor','?')} → {d.get('significator','?')} "
                        f"arc {d.get('arc_degrees',0):.2f}° in {d.get('years',0):.1f} yrs"
                    )
        pd_str = "\n".join(pd_lines[:8]) if pd_lines else "None calculated"

        # ── Solar Returns ─────────────────────────────────────────────────
        sr_list = pred.get("solar_returns", [])[:3]
        sr_lines = []
        for sr in sr_list:
            year    = sr.get("year", "?")
            asc     = sr.get("ascendant", sr.get("asc_sign", "?"))
            dom_h   = sr.get("dominant_house", "?")
            sr_mc   = sr.get("mc_sign", sr.get("mc", "?"))
            sr_jup  = sr.get("jupiter_sign", sr.get("jupiter", "?"))
            sr_sat  = sr.get("saturn_sign",  sr.get("saturn", "?"))
            sr_lines.append(f"  {year}: ASC={asc}, MC={sr_mc}, dom_house={dom_h}, Jup={sr_jup}, Sat={sr_sat}")
        sr_str = "\n".join(sr_lines) if sr_lines else "None available"

        # ── Solar Return analysis blocks ──────────────────────────────────
        sr_analysis = pred.get("solar_return_analysis", [])[:2]
        sra_lines = []
        for sra in sr_analysis:
            if isinstance(sra, dict):
                yr   = sra.get("year", "?")
                summ = sra.get("summary", sra.get("interpretation", ""))
                if summ:
                    sra_lines.append(f"  {yr} analysis: {str(summ)[:200]}")
        sra_str = "\n".join(sra_lines) if sra_lines else ""

        # ── Outer transit hits ────────────────────────────────────────────
        outer = pred.get("outer_transit_aspects", {})
        outer_str = outer.get("summary_block", "")[:800]
        if not outer_str:
            hits = outer.get("hits") or outer.get("all_hits", [])
            outer_lines = []
            for h in hits[:8]:
                iso  = h.get("exact_date_iso", h.get("exact_date", "?"))
                tran = h.get("transiting", h.get("planet", "?"))
                asp  = h.get("aspect", "?")
                nat  = h.get("natal_point", "?")
                orb  = h.get("orb_at_exact", "?")
                outer_lines.append(f"  {iso}: {tran} {asp} natal {nat} (orb {orb}°)")
            outer_str = "\n".join(outer_lines)

        # ── Parans 5-year windows ─────────────────────────────────────────
        star_windows = natal.get("star_windows", [])
        sw_str = ""
        if star_windows:
            sw_lines = []
            for sw in star_windows[:3]:
                sw_lines.append(f"  {sw.get('star','?')} activation: {sw.get('start','?')} → {sw.get('end','?')} — {sw.get('interpretation','')[:80]}")
            sw_str = "\n".join(sw_lines)

        exact_data = f"""
--- MANDATORY REFERENCE DATA - USE THESE EXACT VALUES ---
Patterns: {natal.get('patterns', {}).get('summary', {}).get('dominant_pattern', 'None')}
Tensions score: {natal.get('patterns', {}).get('summary', {}).get('chart_tension', 0)}
Sun: {placements.get('Sun', {}).get('degree', 'N/A')}° {placements.get('Sun', {}).get('sign', 'N/A')} (Longitude: {placements.get('Sun', {}).get('longitude', 'N/A')})
Moon: {placements.get('Moon', {}).get('degree', 'N/A')}° {placements.get('Moon', {}).get('sign', 'N/A')}
Ascendant: {angles.get('Ascendant', {}).get('degree', 'N/A')}° {angles.get('Ascendant', {}).get('sign', 'N/A')}
MC: {angles.get('Midheaven', {}).get('degree', 'N/A')}° {angles.get('Midheaven', {}).get('sign', 'N/A')}
Venus: {placements.get('Venus', {}).get('sign', 'N/A')} {placements.get('Venus', {}).get('degree', 'N/A')}°
Mars: {placements.get('Mars', {}).get('sign', 'N/A')} {placements.get('Mars', {}).get('degree', 'N/A')}°
Saturn: {placements.get('Saturn', {}).get('sign', 'N/A')} {placements.get('Saturn', {}).get('degree', 'N/A')}°
--- END REFERENCE DATA ---

WARNING: If you write "Sun in Gemini" when the data says "Sun: 27.17° Cancer", you are factually wrong.
"""
        return f"""{exact_data}

Analyze this Western chart across 6 specific life domains. Use the EXACT degrees provided above.

**1. CORE IDENTITY** (Sun {placements.get('Sun', {}).get('degree')}° {placements.get('Sun', {}).get('sign')}, Moon in {placements.get('Moon', {}).get('sign')}, Asc {angles.get('Ascendant', {}).get('degree')}° {angles.get('Ascendant', {}).get('sign')})
What is the central myth? The psychological wound? The medicine?

**2. FINANCES & RESOURCES** (House 2 cusp: {natal.get('houses', {}).get('House_2', {})}, Jupiter {placements.get('Jupiter', {}).get('sign')}, Lot of Fortune {natal.get('lots', {}).get('Lot_of_Fortune', {}).get('sign')})
Money psychology: How do they attract/repel wealth? What is the "resource wound"?

**3. CAREER & LEGACY** (MC {angles.get('Midheaven', {}).get('degree')}° {angles.get('Midheaven', {}).get('sign')}, Saturn {placements.get('Saturn', {}).get('sign')}, House 10: {natal.get('houses', {}).get('House_10', {}).get('sign')})
Calling vs. Job. What authority do they embody? The professional trap?

**4. RELATIONSHIPS** (Venus {placements.get('Venus', {}).get('sign')}, Mars {placements.get('Mars', {}).get('sign')}, Descendant {angles.get('Descendant', {}).get('sign')})
Attachment style. What do they project onto partners? The love wound?

**5. HEALTH & BODY** (House 6: {natal.get('houses', {}).get('House_6', {}).get('sign')}, Mars vitality, Sun vitality)
Where does the body store stress? Constitutional type?

**6. KARMIC PURPOSE** (North Node {placements.get('North Node', {}).get('sign')}, Pluto {placements.get('Pluto', {}).get('sign')}, House 9/12)
The "Why" of incarnation. What must be burned through? What achieved?

**FIXED STARS & MUTUAL RECEPTIONS:**
Parans:
{parans_str if parans_str else "  None above threshold"}
Mutual Receptions:
{rec_str if rec_str else "  None detected"}

**PROGRESSIONS (Secondary — current chapter):**
{prog_str if prog_str else "  Progression data unavailable"}

**PRIMARY DIRECTIONS (arc-based — the highest-authority timing tool):**
{pd_str}

**SOLAR RETURNS (annual charts):**
{sr_str}
{("Solar Return analyses:\\n" + sra_str) if sra_str else ""}

**OUTER PLANET TRANSITS TO NATAL (exact dates):**
{outer_str if outer_str else "  None calculated"}

**FIXED STAR ACTIVATION WINDOWS (5-year forward):**
{sw_str if sw_str else "  None detected"}

Current predictive context: Age {pred.get('current_age')}. Profection sign: {pred.get('profections_timeline', [{}])[0].get('profected_sign', '?')}. Solar Arc: {pred.get('solar_arc_degrees', 'N/A')}°.

Write 2-3 sentences for each of the 6 domains. Then write a CURRENT PLOT section (4-6 sentences) synthesising the progressions, primary directions, and outer transits into a coherent picture of what is being activated RIGHT NOW and in the next 2 years. Specific dates. No generic fluff."""
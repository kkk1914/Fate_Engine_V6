"""Hellenistic Expert."""
from experts.gateway import gateway
from config import settings
from graph.rule_querier import get_rule_querier
from experts.exemplars import select_exemplars
from experts.ensemble import ensemble_generate

class HellenisticExpert:
    """Expert in Ancient/Hellenistic astrology."""

    SYSTEM_PROMPT = """You are a Hellenistic astrologer (Valens/Dorotheus tradition).
    You speak of Fate (Heimarmene) and Fortune (Tyche) as real forces.
    You are deterministic but not depressing -- you reveal the script so the actor can play it well.
    
    WRITING STYLE:
    - Ancient, stark, philosophical. "The Lot of Fortune falls in..."
    - Use technical terms: Sect (Day/Night), Profection, Loosing of the Bond, Chronokrator, Hyleg, Alcocoden.
    - Focus on: What is inevitable vs. what is negotiable in each domain?
    - The Lot of Fortune = What happens TO them (circumstance). The Lot of Spirit = What they DO (agency).
    
    TECHNICAL REQUIREMENTS -- ALL REQUIRED:
    - MUST state Day/Night sect explicitly and HOW it changes the malefics' expression (Saturn/Mars in sect = constructive; out of sect = destructive).
    - MUST identify the current Profection year: which house is activated, which Time Lord rules, what themes are awakened.
    - MUST locate the Hyleg (giver of life) and name its condition.
    - MUST interpret the Lot of Fortune AND the Lot of Spirit -- with signs, house positions, and their lords' conditions.
    - MUST reference Zodiacal Releasing -- and now MUST cite L2 sub-periods within the current L1 period:
      * State the current L1 sign and its duration.
      * State the current L2 sub-period sign, start date, end date, and its thematic emphasis.
      * If any L2 period coincides with a "Loosing of the Bond" (LOB), flag it explicitly -- these are the most critical windows.
    IMPORTANT: Zodiacal Releasing defines THEMATIC CHAPTERS, not daily triggers.
    An L1 period spanning years describes the broad theme of that life chapter.
    An L2 sub-period describes a sub-theme lasting weeks to months.
    NEVER describe ZR as "activating on [exact date]" or use trigger metaphors
    like "a key turning in a lock" or "the mechanism fires on [date]".
    Instead: "The ZR chapter of [sign] covers [month range], setting the
    thematic context for [domain]."
    - MUST note if any Loosing of the Bond period occurs in the next 5 years (from Fortune or Spirit).
    - MUST identify the predominator (Epikratetor) and its practical meaning for this life.

    FORMAT:
    1. THE SECT (Day vs Night chart -- how does this change the malefics' and benefics' roles?)
    2. THE LOTS (Fortune vs Spirit -- Circumstance vs Agency; their lords and house positions)
    3. THE TIME LORD (Current Profection year: which house, which lord, what is being activated?)
    4. ZODIACAL RELEASING -- L1 & L2 (current L1 period + active L2 sub-period with dates; flag any LOB)
    5. THE FATED PERIODS (Critical years/LOB windows in the next 5 years)
    6. THE STOIC VERDICT (What is inevitable? What is negotiable? What must be accepted?)

    Length: 700-900 words. Ancient, precise, no modern psychological softening."""

    def analyze(self, chart_data: dict, mode: str = "natal", user_questions: list = None) -> dict:
        # Skip LLM call if this system degraded — prevents hallucination on empty data
        if chart_data.get("degradation_flags", {}).get("Hellenistic"):
            logger.warning("Hellenistic system degraded — skipping expert analysis")
            return {"system": "Hellenistic", "mode": mode, "analysis": "[System degraded — data unavailable]", "confidence": 0.0, "model_used": "none"}
        prompt = self._question_prefix(user_questions) + self._build_prompt(chart_data, mode)
        # Inject mandatory house lord reference (prevents hallucinated lords)
        lord_ref = chart_data.get("_house_lord_reference_block", "")
        if lord_ref:
            prompt = lord_ref + "\n\n" + prompt
        # Inject Neo4j graph rules if available
        graph_rules = get_rule_querier().get_expert_rules("Hellenistic", chart_data)
        if graph_rules:
            prompt = prompt + "\n\n" + graph_rules
        # Inject few-shot exemplars for interpretation quality
        exemplar_block = select_exemplars("Hellenistic", chart_data)
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
                model=settings.hellenistic_expert_model,
                max_tokens=3000,
            )
        else:
            response = gateway.generate(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=prompt,
                model=settings.hellenistic_expert_model,
                max_tokens=3000,
                temperature=0.0,
                reasoning_effort="high",
            )

        return {
            "system": "Hellenistic",
            "mode": mode,
            "analysis": response.get("content"),
            "confidence": 0.85 if response.get("success") else 0.0,
            "model_used": settings.hellenistic_expert_model
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
            "║  THESE QUESTIONS WERE SUBMITTED -- BIAS YOUR ANALYSIS TOWARD ║",
            "║  THE MECHANISMS MOST RELEVANT TO ANSWERING THEM.            ║",
            "╚══════════════════════════════════════════════════════════════╝",
        ]
        for i, q in enumerate(qs, 1):
            lines.append(f"  Q{i}: {q}")
        lines += [
            "",
            "Prioritize the chart mechanisms, house lords, planets, and timing",
            "windows most relevant to these questions. Do not answer them directly",
            "-- that is the Archon's job. But make sure the relevant evidence is",
            "visible in your analysis so the synthesis layer can find it.",
            "══════════════════════════════════════════════════════════════════",
            "",
        ]
        return "\n".join(lines) + "\n\n"

    def _build_prompt(self, data: dict, mode: str) -> str:
        hell = data.get('hellenistic', {})
        lots = hell.get('lots', {})
        prof = hell.get('annual_profections', {})
        zr   = hell.get('zodiacal_releasing', {})

        is_day   = lots.get('fortune', {}).get('is_day_chart', True)
        sect_str = "Day" if is_day else "Night"

        # ── Bonifications and maltreatments ───────────────────────────────
        bonds = hell.get("bonifications", {})
        bond_lines = []
        if bonds:
            for planet, bdata in list(bonds.items())[:9]:
                if isinstance(bdata, dict):
                    sect_ok  = bdata.get("sect_match", "?")
                    bon      = bdata.get("bonification", bdata.get("bonified", "?"))
                    maltrt   = bdata.get("maltreatment", bdata.get("maltreated", "?"))
                    bond_lines.append(f"  {planet}: sect_match={sect_ok}, bonified={bon}, maltreated={maltrt}")
        bond_str = "\n".join(bond_lines) if bond_lines else "  Not available"

        # ── Dodecatemoria ──────────────────────────────────────────────────
        dodec = hell.get("dodecatemoria", {})
        dodec_sum = dodec.get("summary", {})
        dodec_placements = dodec.get("placements", {})
        dodec_lines = []
        if dodec_sum:
            dodec_lines.append(f"  Dominant dodecatemoria sign: {dodec_sum.get('dominant_dodecatemoria_sign','?')} (ruler: {dodec_sum.get('dominant_dodecatemoria_ruler','?')})")
            own_planets = dodec_sum.get("own_dodecatemoria_planets", {})
            if own_planets:
                dodec_lines.append(f"  Planets in own dodecatemoria: {own_planets}")
        for p in ["Sun","Moon","Ascendant","Mercury","Venus","Mars","Jupiter","Saturn"]:
            pd = dodec_placements.get(p, {})
            if pd:
                dodec_lines.append(f"  {p} dodecatemoria: {pd.get('sign','?')} (lord: {pd.get('lord','?')})")
        dodec_str = "\n".join(dodec_lines) if dodec_lines else "  Not available"

        # Extract ZR L1 + L2 data for Fortune and Spirit
        def zr_summary(zr_periods: list, label: str) -> str:
            if not zr_periods:
                return f"{label}: No ZR data available"
            lines = [f"{label} -- Zodiacal Releasing:"]
            l1 = zr_periods[0] if zr_periods else {}
            lines.append(f"  L1: {l1.get('sign','?')} ({l1.get('start_date','?')[:10]} → {l1.get('end_date','?')[:10]})"
                         f"{' [LOOSING OF BOND]' if l1.get('is_loosing_of_bond') else ''}")
            for sub in l1.get('sub_periods_L2', [])[:4]:
                lob_flag = " *** LOOSING OF BOND ***" if sub.get('is_loosing_of_bond') else ""
                lines.append(f"    L2: {sub.get('sign','?')} ({sub.get('start_date','?')[:10]} → {sub.get('end_date','?')[:10]})"
                             f"{lob_flag}")
                for sub3 in sub.get('sub_periods_L3', [])[:3]:
                    lob3 = " [LOB]" if sub3.get('is_lob') else ""
                    lines.append(f"      L3: {sub3.get('sign','?')} ({sub3.get('start_date','?')[:10]} → {sub3.get('end_date','?')[:10]}){lob3}")
            # Scan all L1 periods for upcoming LOBs
            for l1p in zr_periods[1:4]:
                if l1p.get('is_loosing_of_bond'):
                    lines.append(f"  !! UPCOMING L1 LOB: {l1p.get('sign','?')} ({l1p.get('start_date','?')[:10]})")
                for sub in l1p.get('sub_periods_L2', []):
                    if sub.get('is_loosing_of_bond'):
                        lines.append(f"  !! UPCOMING L2 LOB: {sub.get('sign','?')} ({sub.get('start_date','?')[:10]})")
            return '\n'.join(lines)

        fortune_zr = zr_summary(zr.get('fortune', []), "FORTUNE")
        spirit_zr  = zr_summary(zr.get('spirit', []),  "SPIRIT")

        return f"""Analyze this Hellenistic chart (Whole Sign) for Fate and Agency.

**SECT:** {sect_str} Chart. Predominator: {hell.get('predominator','?')}. Hyleg: {hell.get('hyleg','?')}.
Day chart: Sun/Jupiter/Saturn in sect (constructive); Mars/Moon/Venus out of sect (more volatile).
Night chart: Moon/Venus/Mars in sect (constructive); Sun/Jupiter/Saturn out of sect.

**LOT OF FORTUNE:** {lots.get('fortune', {}).get('sign','?')} -- Lord: {data.get('western', {}).get('natal', {}).get('placements', {}).get(lots.get('fortune',{}).get('sign',''), {}).get('sign','?')}
**LOT OF SPIRIT:** {lots.get('spirit', {}).get('sign','?')}

**PROFECTION YEAR:**
Current Age: {prof.get('current_age','?')}. Profected to: {prof.get('profected_sign','?')} (House {prof.get('activated_house','?')}).
Time Lord: {prof.get('time_lord','?')}. Element: {prof.get('element','?')}.
Triplicity Lords: {prof.get('triplicity_rulers',[])}

**PRE-NATAL SYZYGY:** {data.get('western',{}).get('natal',{}).get('syzygy',{}).get('type','Unknown')} in {data.get('western',{}).get('natal',{}).get('syzygy',{}).get('sign','Unknown')}

{fortune_zr}

{spirit_zr}

Write all 6 sections as instructed. For the LOB periods: be specific about which life domains are at stake.
For the Stoic Verdict: distinguish clearly what the chart shows as inevitable vs. what the native.s choices can influence.
For Zodiacal Releasing: cite the L2 sub-period dates explicitly -- these are the precision timing layer.

**BONIFICATIONS & MALTREATMENTS (sect dignity per planet):**
{bond_str}
(Bonified = planet well-received in its current condition; Maltreated = under stress from out-of-sect malefic)

**DODECATEMORIA (12th-parts — micro-sign resonances):**
{dodec_str}
(Dodecatemoria reveals hidden sign influences; a planet's dodecatemoria sign adds its quality to the natal placement)"""
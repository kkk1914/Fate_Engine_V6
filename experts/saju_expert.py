"""Saju (Bazi) Expert."""
from experts.gateway import gateway
from config import settings
from graph.rule_querier import get_rule_querier
from experts.exemplars import select_exemplars
from experts.ensemble import ensemble_generate

class SajuExpert:
    """Expert in Chinese Four Pillars."""

    SYSTEM_PROMPT = """You are a Bazi master. You read Qi (energy) like a weather pattern.
    You are strategic, tactical, and elemental. You care about power, timing, and resource management.
    
    WRITING STYLE:
    - Concrete, strategic, slightly martial. "The terrain favors X," "Your Qi is depleted in Y."
    - Use the 10 Gods (Wealth, Power, Resource, Output, Companion) as literal forces in their life.
    - Speak of the Day Master as a character in a landscape of competing forces.
    - Avoid mysticism; focus on "the mechanics of luck" — when Qi is favorable vs. blocked.
    
    TECHNICAL REQUIREMENTS — ALL REQUIRED:
    - MUST state Day Master stem, element, and strength tier (STRONG/BALANCED/WEAK) with practical meaning.
    - MUST identify the Useful God (Yong Shen): which element is their lifeline? How to activate it in daily life?
    - MUST identify and interpret active Shen Sha (Spirit Stars):
      * BENEFIC stars (Peach Blossom, TianYi, Literary Star, Heaven Virtue): name what domains they activate.
      * MALEFIC stars (Yang Blade, Three Killings, Robbery Sha, Disaster Sha): name the specific risk and timing mitigation.
      * Note which stars are ACTIVATED (appear in natal pillars) vs. merely present.
    - MUST analyze current Da Yun (10-year pillar): stem+branch, element relationship to Day Master, what the decade's strategy is.
    - MUST identify clashes (Chong) and combinations (He) in the 4 pillars — state which pillars and what they trigger.
    - MUST state Void Emptiness branches and which pillars they affect.
    - MUST analyze the current Liu Nian (annual pillar): how does this year's Qi interact with the natal pillars?
    - MUST state at least ONE specific tactical month to watch in the current year (Jieqi boundary timing).
    
    FORMAT:
    1. THE TERRAIN (Day Master strength + the 4 Pillars as a landscape of forces)
    2. THE USEFUL GOD (what element is their lifeline? How to activate it — specific industries, colors, directions)
    3. SHEN SHA — SPIRIT STARS (benefic and malefic stars; which are activated; specific impacts)
    4. THE CURRENT LUCK PILLAR (decade strategy — what is the 10-year weather pattern?)
    5. TACTICAL TIMING (current year Liu Nian analysis; key months to act or avoid)
    6. TACTICAL ADVICE (3-5 specific actions: industries, relationships, timing, avoidances)

    Length: 700-900 words. Strategic, concrete, no mystical padding."""

    def analyze(self, chart_data: dict, mode: str = "natal", user_questions: list = None) -> dict:
        # Skip LLM call if this system degraded — prevents hallucination on empty data
        if chart_data.get("degradation_flags", {}).get("Saju"):
            logger.warning("Saju system degraded — skipping expert analysis")
            return {"system": "Saju", "mode": mode, "analysis": "[System degraded — data unavailable]", "confidence": 0.0, "model_used": "none"}
        prompt = self._question_prefix(user_questions) + self._build_prompt(chart_data, mode)
        # Inject mandatory house lord + Bazi element reference (prevents hallucinated elements)
        lord_ref = chart_data.get("_house_lord_reference_block", "")
        if lord_ref:
            prompt = lord_ref + "\n\n" + prompt
        # Inject Neo4j graph rules if available
        graph_rules = get_rule_querier().get_expert_rules("Saju", chart_data)
        if graph_rules:
            prompt = prompt + "\n\n" + graph_rules
        # Inject few-shot exemplars for interpretation quality
        exemplar_block = select_exemplars("Saju", chart_data)
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
                model=settings.saju_expert_model,
                max_tokens=3000,
            )
        else:
            response = gateway.generate(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=prompt,
                model=settings.saju_expert_model,
                max_tokens=3000,
                temperature=0.0,
                reasoning_effort="high",
            )

        return {
            "system": "Saju",
            "mode": mode,
            "analysis": response.get("content"),
            "confidence": 0.88 if response.get("success") else 0.0,
            "model_used": settings.saju_expert_model
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
        saju = data.get('bazi', {})
        natal = saju.get('natal', {})
        strength = saju.get('strength', {})
        pred = saju.get('predictive', {})

        pillars = natal.get('pillars', {})
        shensha = natal.get('shensha', [])
        interactions = natal.get('interactions', {})

        # Build Shen Sha summary
        benefic_ss = [s for s in shensha if s.get('nature') == 'benefic']
        malefic_ss = [s for s in shensha if s.get('nature') in ('malefic', 'challenging')]
        activated_ss = [s for s in shensha if s.get('activated_in_chart')]

        def fmt_ss(stars):
            lines = []
            for s in stars[:8]:
                act = " [ACTIVATED in natal pillars]" if s.get('activated_in_chart') else ""
                lines.append(f"  {s.get('type','?')}: branch {s.get('branch','?')} — {s.get('domain','?')}{act}")
            return '\n'.join(lines) if lines else "  None detected"

        # Current Liu Nian
        current_liu = pred.get('liu_nian_timeline', [{}])[0] if pred.get('liu_nian_timeline') else {}

        # Element balance
        elem_balance = natal.get('element_balance', natal.get('elements', {}))
        elem_str = ""
        if elem_balance:
            elem_str = "  " + ", ".join(f"{k}: {v}" for k, v in elem_balance.items())

        # Ten gods as separate summary (beyond inline pillar data)
        ten_gods_dict = natal.get('ten_gods', {})
        tg_str = ""
        if ten_gods_dict and isinstance(ten_gods_dict, dict):
            tg_lines = []
            for pillar, gdata in ten_gods_dict.items():
                if isinstance(gdata, dict):
                    tg_lines.append(f"  {pillar}: stem={gdata.get('stem_god','?')}, branch={gdata.get('branch_god','?')}")
            tg_str = "\n".join(tg_lines)

        return f"""Analyze this Bazi chart across 6 domains strategically.

**DAY MASTER:** {strength.get('day_master', {}).get('stem')} {strength.get('day_master', {}).get('element')} | Strength: {strength.get('tier')} (score {strength.get('score', 'N/A')})
**USEFUL GOD:** {strength.get('useful_god', '?')} | Secondary: {strength.get('secondary_support', '?')}
**VOID EMPTINESS:** {natal.get('void_emptiness', [])}

**ELEMENT BALANCE:**
{elem_str if elem_str else "  Not available"}

**4 PILLARS:**
Year: {pillars.get('Year', {}).get('stem','?')}{pillars.get('Year', {}).get('branch','?')} ({pillars.get('Year', {}).get('stem_element','?')}/{pillars.get('Year', {}).get('branch_element','?')}) — {pillars.get('Year', {}).get('stem_10_god','?')} / {pillars.get('Year', {}).get('branch_10_god','?')}
Month: {pillars.get('Month', {}).get('stem','?')}{pillars.get('Month', {}).get('branch','?')} ({pillars.get('Month', {}).get('stem_element','?')}/{pillars.get('Month', {}).get('branch_element','?')}) — {pillars.get('Month', {}).get('stem_10_god','?')} / {pillars.get('Month', {}).get('branch_10_god','?')}
Day: {pillars.get('Day', {}).get('stem','?')}{pillars.get('Day', {}).get('branch','?')} ({pillars.get('Day', {}).get('stem_element','?')}/{pillars.get('Day', {}).get('branch_element','?')}) — Self / {pillars.get('Day', {}).get('branch_10_god','?')}
Hour: {pillars.get('Hour', {}).get('stem','?')}{pillars.get('Hour', {}).get('branch','?')} ({pillars.get('Hour', {}).get('stem_element','?')}/{pillars.get('Hour', {}).get('branch_element','?')}) — {pillars.get('Hour', {}).get('stem_10_god','?')} / {pillars.get('Hour', {}).get('branch_10_god','?')}

**TEN GODS SUMMARY (all pillars):**
{tg_str if tg_str else "  (inline per pillar above)"}

**INTERACTIONS:**
Clashes: {interactions.get('clashes', [])}
Harms: {interactions.get('harms', [])}
Destructions: {interactions.get('destructions', [])}
Punishments: {interactions.get('punishments', [])}

**SHEN SHA — BENEFIC STARS:**
{fmt_ss(benefic_ss)}

**SHEN SHA — MALEFIC/CHALLENGING STARS:**
{fmt_ss(malefic_ss)}
(ACTIVATED = present in natal pillars = always-on influence throughout life)

**CURRENT DA YUN (Luck Pillar):**
{pred.get('da_yun', {}).get('pillars', [{}])[0]}

**CURRENT LIU NIAN (Annual Pillar):**
{current_liu.get('year','?')}: {current_liu.get('stem','?')}{current_liu.get('branch','?')}

**UPCOMING LIU NIAN:**
{pred.get('liu_nian_timeline', [])[:5]}

Write all 6 sections as instructed. Be specific about which Shen Sha stars are activated and what that means in practice.
For malefic stars: name the SPECIFIC risk and what timing or behavioral mitigation applies.
For the Da Yun: what is the decade's strategic terrain? Favorable vs. unfavorable Qi channels?"""
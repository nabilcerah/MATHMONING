"""Agent 3 - Difficulty Manager (GDD 14). Rule-based, never an LLM decision.

Starting point - the mastery band:
    0-39 Foundation, 40-69 Intermediate, 70-84 Advanced, 85-100 Mastery challenge.
Player level (report 9 Nov): the team's level sets a FLOOR, so questions grow harder as you
level up - Lv 1-4 foundation, 5-9 intermediate, 10-14 advanced, 15+ mastery. A learner who is
struggling gets the floor one band lower, so levelling up never makes maths unfair.
Safeguards on top:
    * not enough evidence  -> never above Intermediate;
    * struggling recently (low accuracy, many second attempts, heavy hint use) -> one band down;
    * never move more than one band away from the last question in this topic.
"""
from ai.agent_base import Agent
from ai.schemas import DifficultyDecision, validate_difficulty
from mathematics.curriculum import DIFFICULTIES


class DifficultyManager(Agent):
    name = "difficulty_manager"
    BANDS = ((85, "mastery"), (70, "advanced"), (40, "intermediate"), (0, "foundation"))
    LEVEL_BANDS = ((15, "mastery"), (10, "advanced"), (5, "intermediate"), (0, "foundation"))

    def level_floor(self, player_level):
        return next(level for threshold, level in self.LEVEL_BANDS if player_level >= threshold)

    def band(self, mastery):
        return next(level for threshold, level in self.BANDS if mastery >= threshold)

    def recommend(self, analysis, previous="", player_level=None):
        level = self.band(analysis.mastery_score)
        reasons = [f"mastery {analysis.mastery_score} suggests {level}"]
        index = DIFFICULTIES.index(level)
        if analysis.status == "insufficient_evidence":
            index = min(index, 1)
            reasons.append("still gathering evidence, so not above intermediate")
        struggling = analysis.status == "weakness" or (analysis.evidence_count >= 3 and analysis.recent_accuracy < 0.5)
        if struggling and index > 0:
            index -= 1
            reasons.append("recent answers show a struggle, so one step gentler")
        if analysis.hint_rate > 0.6 and index > 0 and analysis.evidence_count >= 3:
            index -= 1
            reasons.append("hints are doing a lot of the work, so one step gentler")
        if player_level:
            floor = DIFFICULTIES.index(self.level_floor(player_level))
            if struggling and floor > 0:
                floor -= 1
            if index < floor:
                index = floor
                reasons.append(f"your team is Lv {player_level}, so at least {DIFFICULTIES[floor]}")
        if previous in DIFFICULTIES:
            last = DIFFICULTIES.index(previous)
            if abs(index - last) > 1:
                index = last + (1 if index > last else -1)
                reasons.append("changing one band at a time")
        reason = "; ".join(reasons)
        return validate_difficulty(DifficultyDecision(DIFFICULTIES[index], reason[:1].upper() + reason[1:] + ".",
                                                      previous))

    # Pre-GDD interface (Arena): three levels from the old per-topic stats.
    LEGACY = ("easy", "intermediate", "advanced")

    def choose(self, performance=None, fallback="easy"):
        performance = performance or {}
        current = performance.get("last_difficulty", fallback)
        index = self.LEGACY.index(current) if current in self.LEGACY else 0
        attempted = performance.get("attempted", 0)
        recent = performance.get("recent_accuracy", performance.get("accuracy", 0.5))
        overall = performance.get("accuracy", recent)
        if attempted >= 3 and (recent < 0.45 or overall < 0.4):
            index, reason = max(0, index - 1), "Recent practice suggests a gentler step will help."
        elif attempted >= 8 and recent >= 0.8 and overall >= 0.72 and performance.get("mastery", 0) >= 65:
            index, reason = min(2, index + 1), "Consistent accuracy shows readiness for a bigger challenge."
        else:
            reason = "Keeping the challenge steady while we build a reliable pattern."
        return _LegacyDecision(self.LEGACY[index], reason)


class _LegacyDecision:
    def __init__(self, level, reason):
        self.level, self.reason = level, reason

"""Agent 5 - Game Master / Quest Director (GDD 14).

Looks at the learning profile, the party and quest progress and RECOMMENDS: the existing quest
that best fits the learner's needs, training activities, boss readiness and learning objectives.
It cannot start, change or complete a quest - those rules live in world.quest_manager.
"""
from ai.agent_base import Agent
from ai.schemas import QuestRecommendation
from mathematics import curriculum
from monsters.monster_data import quests

# Where each topic is practised best when no quest covers it (area name, monster to look for).
TRAINING = {
    "addition": ("Green Meadow", "PYRON"), "subtraction": ("Mirror Beach", "AQUABIT"),
    "multiplication": ("Green Meadow", "VOLTIX"), "division": ("Pine Ridge", "DIVOWL"),
    "fractions": ("Pine Ridge", "FRACTELLA"), "ratios": ("Pine Ridge", "FRACTELLA"),
    "integers": ("Ancient Number Ruins", "NUMEREX"), "algebra": ("the stone tablet in Pine Ridge", "CHRONOX"),
    "geometry": ("Sunsand Desert", "GEOMAX"), "sequences": ("Green Meadow", "CHRONOX"),
}


class GameMaster(Agent):
    name = "game_master"
    BOSS_LEVEL = 7
    BOSS_MASTERY = 45

    def recommend_quest(self, analyses, available, active):
        """Pick the existing quest that best practises the weakest topic. ``analyses`` are
        AnalysisResults ordered from most to least in need."""
        catalogue = quests()
        for analysis in analyses:
            if analysis.status in ("strong", "mastered"):
                continue
            for pool, verb in ((active, "Continue"), (available, "Try")):
                for quest_id in pool:
                    if analysis.topic in catalogue[quest_id].get("topics", ()):
                        name = curriculum.label(analysis.topic).lower()
                        if analysis.status == "weakness":
                            why = f"you are still building {name} skills (mastery {analysis.mastery_score})"
                        elif analysis.status == "insufficient_evidence":
                            why = f"we need a few more {name} questions to see how you're doing"
                        else:
                            why = f"it will strengthen your {name}"
                        priority = {"weakness": 3, "insufficient_evidence": 2}.get(analysis.status, 1)
                        return QuestRecommendation(quest_id, catalogue[quest_id]["title"],
                                                   f"{verb} {catalogue[quest_id]['title']}: {why}.",
                                                   tuple(catalogue[quest_id].get("topics", ())), priority)
        return None

    def training_tip(self, analysis):
        place, monster = TRAINING.get(analysis.topic, ("Green Meadow", ""))
        name = curriculum.label(analysis.topic).lower()
        extra = f" {monster} lives there and uses {name} moves." if monster else ""
        return f"Train {name} in {place}.{extra}"

    def boss_readiness(self, analyses, party_level, seals_done):
        """Advice only: the arch itself opens on the three Numera Seals (a deterministic rule)."""
        weak = [a for a in analyses if a.status == "weakness"]
        if not seals_done:
            return False, "Restore the three Numera Seals in the ruins to open the arch."
        if party_level < self.BOSS_LEVEL:
            return False, f"Train your team to about Lv {self.BOSS_LEVEL} before facing the Arithmetic Beast."
        if weak:
            return False, f"You can enter, but {curriculum.label(weak[0].topic).lower()} practice first would help."
        return True, "Your team and your number skills look ready for the Arithmetic Beast!"

    def objectives(self, analyses, limit=3):
        goals = []
        for analysis in analyses:
            name = curriculum.label(analysis.topic)
            if analysis.status == "insufficient_evidence":
                goals.append(f"Answer {max(1, 5 - analysis.evidence_count)} more {name} questions.")
            elif analysis.status in ("weakness", "developing"):
                target = 40 if analysis.mastery_score < 40 else 70
                goals.append(f"Raise {name} mastery to {target} (now {analysis.mastery_score}).")
            if len(goals) == limit:
                break
        return goals or ["Keep exploring - your skills are in great shape!"]

    def recommendation_text(self, analyses, quest):
        if quest:
            return quest.reason
        need = next((a for a in analyses if a.status in ("weakness", "insufficient_evidence", "developing")), None)
        if need:
            return self.training_tip(need)
        return "All your topics are strong. Seek out the Arena or the Monster Trials for a bigger challenge!"

    # Pre-GDD interface (older screens).
    SKILLS_NEEDED = 3

    def recommendation(self, profile, level=1):
        return "Explore Number Forest and follow your quests in the trainer menu (TAB)."

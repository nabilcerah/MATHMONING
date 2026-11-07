"""Quest and reward recommendations."""


class GameMasterAgent:
    def recommendation(self, profile, level=1):
        if not profile:
            return "Explore Number Forest and meet the forest guide to begin your training."
        weakest = min(profile.items(), key=lambda item: (item[1].get("mastery", 0), item[1].get("accuracy", 0)))[0]
        stats = profile[weakest]
        if stats.get("attempted", 0) < 4:
            return f"A few more {weakest} challenges will reveal your learning pattern."
        if stats.get("mastery", 0) >= 65 and level >= 3:
            return "You are building strong number sense. Visit the old stone arch when you feel ready."
        return f"Try a short practice round on {weakest}; your next wins will make it feel easier."

    def boss_ready(self, profile, level):
        return level >= 3 and len(profile) >= 3 and all(
            value.get("attempted", 0) >= 4 and value.get("mastery", 0) >= 45
            for value in profile.values()
        )

    @staticmethod
    def reward(correct, difficulty, streak=0):
        if not correct:
            return 0
        return {"easy": 4, "intermediate": 7, "advanced": 10}.get(difficulty, 4) + min(streak, 3)

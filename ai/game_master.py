"""Quest and reward recommendations."""


class GameMasterAgent:
    def recommendation(self, profile, level=1):
        if not profile:
            return "Explore Number Forest and meet the forest guide to begin your training."
        from mathematics.question_generator import topic_label
        weakest_id = min(profile.items(), key=lambda item: (item[1].get("mastery", 0), item[1].get("accuracy", 0)))[0]
        stats = profile[weakest_id]
        weakest = topic_label(weakest_id).lower()
        if stats.get("attempted", 0) < 4:
            return f"A few more {weakest} challenges will reveal your learning pattern."
        if stats.get("mastery", 0) >= 65 and level >= 3:
            return "You are building strong number sense. Visit the old stone arch when you feel ready."
        return f"Try a short practice round on {weakest}; your next wins will make it feel easier."

    BOSS_LEVEL = 3
    SKILLS_NEEDED = 3
    MIN_ATTEMPTS = 4
    MIN_MASTERY = 45

    def skill_ready(self, stats):
        return stats.get("attempted", 0) >= self.MIN_ATTEMPTS and stats.get("mastery", 0) >= self.MIN_MASTERY

    def boss_ready(self, profile, level):
        """The arch opens at Lv 3 once any three of the four arithmetic skills are steady."""
        ready = sum(1 for stats in profile.values() if self.skill_ready(stats))
        return level >= self.BOSS_LEVEL and ready >= self.SKILLS_NEEDED

    def boss_progress(self, profile, level, topics=None):
        """Readable checklist lines explaining what still keeps the seal closed."""
        from mathematics.question_generator import QuestionGenerator, topic_label
        lines = []
        for topic in topics or QuestionGenerator.TOPICS:
            stats = profile.get(topic, {})
            attempted, mastery = stats.get("attempted", 0), stats.get("mastery", 0)
            name = topic_label(topic).title()
            if self.skill_ready(stats):
                lines.append(f"{name}: READY")
            elif attempted < self.MIN_ATTEMPTS:
                lines.append(f"{name}: {attempted}/{self.MIN_ATTEMPTS} questions tried")
            else:
                lines.append(f"{name}: mastery {mastery}/{self.MIN_MASTERY}, keep practising")
        return lines

    @staticmethod
    def reward(correct, difficulty, streak=0):
        if not correct:
            return 0
        return {"easy": 4, "intermediate": 7, "advanced": 10}.get(difficulty, 4) + min(streak, 3)

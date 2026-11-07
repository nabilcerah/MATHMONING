"""Question selection agent; all problem answers come from deterministic code."""


class QuestionGeneratorAgent:
    def __init__(self, generator, difficulty_manager):
        self.generator = generator
        self.difficulty_manager = difficulty_manager

    def act(self, profile, topic=None, fallback="easy"):
        profile = profile or {}
        topic = topic or self.generator.choose_topic(profile)
        performance = profile.get(topic, {})
        decision = self.difficulty_manager.choose(performance, fallback)
        question = self.generator.generate(decision.level, topic, profile)
        return {"question": question, "difficulty_reason": decision.reason}

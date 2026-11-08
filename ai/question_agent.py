"""Agent 1 - Question Generator (GDD 14).

Chooses the topic (the move/monster affinity when there is one, otherwise the learner's greatest
need in the current region), asks the deterministic templates for a question at the Difficulty
Manager's level, avoids anything the learner saw recently, and returns the structured question.
Every answer has already been proven by mathematics.question_generator.verify_draft.
"""
from ai.agent_base import Agent
from mathematics import curriculum
from mathematics.question_generator import TemplateQuestionGenerator


class QuestionGeneratorAgent(Agent):
    name = "question_generator"

    def __init__(self, generator=None, difficulty_manager=None, rng=None):
        # ``generator`` may be the pre-GDD QuestionGenerator (Arena compatibility path).
        self.legacy = generator
        self.templates = TemplateQuestionGenerator(rng)
        self.difficulty_manager = difficulty_manager

    @property
    def generator(self):
        return self.legacy

    def choose_topic(self, analyses, affinity=None):
        """``analyses``: AnalysisResults for candidate topics. A move's own topic always wins."""
        if affinity:
            return curriculum.mastery_topic(affinity)
        order = {"weakness": 0, "insufficient_evidence": 1, "developing": 2, "strong": 3, "mastered": 4}
        return min(analyses, key=lambda a: (order[a.status], a.mastery_score)).topic

    def generate(self, topic, difficulty, subtopic=None, affinity="", recent_prompts=()):
        return self.templates.generate(topic, difficulty, subtopic, affinity, avoid=recent_prompts)

    def worked_example(self, question):
        return self.templates.worked_example(question)

    # Pre-GDD interface used by the Arena.
    def act(self, profile, topic=None, fallback="easy"):
        profile = profile or {}
        topic = topic or self.legacy.choose_topic(profile)
        decision = self.difficulty_manager.choose(profile.get(topic, {}), fallback)
        return {"question": self.legacy.generate(decision.level, topic, profile), "difficulty_reason": decision.reason}

"""Coordinates the five offline agents through structured data."""
from dataclasses import dataclass

from ai.difficulty_manager import DifficultyManager
from ai.game_master import GameMasterAgent
from ai.learning_analyst import LearningAnalystAgent
from ai.question_agent import QuestionGeneratorAgent
from ai.tutor_agent import TutorAgent
from mathematics.answer_validator import AnswerValidator
from mathematics.question_generator import QuestionGenerator


@dataclass(frozen=True)
class AnswerDecision:
    correct: bool
    feedback: str
    weakness: str
    next_difficulty: str
    exp_reward: int
    recommendation: str


class AgentOrchestrator:
    """Routes questions, verified answers, learning signals, and rewards."""

    def __init__(self, repository, question_generator=None):
        self.repository = repository
        self.difficulty_manager = DifficultyManager()
        self.questions = QuestionGeneratorAgent(question_generator or QuestionGenerator(), self.difficulty_manager)
        self.analyst = LearningAnalystAgent(repository)
        self.tutor = TutorAgent()
        self.game_master = GameMasterAgent()

    def next_question(self, player_id, topic=None, fallback="easy"):
        profile = self.repository.get_learning_profile(player_id)
        return self.questions.act(profile, topic, fallback)

    def submit_answer(self, player_id, question, submitted):
        correct = AnswerValidator.check(submitted, question.answer)
        signal = self.analyst.observe(player_id, question, submitted, correct)
        profile = self.repository.get_learning_profile(player_id)
        performance = profile.get(question.topic, {})
        next_level = self.difficulty_manager.choose(performance, question.difficulty).level
        feedback = self.tutor.feedback(question, correct)
        recommendation = self.game_master.recommendation(profile)
        if signal.weakness:
            recommendation = signal.weakness + " " + recommendation
        self.repository.add_recommendation(player_id, recommendation)
        reward = self.game_master.reward(correct, question.difficulty, performance.get("streak", 0))
        return AnswerDecision(correct, feedback, signal.weakness, next_level, reward, recommendation)

    def profile(self, player_id, level=1):
        profile = self.repository.get_learning_profile(player_id)
        attempts = self.repository.recent_attempts(player_id, 25)
        mistakes = [attempt for attempt in attempts if not attempt["correct"]][:4]
        return {"topics": profile, "summary": self.repository.overall_summary(player_id),
                "mistakes": mistakes,
                "recommendations": self.repository.recommendations(player_id),
                "next_step": self.game_master.recommendation(profile, level),
                "boss_ready": self.game_master.boss_ready(profile, level)}

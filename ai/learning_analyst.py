"""Records attempts and converts performance into understandable learning signals."""
from dataclasses import dataclass


@dataclass(frozen=True)
class LearningSignal:
    topic: str
    accuracy: float
    recent_accuracy: float
    weakness: str
    improving: bool


class LearningAnalystAgent:
    def __init__(self, repository):
        self.repository = repository

    def observe(self, player_id, question, submitted, correct):
        stats = self.repository.record_attempt(player_id, question, submitted, correct)
        weakness = ""
        if stats["attempted"] >= 3 and (stats["accuracy"] < 0.6 or stats["recent_accuracy"] < 0.5):
            weakness = f"The player may need more practice with {question.concept} in {question.topic}."
        return LearningSignal(question.topic, stats["accuracy"], stats["recent_accuracy"],
                              weakness, stats["recent_accuracy"] > stats["accuracy"])

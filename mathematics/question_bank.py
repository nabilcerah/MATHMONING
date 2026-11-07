"""Immutable question shape shared by the generator and the agents."""
from dataclasses import dataclass


@dataclass(frozen=True)
class MathQuestion:
    question_id: str
    topic: str
    difficulty: str
    prompt: str
    answer: str
    explanation: str
    hint: str
    ability: str
    base_damage: int
    concept: str

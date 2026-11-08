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
    # Optional extras (all defaulted, so older call sites are unchanged):
    steps: tuple = ()          # worked steps for the "solve it together" walkthrough
    visual: tuple = ()         # small drawing, e.g. ("rect", 6, 4) or ("clock", 2, 45)
    format: str = "standard"   # "standard", or a puzzle format used in battle (Phase B)

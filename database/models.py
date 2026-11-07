"""Persistence contracts kept separate from game presentation."""
from dataclasses import dataclass


@dataclass
class PlayerRecord:
    player_id: int
    name: str
    creature: str
    level: int
    hp: int
    max_hp: int
    exp: int
    world: str
    x: int
    y: int


@dataclass
class TopicPerformance:
    topic: str
    attempted: int
    correct: int
    accuracy: float
    mastery: int
    streak: int
    recent_accuracy: float
    common_mistake: str


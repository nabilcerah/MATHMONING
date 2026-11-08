"""Persistence contracts kept separate from game presentation."""
from dataclasses import dataclass


@dataclass
class PlayerRecord:
    player_id: int
    name: str
    creature: str       # the lead monster's species (mirrored for the title screen)
    level: int          # the lead monster's level
    hp: int
    max_hp: int
    exp: int
    world: str          # current map id
    x: int
    y: int
    currency: int = 0
    region: str = "number_forest"


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

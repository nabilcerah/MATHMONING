"""Small records passed from the engine to the screen (animations) and to the battle log."""
from dataclasses import dataclass, field


@dataclass
class Event:
    kind: str            # e.g. player_hit, shield_hit, shield_break, charge, interrupt, monster_hit, phase...
    text: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class Badge:
    """A status chip in the battle UI (shield HP, heat, gravity, phase...)."""
    label: str
    value: str = ""
    color: str = "cream"     # a PALETTE key
    tip: str = ""            # one-line explanation for students


@dataclass
class QuestionRequest:
    """How the next question should be chosen. Mechanics can ask for a special one."""
    purpose: str = "attack"  # attack | interrupt | barrier | split_target | predict | time
    topic: str = None
    level_offset: int = 0
    question: object = None  # a ready-made Question (split targets, combo predictions)
    time_limit: float = None  # seconds for a bonus window (never a failure condition)
    label: str = ""
    source: object = None    # the mechanic that asked


@dataclass
class AnswerResult:
    correct: bool
    question: object
    hit: object = None
    events: list = field(default_factory=list)
    summary: str = ""
    explanation: str = ""
    forgiven: bool = False

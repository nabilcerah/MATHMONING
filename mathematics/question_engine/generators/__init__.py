"""Topic generators. Each is ``generate(rng, level) -> Draft`` and is pure and deterministic for a
given ``random.Random`` state. The engine verifies every draft before a student sees it."""
from dataclasses import dataclass, field
from fractions import Fraction


@dataclass
class Draft:
    prompt: str
    answer: object                 # Fraction/int for number questions, str for choice questions
    mistakes: list = field(default_factory=list)   # values produced by real misconceptions
    explanation: str = ""
    hint: str = ""
    expression: str = ""           # arithmetic that must evaluate to ``answer``
    kind: str = "number"
    options: list = None           # choice questions supply their own options
    visual: tuple = None
    tags: tuple = ()
    verify: object = None          # optional callable() -> bool for answers no expression can show


def frac(a, b=1):
    return Fraction(a, b)


def pick_range(level, table):
    """``table`` has five entries, one per level (1..5)."""
    return table[max(1, min(5, level)) - 1]

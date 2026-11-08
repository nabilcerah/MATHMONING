"""The question record shared by every generator, plus exact answer parsing and checking.

Answers are compared with ``fractions.Fraction`` (never floats, never ``eval``), so 0.5, 1/2 and
2/4 are all the same number. Choice questions (logic, comparisons) compare normalised text.
"""
import re
from dataclasses import dataclass, field
from fractions import Fraction

# Question levels follow the five monster tiers.
LEVEL_NAMES = {1: "Beginner", 2: "Easy-Intermediate", 3: "Intermediate", 4: "Advanced", 5: "Expert"}
# The existing learning profile stores three difficulty labels.
LEVEL_LABELS = {1: "easy", 2: "easy", 3: "intermediate", 4: "advanced", 5: "advanced"}

_NUMBER = re.compile(r"^([+-]?\d+(?:\.\d+)?)$")
_FRACTION = re.compile(r"^([+-]?\d+)\s*/\s*([+-]?\d+)$")
_MIXED = re.compile(r"^([+-]?\d+)\s+(\d+)\s*/\s*(\d+)$")


def parse_number(text):
    """'-3', '0.75', '3/4', '1 1/2', '1,200', '30%' -> Fraction, or None if it isn't a plain number."""
    if isinstance(text, (int, Fraction)):
        return Fraction(text)
    cleaned = str(text).strip().replace(",", "").replace("−", "-").rstrip("%°").strip()
    if not cleaned or len(cleaned) > 24:
        return None
    match = _NUMBER.match(cleaned)
    if match:
        return Fraction(match.group(1))
    match = _FRACTION.match(cleaned)
    if match:
        denominator = int(match.group(2))
        return Fraction(int(match.group(1)), denominator) if denominator else None
    match = _MIXED.match(cleaned)
    if match:
        whole, numerator, denominator = (int(g) for g in match.groups())
        if not denominator:
            return None
        part = Fraction(numerator, denominator)
        return whole - part if whole < 0 or cleaned.startswith("-") else whole + part
    return None


def fmt(value):
    """Display a number the way a student would write it: 7, -3, 3/4, 2.5 for money-like halves."""
    if isinstance(value, str):
        return value
    value = Fraction(value)
    if value.denominator == 1:
        number = value.numerator
        return f"{number:,}" if abs(number) >= 10000 else str(number)
    return f"{value.numerator}/{value.denominator}"


def normalise_text(text):
    return re.sub(r"\s+", " ", str(text).strip().lower())


@dataclass
class Question:
    question_id: str
    topic: str
    level: int                      # 1..5, matching the monster tiers
    prompt: str
    answer: str                     # canonical display form
    choices: list = field(default_factory=list)   # multiple-choice options (answer included)
    explanation: str = ""
    hint: str = ""
    kind: str = "number"            # "number" (typed or chosen) or "choice" (choose only)
    monster: str = ""               # the monster that asked it
    weakness: bool = False          # does it target the monster's weakness?
    expression: str = ""            # arithmetic that reproduces the answer (verified on creation)
    visual: tuple = None            # optional diagram data for the UI
    tags: tuple = ()
    base_damage: int = 10           # compatibility with the classic battle code

    # ----------------------------------------------------- compatibility with the learning profile
    @property
    def difficulty(self):
        return LEVEL_LABELS.get(self.level, "intermediate")

    @property
    def concept(self):
        return self.topic.replace("_", " ")

    @property
    def level_name(self):
        return LEVEL_NAMES.get(self.level, "")

    @property
    def typed_allowed(self):
        return self.kind == "number"

    @property
    def answer_index(self):
        for index, choice in enumerate(self.choices):
            if self.check(choice):
                return index
        return -1

    def check(self, submitted):
        """Exact, deterministic checking. Never trusts an LLM and never runs ``eval``."""
        if submitted is None:
            return False
        if self.kind == "number":
            got, expected = parse_number(submitted), parse_number(self.answer)
            return got is not None and expected is not None and got == expected
        return normalise_text(submitted) == normalise_text(self.answer)

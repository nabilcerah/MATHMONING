"""QuestionEngine: one per battle. Picks the generator, sets the difficulty, refuses repeats and
verifies every answer before the question is shown.

    engine = QuestionEngine(random.Random(7), monster="CRYSTALGON")
    q = engine.generate("angles", level=3, weakness=True)
    q.check("70")   # exact, deterministic
"""
import itertools
import random
from fractions import Fraction

from mathematics.question_engine.distractors import build_choices, numeric_options
from mathematics.question_engine.generators import arithmetic, algebra, fractions, geometry, patterns, reasoning
from mathematics.question_engine.model import Question, fmt
from mathematics.question_engine.safe_eval import safe_eval

GENERATORS = {
    "addition": arithmetic.addition,
    "subtraction": arithmetic.subtraction,
    "multiplication": arithmetic.multiplication,
    "division": arithmetic.division,
    "negative_numbers": arithmetic.negative_numbers,
    "large_numbers": arithmetic.large_numbers,
    "fractions": fractions.fractions,
    "percentages": fractions.percentages,
    "geometry": geometry.geometry,
    "angles": geometry.angles,
    "algebra": algebra.algebra,
    "equations": algebra.equations,
    "sequences": patterns.sequences,
    "exponents": patterns.exponents,
    "mixed_operations": reasoning.mixed_operations,
    "logic": reasoning.logic,
    "combined": reasoning.combined,
}
# Friendly names shown in battle.
LABELS = {
    "addition": "Addition", "subtraction": "Subtraction", "multiplication": "Multiplication",
    "division": "Division", "negative_numbers": "Negative Numbers", "large_numbers": "Large Numbers",
    "fractions": "Fractions", "percentages": "Percentages", "geometry": "Geometry", "angles": "Angles",
    "algebra": "Algebra", "equations": "Equations", "sequences": "Sequences", "exponents": "Exponents",
    "mixed_operations": "Order of Operations", "logic": "Logic", "combined": "Combined Concepts",
}
# Aliases let monster data use natural words ("integers", "patterns") for engine topics.
ALIASES = {"integers": "negative_numbers", "integer_arithmetic": "negative_numbers", "patterns": "sequences",
           "pattern_recognition": "sequences", "powers": "exponents", "order_of_operations": "mixed_operations",
           "number_comparison": "large_numbers", "reasoning": "logic", "puzzles": "logic", "shapes": "geometry",
           "unknowns": "equations", "variables": "equations", "percent": "percentages"}
TOPICS = tuple(t for t in GENERATORS if t != "combined")


class GenerationError(RuntimeError):
    pass


def canonical_topic(topic):
    topic = str(topic).lower().replace(" ", "_")
    return ALIASES.get(topic, topic)


def topic_label(topic):
    return LABELS.get(canonical_topic(topic), str(topic).replace("_", " ").title())


def verify_draft(draft):
    """True only if the draft's answer is proven by its expression or its verify() check."""
    if draft.kind == "choice":
        return draft.options is not None and str(draft.answer) in [str(o) for o in draft.options]
    if draft.expression:
        try:
            if safe_eval(draft.expression) != Fraction(draft.answer):
                return False
        except (ValueError, ZeroDivisionError, SyntaxError):
            return False
    elif draft.verify is None:
        return False  # every numeric answer must be provable
    if draft.verify is not None and not draft.verify():
        return False
    return True


class QuestionEngine:
    MAX_ATTEMPTS = 40

    def __init__(self, rng=None, monster=""):
        self.rng = rng or random.Random()
        self.monster = monster
        self.seen = set()
        self._ids = itertools.count(1)

    def generate(self, topic, level=1, weakness=False, choice_count=4):
        topic = canonical_topic(topic)
        if topic not in GENERATORS:
            raise GenerationError(f"unknown topic {topic!r}")
        level = max(1, min(5, int(level)))
        last_error = None
        for _ in range(self.MAX_ATTEMPTS):
            draft = GENERATORS[topic](self.rng, level)
            if not verify_draft(draft):
                last_error = draft.prompt
                continue
            if draft.prompt in self.seen:
                continue  # no repeats inside one battle
            self.seen.add(draft.prompt)
            return self._finish(draft, topic, level, weakness, choice_count)
        if last_error:
            raise GenerationError(f"{topic} could not produce a verified question (last: {last_error})")
        # Every prompt in this tiny space was used: allow a repeat rather than stalling the battle.
        draft = GENERATORS[topic](self.rng, level)
        return self._finish(draft, topic, level, weakness, choice_count)

    def _finish(self, draft, topic, level, weakness, choice_count):
        if draft.kind == "choice":
            answer = str(draft.answer)
            choices = build_choices(answer, [str(o) for o in draft.options if str(o) != answer], self.rng, "choice")
        else:
            answer = fmt(Fraction(draft.answer))
            wrong = numeric_options(Fraction(draft.answer), draft.mistakes, self.rng, count=choice_count - 1)
            choices = build_choices(answer, wrong, self.rng, "number")
        prefix = (self.monster or "q").lower()
        return Question(f"{prefix}-{topic}-{next(self._ids)}", topic, level, draft.prompt, answer, choices,
                        draft.explanation, draft.hint, draft.kind, self.monster, weakness, draft.expression,
                        draft.visual, tuple(draft.tags), base_damage=8 + 3 * level)

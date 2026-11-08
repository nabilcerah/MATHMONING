"""Deterministic, seeded-friendly arithmetic and extension question generator."""
import random
import uuid
from collections import deque

from mathematics import extra_topics
from mathematics.question_bank import MathQuestion


def topic_label(topic):
    """Readable topic name: "place_value" -> "PLACE VALUE"."""
    return extra_topics.LABELS.get(topic, str(topic).replace("_", " ").upper())


class QuestionGenerator:
    CORE_TOPICS = ("addition", "subtraction", "multiplication", "division")
    TOPICS = CORE_TOPICS + tuple(extra_topics.BUILDERS)
    EXTENSION_TOPICS = ("algebra",)
    DIFFICULTY_ORDER = ("easy", "intermediate", "advanced")

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.recent_ids = deque(maxlen=12)
        self.recent_prompts = deque(maxlen=10)

    def choose_topic(self, profile=None):
        profile = profile or {}
        choices = list(self.TOPICS)
        weak = [name for name in choices if profile.get(name, {}).get("accuracy", 1.0) < 0.6]
        # Skills with little evidence also get priority, so every topic gets regular practice.
        unpractised = [name for name in choices if profile.get(name, {}).get("attempted", 0) < 4]
        roll = self.rng.random()
        if weak and roll < 0.68:
            choices = weak
        elif unpractised and roll < 0.9:
            choices = unpractised
        return self.rng.choice(choices)

    def generate(self, difficulty="easy", topic=None, profile=None):
        difficulty = difficulty if difficulty in self.DIFFICULTY_ORDER else "easy"
        profile = profile or {}
        # Algebra is supported as a reusable agent/workflow extension; the first
        # explorable world still draws only from its arithmetic topic set.
        if topic not in self.TOPICS + self.EXTENSION_TOPICS:
            topic = self.choose_topic(profile)
        if topic in extra_topics.BUILDERS:
            return self._extra(topic, difficulty, profile)
        bounds = {"easy": (2, 12), "intermediate": (8, 35), "advanced": (16, 99)}[difficulty]
        low, high = bounds
        a = self.rng.randint(low, high)
        b = self.rng.randint(low, high)
        if topic == "algebra":
            coefficient = self.rng.randint(2, 8)
            variable = self.rng.randint(low, high)
            offset = self.rng.randint(1, max(3, high // 2))
            total = coefficient * variable + offset
            answer = variable
            prompt = f"Solve for x: {coefficient}x + {offset} = {total}"
            explain = f"Undo the + {offset}: {total} − {offset} = {coefficient}x. Then divide by {coefficient}; x = {answer}."
            hint = f"Undo operations in reverse: subtract {offset} from both sides, then divide by {coefficient}."
            concept = "isolating variables"
        elif topic == "addition":
            answer, prompt = a + b, f"{a} + {b} = ?"
            explain = f"Add the two parts: {a} + {b} = {answer}."
            hint = f"Start at {a} and count on {b}, or split {b} into tens and ones."
            concept = "combining quantities"
        elif topic == "subtraction":
            a, b = max(a, b), min(a, b)
            answer, prompt = a - b, f"{a} − {b} = ?"
            explain = f"Subtract {b} from {a}: {a} − {b} = {answer}."
            hint = f"Think: what number added to {b} makes {a}?"
            concept = "difference"
        elif topic == "multiplication":
            answer, prompt = a * b, f"{a} × {b} = ?"
            explain = f"Multiplication is equal groups: {a} groups of {b} make {answer}."
            hint = f"Break {b} into easier parts and calculate {a} × each part."
            concept = "equal groups"
        else:
            answer = a
            product = a * b
            prompt = f"{product} ÷ {b} = ?"
            explain = f"Division undoes multiplication: {b} × {a} = {product}, so {product} ÷ {b} = {a}."
            hint = f"Ask which number multiplied by {b} gives {product}."
            concept = "inverse operations"
        question_id = uuid.uuid4().hex
        while prompt in self.recent_prompts:
            return self.generate(difficulty, topic, profile)
        self.recent_ids.append(question_id)
        self.recent_prompts.append(prompt)
        return MathQuestion(question_id, topic, difficulty, prompt, str(answer), explain, hint,
                            self._ability(topic), {"easy": 6, "intermediate": 9, "advanced": 13}[difficulty], concept)

    def _extra(self, topic, difficulty, profile):
        for _ in range(20):  # avoid repeating a recent prompt
            built = extra_topics.BUILDERS[topic](self.rng, difficulty)
            if built["prompt"] not in self.recent_prompts:
                break
        self.recent_prompts.append(built["prompt"])
        question_id = uuid.uuid4().hex
        self.recent_ids.append(question_id)
        return MathQuestion(question_id, topic, difficulty, built["prompt"], built["answer"], built["explanation"],
                            built["hint"], self._ability(topic), {"easy": 6, "intermediate": 9, "advanced": 13}[difficulty],
                            built["concept"], built["steps"], built["visual"])

    @staticmethod
    def _ability(topic):
        return {"addition": "Addition Strike", "subtraction": "Tidal Reversal", "algebra": "Algebra Beam",
                "multiplication": "Multiplication Blast", "division": "Division Current",
                "fractions": "Fraction Slice", "place_value": "Place Value Pulse", "shapes": "Shape Shield",
                "time_money": "Clockwork Coin"}[topic]


# =============================================================================== GDD generator
# GDD 14 (Agent 1) and 18: structured, verified questions from the deterministic templates.
import itertools as _itertools
from dataclasses import dataclass as _dataclass, field as _field
from fractions import Fraction as _Fraction

from mathematics import curriculum as _curriculum
from mathematics import question_templates as _templates


class VerificationError(RuntimeError):
    """A template produced an answer the mathematics engine could not prove."""


@_dataclass(frozen=True)
class GeneratedQuestion:
    """GDD 18: every question carries its topic, subtopic, difficulty, answer type, verified answer,
    hints, worked explanation, monster affinity and source."""
    question_id: str
    topic: str
    subtopic: str
    difficulty: str
    prompt: str
    answer_type: str
    answer: str
    hints: tuple
    explanation: str
    steps: tuple = ()
    affinity: str = ""
    source: str = "template"
    misconceptions: dict = _field(default_factory=dict)
    visual: tuple = ()
    format: str = "standard"
    proof: dict = _field(default_factory=dict, compare=False, repr=False)   # how the answer is proven

    def verified(self):
        """Re-prove the stored answer from the generator's proof (independent of the template)."""
        return bool(self.proof) and verify_draft({**self.proof, "answer": self.answer})

    # Compatibility with the MathQuestion shape used by the tutor, arena and learning records.
    @property
    def hint(self):
        return self.hints[0] if self.hints else ""

    @property
    def concept(self):
        return self.subtopic.replace("_", " ")

    @property
    def ability(self):
        return _curriculum.label(self.topic)

    @property
    def base_damage(self):
        return {"foundation": 6, "intermediate": 9, "advanced": 12, "mastery": 14}.get(self.difficulty, 8)

    def to_dict(self):
        """The structured question object from GDD 14 (Agent 1)."""
        return {"question_id": self.question_id, "topic": self.topic, "subtopic": self.subtopic,
                "difficulty": self.difficulty, "question": self.prompt, "answer_type": self.answer_type,
                "correct_answer": self.answer, "hint": self.hint, "hints": list(self.hints),
                "explanation": self.explanation, "affinity": self.affinity, "source": self.source}

    def check(self, submitted):
        from mathematics.answer_validator import validate
        return validate(submitted, self.answer, self.answer_type)


def verify_draft(draft):
    """Prove a template's answer independently of the template's own arithmetic."""
    from mathematics.answer_validator import parse_expression, parse_number, parse_time
    from mathematics.question_engine.safe_eval import safe_eval
    answer = draft["answer"]
    checked = False
    if draft.get("expression"):
        value = safe_eval(draft["expression"])
        expected = parse_number(answer)
        if expected is None or _Fraction(value) != expected:
            return False
        checked = True
    if draft.get("equation"):
        lhs, rhs = draft["equation"]
        value = parse_number(answer)
        if value is None:
            return False
        if parse_expression(lhs).subs("x", value) != parse_expression(rhs).subs("x", value):
            return False
        checked = True
    if draft.get("same_as"):
        original, simplified = draft["same_as"]
        if parse_expression(original) != parse_expression(simplified):
            return False
        if parse_expression(simplified) != parse_expression(answer):
            return False
        checked = True
    if draft.get("minutes"):
        expression, minutes = draft["minutes"]
        if safe_eval(expression) != minutes or parse_time(answer) != minutes % (24 * 60):
            return False
        checked = True
    if draft.get("check") is not None:
        if not draft["check"]():
            return False
        checked = True
    return checked


SAFE_HINT = "Do one step at a time and write down what you get after each step."


def _safe_hints(prompt, answer, hints):
    """A hint may never state the answer (unless the prompt itself already shows that number)."""
    from ai.schemas import reveals
    if reveals(prompt, answer):
        return list(hints)
    return [SAFE_HINT if reveals(hint, answer) else hint for hint in hints]


class TemplateQuestionGenerator:
    """Builds verified questions for a topic and difficulty, never repeating a recent prompt."""
    MAX_TRIES = 30

    def __init__(self, rng=None, history=12):
        self.rng = rng or random.Random()
        self.recent = deque(maxlen=history)
        self._ids = _itertools.count(1)

    def generate(self, topic, difficulty="foundation", subtopic=None, affinity="", avoid=()):
        topic = _curriculum.mastery_topic(topic)
        if topic not in _templates.TEMPLATES:
            topic = "addition"
        difficulty = _curriculum.normalise_difficulty(difficulty)
        builder = _templates.TEMPLATES[topic]
        avoid = set(avoid) | set(self.recent)
        last = None
        for _ in range(self.MAX_TRIES):
            draft = builder(self.rng, difficulty, subtopic)
            if not verify_draft(draft):
                raise VerificationError(f"{topic}/{difficulty}: unverified answer for {draft['prompt']!r}")
            last = draft
            if draft["prompt"] not in avoid:
                break
        self.recent.append(last["prompt"])
        last["hints"] = _safe_hints(last["prompt"], last["answer"], last["hints"])
        code = topic[:3].upper()
        return GeneratedQuestion(f"{code}_{difficulty[:3].upper()}_{next(self._ids):04d}_{uuid.uuid4().hex[:6]}",
                                 topic, last["subtopic"], difficulty, last["prompt"], last["answer_type"],
                                 last["answer"], tuple(last["hints"]), last["explanation"], tuple(last["steps"]),
                                 affinity, "template", dict(last["misconceptions"]), tuple(last["visual"] or ()),
                                 proof={key: last.get(key) for key in ("expression", "equation", "same_as", "minutes",
                                                                       "check")})

    def worked_example(self, question):
        """A solved question of the same kind with different numbers (never the player's own)."""
        for _ in range(10):
            draft = _templates.TEMPLATES[question.topic](self.rng, question.difficulty, question.subtopic
                                                         if question.subtopic.startswith("bridge") else None)
            if draft["prompt"] != question.prompt and draft["subtopic"] == question.subtopic:
                return {"prompt": draft["prompt"], "steps": list(draft["steps"]), "answer": draft["answer"]}
        return {"prompt": draft["prompt"], "steps": list(draft["steps"]), "answer": draft["answer"]}

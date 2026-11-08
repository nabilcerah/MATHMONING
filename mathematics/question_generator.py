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

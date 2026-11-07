"""Deterministic, seeded-friendly arithmetic and extension question generator."""
import random
import uuid
from collections import deque

from mathematics.question_bank import MathQuestion


class QuestionGenerator:
    TOPICS = ("addition", "subtraction", "multiplication", "division")
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
        if weak and self.rng.random() < 0.68:
            choices = weak
        return self.rng.choice(choices)

    def generate(self, difficulty="easy", topic=None, profile=None):
        difficulty = difficulty if difficulty in self.DIFFICULTY_ORDER else "easy"
        profile = profile or {}
        # Algebra is supported as a reusable agent/workflow extension; the first
        # explorable world still draws only from its arithmetic topic set.
        if topic not in self.TOPICS + self.EXTENSION_TOPICS:
            topic = self.choose_topic(profile)
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

    @staticmethod
    def _ability(topic):
        return {"addition": "Addition Strike", "subtraction": "Tidal Reversal", "algebra": "Algebra Beam",
                "multiplication": "Multiplication Blast", "division": "Division Current"}[topic]

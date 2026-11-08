"""AI players for the Math Arena.

Each rival is an agent with a rating and a playing style. For every question it decides how long
it will "think" and whether it will get the answer right, from its rating, the question's
difficulty and its style. A rival that answers wrong is locked out of the round, so the player can
still win it. A light "focus" mechanic keeps matches tense: a rival that falls behind concentrates
a little harder, and one that is far ahead relaxes a little.
"""
import math
import random
from dataclasses import dataclass

DIFFICULTY_SECONDS = {"easy": 6.0, "intermediate": 9.0, "advanced": 13.0}
DIFFICULTY_PENALTY = {"easy": 0.0, "intermediate": 0.05, "advanced": 0.12}
STYLES = {
    # style: (speed multiplier, accuracy bonus, description)
    "steady": (1.00, 0.00, "Never rushes, rarely panics."),
    "careful": (1.25, 0.08, "Slow and sure: checks every answer twice."),
    "fast": (0.75, -0.10, "Buzzes in early... sometimes too early."),
    "genius": (0.85, 0.06, "Quick AND accurate. The final boss of the Arena."),
}


@dataclass(frozen=True)
class RivalProfile:
    rival_id: str
    name: str
    title: str
    rating: int
    style: str
    monster: str
    sheet: str = ""          # character art, if this rival has some
    taunt: str = ""
    lose_line: str = ""


RIVALS = (
    RivalProfile("byte", "BYTE", "Practice Bot", 900, "steady", "VOLTIX", "",
                 "BEEP. Calculating your defeat... 2 + 2 = victory.", "ERROR 404: win not found. Good game!"),
    RivalProfile("friend", "{friend}", "Fellow Ranger", 1000, "careful", "DIVOWL", "characters/{friend_upper}",
                 "Let's make this a good one!", "Wow, you're quick! Rematch soon?"),
    RivalProfile("rex", "Rex", "Rival Ranger", 1100, "fast", "VOLTIX", "characters/REX",
                 "My VOLTIX multiplies faster than you can blink!", "...Fine. You got lucky. Next time!"),
    RivalProfile("cipher", "CIPHER", "AI Speedster", 1250, "fast", "FRACTELLA", "",
                 "Processing speed: maximum. Error rate: acceptable.", "Recalibrating... your accuracy is impressive."),
    RivalProfile("nova", "NOVA", "AI Strategist", 1400, "careful", "PRISMVOLT", "",
                 "I have studied 10,000 matches. I know your next move.", "Unexpected. Adding you to my notes."),
    RivalProfile("numeris", "Professor Numeris", "Arena Champion", 1550, "genius", "CHRONOX",
                 "characters/PROFESSOR_NUMERIS",
                 "Show me everything you've learned, young ranger!", "Splendid! You are the new Champion!"),
)

RANKS = ((1450, "CHAMPION"), (1300, "PLATINUM"), (1150, "GOLD"), (1000, "SILVER"), (0, "BRONZE"))


def rank_for(rating):
    return next(name for floor, name in RANKS if rating >= floor)


def elo_change(player_rating, rival_rating, player_won, k=32):
    expected = 1 / (1 + 10 ** ((rival_rating - player_rating) / 400))
    return round(k * ((1 if player_won else 0) - expected))


@dataclass
class RivalPlan:
    think_seconds: float
    correct: bool
    shown_answer: str


class ArenaRivalAgent:
    def __init__(self, profile, rating=None, rng=None):
        self.profile = profile
        self.rating = rating if rating is not None else profile.rating
        self.rng = rng or random.Random()
        self.speed, self.accuracy_bonus, _ = STYLES[profile.style]

    def accuracy(self, difficulty, focus=0.0):
        base = 0.55 + (self.rating - 900) / 1600          # 0.55 at 900 rating, ~0.95 at 1550
        value = base + self.accuracy_bonus - DIFFICULTY_PENALTY.get(difficulty, 0) + focus * 0.05
        return max(0.4, min(0.97, value))

    def plan(self, question, score_gap=0):
        """Decide this round. score_gap = player's score minus the rival's score."""
        focus = max(-1.0, min(1.0, score_gap / 2))  # behind -> focus harder; ahead -> relax a little
        seconds = DIFFICULTY_SECONDS.get(question.difficulty, 8.0)
        if getattr(question, "format", "standard") != "standard":
            seconds *= 1.6
        seconds *= self.speed * (1000 / self.rating) ** 0.8 * (1 - 0.12 * focus)
        seconds *= self.rng.uniform(0.8, 1.25)
        correct = self.rng.random() < self.accuracy(question.difficulty, focus)
        return RivalPlan(max(1.5, seconds), correct, question.answer if correct else self._near_miss(question.answer))

    def _near_miss(self, answer):
        """A believable wrong answer (off by a little), so a rival's mistake looks like a real slip."""
        try:
            value = float(answer)
        except ValueError:
            return "?"
        slip = self.rng.choice([-10, -2, -1, 1, 2, 10])
        wrong = value + slip
        if wrong == value or wrong < 0:
            wrong = value + 1
        return str(int(wrong)) if wrong == int(wrong) else f"{wrong:.2f}"

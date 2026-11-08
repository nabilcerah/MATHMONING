"""Trainer skills, unlocked by trainer level. Using a skill is free (it doesn't end your turn) but
each has a cooldown counted in answered questions."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    unlock_level: int
    cooldown: int
    description: str


SKILLS = (
    Skill("focus", "Focus", 1, 4, "Removes two wrong options from the next question."),
    Skill("analyse", "Analyse", 2, 3, "Reveals the monster's next move and how to counter it."),
    Skill("shield_breaker", "Shield Breaker", 4, 4, "Your next correct answer hits shields and barriers twice as hard."),
    Skill("second_chance", "Second Chance", 6, 5, "Your next wrong answer is forgiven: the monster can't feed on it."),
    Skill("mind_surge", "Mind Surge", 9, 6, "Your next correct answer is a guaranteed critical hit."),
)
SKILL_BY_ID = {skill.id: skill for skill in SKILLS}


def unlocked(trainer_level):
    return [skill for skill in SKILLS if trainer_level >= skill.unlock_level]


def newly_unlocked(old_level, new_level):
    return [skill for skill in SKILLS if old_level < skill.unlock_level <= new_level]

"""Authoritative damage maths (deterministic for a seeded RNG; never decided by an AI or LLM).

Player hit:   BaseAtk x AnswerMult x WeaknessMult x CritMult x extras - Defence x defence_factor
Monster hit:  MonsterAtk x Power x extras x variance - PlayerDefence x defence_factor

Both are clamped: a minimum so progress is always visible, and a maximum fraction of the target's
max HP so no single answer (or single attack) can end a battle from full health.
"""
from dataclasses import dataclass, field


@dataclass
class Hit:
    """A player attack being built up. Mechanics append to ``extras`` and ``notes``."""
    base: float
    answer_mult: float = 1.0
    weakness_mult: float = 1.0
    critical_mult: float = 1.0
    extras: list = field(default_factory=list)      # [(label, multiplier)]
    defence: float = 0.0
    shield_mult: float = 1.0                        # extra damage dealt to shields/barriers
    notes: list = field(default_factory=list)       # plain-language reasons shown to the student
    raw: int = 0
    to_shield: int = 0
    to_hp: int = 0
    blocked: int = 0
    critical: bool = False

    def multiplier(self):
        total = self.answer_mult * self.weakness_mult * self.critical_mult
        for _, value in self.extras:
            total *= value
        return total


def resolve_player_hit(hit, monster_max_hp, settings):
    raw = hit.base * hit.multiplier() - hit.defence * settings["defence_factor"]
    cap = max(settings["min_damage"], round(monster_max_hp * settings["max_fraction_of_max_hp"]))
    if hit.answer_mult <= 0:
        hit.raw = 0
    else:
        hit.raw = int(max(settings["min_damage"], min(cap, round(raw))))
    hit.to_hp = hit.raw
    return hit


@dataclass
class MonsterHit:
    attack: float
    power: float = 1.0
    extras: list = field(default_factory=list)
    defence: float = 0.0
    variance: float = 1.0
    critical: bool = False
    amount: int = 0
    notes: list = field(default_factory=list)


def resolve_monster_hit(hit, player_max_hp, settings, critical_mult=1.5):
    total = hit.attack * hit.power * hit.variance * settings.get("global_mult", 1.0)
    for _, value in hit.extras:
        total *= value
    if hit.critical:
        total *= critical_mult
    total -= hit.defence * settings["defence_factor"]
    cap = max(settings["min_damage"], round(player_max_hp * settings["max_fraction_of_player_hp"]))
    hit.amount = int(max(settings["min_damage"], min(cap, round(total))))
    return hit

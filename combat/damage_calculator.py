"""GDD 7.5. The game engine is the only thing that calculates or applies damage.

    Damage = (Move Power + 0.5 x Attacker Attack) x Defence Factor x Answer Multiplier
             x Mastery Multiplier x Element Multiplier
    Defence Factor     = 100 / (100 + Defender Defence x 2)
    Mastery Multiplier = 0.9 + 0.2 x (Topic Mastery / 100)

``extra`` carries the documented passive/item/effect multipliers (1.0 when none apply), so the
core formula above is always visible and testable on its own.
"""
from dataclasses import dataclass, field

from monsters.monster_data import rules


@dataclass(frozen=True)
class DamageResult:
    amount: int
    raw: float
    parts: dict = field(default_factory=dict)


def defence_factor(defence):
    cfg = rules()["damage"]
    return cfg["defence_base"] / (cfg["defence_base"] + max(0, defence) * cfg["defence_weight"])


def mastery_multiplier(mastery):
    cfg = rules()["damage"]
    mastery = max(0, min(100, mastery))
    return cfg["mastery_floor"] + cfg["mastery_range"] * (mastery / 100)


def calculate(power, attack, defence, answer_multiplier=1.0, mastery=50, element_multiplier=1.0, extra=1.0):
    cfg = rules()["damage"]
    base = power + cfg["attack_weight"] * attack
    parts = {"base": base, "defence": defence_factor(defence), "answer": answer_multiplier,
             "mastery": mastery_multiplier(mastery), "element": element_multiplier, "extra": extra}
    raw = base * parts["defence"] * answer_multiplier * parts["mastery"] * element_multiplier * extra
    if answer_multiplier <= 0 or power <= 0:
        return DamageResult(0, raw, parts)
    # round() alone would round 0.5 to even; damage rounds half up so equal inputs never feel stingy.
    amount = int(raw + 0.5)
    return DamageResult(max(int(cfg["minimum"]), amount), raw, parts)

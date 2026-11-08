"""GDD 8: Math Capsule captures. The probability is pure arithmetic; AI never touches it."""
from dataclasses import dataclass

from monsters.monster_data import rules


@dataclass(frozen=True)
class CaptureResult:
    success: bool
    chance: float      # percentage, already clamped
    roll: float        # the 0-100 roll that was compared with the chance


def capture_chance(hp_ratio, correct):
    """Capture Chance = 20 + 50 x (1 - HP ratio) + 15 if the binding answer was right; clamped 5-90."""
    cfg = rules()["capture"]
    hp_ratio = max(0.0, min(1.0, float(hp_ratio)))
    chance = cfg["base"] + cfg["hp_weight"] * (1 - hp_ratio) + (cfg["knowledge_bonus"] if correct else 0)
    return max(cfg["min"], min(cfg["max"], chance))


def can_capture(enemy, kind, capsules):
    """(allowed, reason). Only wild monsters, never bosses, and only with a capsule in the bag."""
    if kind != "wild" or enemy.spec.boss:
        return False, "Only wild monsters can be captured."
    if enemy.fainted:
        return False, "It has fainted."
    if capsules <= 0:
        return False, "You have no Math Capsules. Buy some at the shop."
    return True, ""


def attempt(enemy, correct, rng):
    """Roll a capture. The capsule is consumed by the caller whether or not it works."""
    chance = capture_chance(enemy.hp / max(1, enemy.max_hp), correct)
    roll = rng.random() * 100
    return CaptureResult(roll < chance, chance, roll)

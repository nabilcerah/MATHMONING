"""Every tunable number of the advanced battle system, in one place.

Defaults live here; ``data/balance.json`` (optional) overrides any of them, so the battle can be
rebalanced without touching code. Values are merged section by section.
"""
import copy
import json

from config import ROOT

BALANCE_PATH = ROOT / "data" / "balance.json"

DEFAULTS = {
    # Five tiers. ``question_level`` is the maths difficulty (1 Beginner .. 5 Expert).
    "tiers": [
        {"id": "common", "name": "Common", "min_level": 1, "max_level": 9, "question_level": 1,
         "stat_mult": 1.0, "exp_mult": 1.0, "color": [176, 186, 176]},
        {"id": "uncommon", "name": "Uncommon", "min_level": 10, "max_level": 20, "question_level": 2,
         "stat_mult": 1.1, "exp_mult": 1.3, "color": [120, 214, 140]},
        {"id": "rare", "name": "Rare", "min_level": 21, "max_level": 35, "question_level": 3,
         "stat_mult": 1.22, "exp_mult": 1.7, "color": [110, 170, 250]},
        {"id": "epic", "name": "Epic", "min_level": 36, "max_level": 49, "question_level": 4,
         "stat_mult": 1.36, "exp_mult": 2.2, "color": [200, 130, 255]},
        {"id": "mythical", "name": "Mythical", "min_level": 50, "max_level": 99, "question_level": 5,
         "stat_mult": 1.55, "exp_mult": 3.0, "color": [255, 196, 80]},
    ],
    # Per-level growth of each stat (relative to the monster's reference level in its JSON).
    "growth": {"hp": 0.05, "attack": 0.035, "defence": 0.03, "speed": 0.015},
    "monster_hp_mult": 1.35,         # one knob to make every fight longer or shorter
    "crit": {"base": 0.04, "per_speed": 0.002, "cap": 0.25, "multiplier": 1.5},
    "special_power": 1.6,            # special attack power = attack x this
    "exp": {"base": 18, "per_level": 5, "boss_mult": 1.6},
    # Player -> monster:  Damage = BaseAtk x Answer x Weakness x Critical x extras - Defence x defence_factor
    "player_damage": {
        "answer_correct": 1.0, "answer_wrong": 0.0, "typed_bonus": 1.15,
        "weakness": 1.5, "resistance": 0.6, "critical": 1.6, "combo_step": 0.05, "combo_cap": 4,
        "defence_factor": 0.5, "min_damage": 3, "max_fraction_of_max_hp": 0.25,
    },
    # Monster -> player.
    "monster_damage": {
        "variance_low": 0.9, "defence_factor": 0.5, "min_damage": 2, "max_fraction_of_player_hp": 0.45,
        "counter_power": 1.3, "global_mult": 0.7,
    },
    # Player combat numbers come from the fighting team member's level.
    # attack = attack_base x (1 + attack_growth x (level - 1)) + trainer bonus: the same kind of growth as
    # monster HP, so fights stay a similar length at every tier.
    "player": {"attack_base": 18, "attack_growth": 0.05, "defence_base": 4, "defence_per_level": 0.6,
               "speed_base": 10, "speed_per_level": 0.4, "crit_base": 0.06, "trainer_attack_per_level": 0.3},
    # Chronowl's time windows: generous, and missing them only loses a bonus.
    "time_window_seconds": [45, 50, 60, 70, 80],
    "trainer": {"xp_first_level": 150, "xp_growth": 1.3, "member_exp_share": 0.35},
    # Sprite animation speed (frames per second per animation; speed_scale multiplies them all).
    "animation": {"idle_fps": 5, "walk_fps": 8, "attack_fps": 9, "speed_scale": 1.0},
}


def _merge(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def load_balance(path=None):
    data = copy.deepcopy(DEFAULTS)
    path = path or BALANCE_PATH
    try:
        with open(path, encoding="utf-8") as handle:
            _merge(data, json.load(handle))
    except FileNotFoundError:
        pass
    return data


BALANCE = load_balance()

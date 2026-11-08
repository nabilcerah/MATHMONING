"""GDD 7.4, 7.6, 7.10 and 9.1 as small pure functions. All numbers come from data/rules.json."""
from monsters.monster_data import rules

# How a question was answered. The battle screen reports one of these.
FIRST_TRY = "first_try"            # right on the first attempt, no hint
AFTER_HINT = "after_hint"          # right on the first attempt after asking for a hint
SECOND_ATTEMPT = "second_attempt"  # right on the second attempt
FAILED = "failed"                  # wrong after both attempts
OUTCOMES = (FIRST_TRY, AFTER_HINT, SECOND_ATTEMPT, FAILED)


def answer_multiplier(outcome):
    return float(rules()["answer_multipliers"][outcome])


def learning_score(outcome, worked_example=False):
    """GDD 9.4: 1.0 unaided, 0.75 after a hint, 0.5 after a worked example, 0 when wrong."""
    scores = rules()["learning_scores"]
    if outcome == FAILED:
        return float(scores["failed"])
    if worked_example:
        return float(scores["worked_example"])
    return float(scores[outcome])


def outcome_for(correct, attempts_used, used_hint):
    if not correct:
        return FAILED
    if attempts_used >= 2:
        return SECOND_ATTEMPT
    return AFTER_HINT if used_hint else FIRST_TRY


def escape_chance(player_speed, enemy_speed):
    """Escape Chance = 50 + 3 x (Player Speed - Enemy Speed), clamped to 20-90 (percent)."""
    cfg = rules()["escape"]
    chance = cfg["base"] + cfg["per_speed"] * (player_speed - enemy_speed)
    return max(cfg["min"], min(cfg["max"], chance))


def battle_exp(enemy_level, boss=False):
    """EXP Reward = 20 + 5 x Enemy Level (bosses use the configured multiplier)."""
    cfg = rules()["exp"]
    exp = cfg["battle_base"] + cfg["battle_per_level"] * int(enemy_level)
    return round(exp * (cfg["boss_multiplier"] if boss else 1))


def shared_exp(amount):
    """Reserve party members train alongside the active monster: 35% of the battle EXP."""
    return round(amount * rules()["exp"]["shared_fraction"])


def capture_exp(enemy_level):
    cfg = rules()["exp"]
    return cfg["capture_base"] + cfg["capture_per_level"] * int(enemy_level)


def battle_coins(enemy_level, boss=False):
    cfg = rules()["coins"]
    return cfg["battle_base"] + cfg["battle_per_level"] * int(enemy_level) + (cfg["boss_bonus"] if boss else 0)


def max_focus():
    return int(rules()["focus"]["max"])


def focus_gain():
    return int(rules()["focus"]["gain_on_correct_normal"])

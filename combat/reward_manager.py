"""GDD 9.1: battle EXP goes 100% to the active monster and 35% to the other healthy party members."""
from combat import battle_rules


def distribute_exp(party_monsters, active, amount):
    """Returns [(monster, exp_gained, level_ups)] for everyone who received EXP."""
    results = []
    for monster in party_monsters:
        if monster.fainted:
            continue
        gained = amount if monster is active else battle_rules.shared_exp(amount)
        if gained <= 0:
            continue
        results.append((monster, gained, monster.add_exp(gained)))
    return results

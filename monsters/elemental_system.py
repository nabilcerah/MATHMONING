"""GDD 5: the Crystal > Time > Dark > Earth > Crystal cycle. Only the battle engine calls this."""
from monsters.monster_data import elements


def effectiveness(attacker_element, defender_element):
    """'super', 'weak' or 'neutral' for an attack of ``attacker_element`` hitting ``defender_element``."""
    beats = elements()["beats"]
    if beats.get(attacker_element) == defender_element:
        return "super"
    if beats.get(defender_element) == attacker_element:
        return "weak"
    return "neutral"


def multiplier(attacker_element, defender_element):
    return float(elements()["multipliers"][effectiveness(attacker_element, defender_element)])


def message(attacker_element, defender_element):
    return elements()["messages"][effectiveness(attacker_element, defender_element)]


def strong_against(element):
    """The element ``element`` is super effective against."""
    return elements()["beats"].get(element, "")


def weak_against(element):
    """The element that is super effective against ``element``."""
    for attacker, target in elements()["beats"].items():
        if target == element:
            return attacker
    return ""


def color(element):
    return tuple(elements()["colors"].get(element, (220, 220, 220)))

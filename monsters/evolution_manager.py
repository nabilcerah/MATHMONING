"""GDD 9.5: evolution needs BOTH a combat level and mastery of the monster's maths topic.

Evolution is never automatic: ``check`` tells the shrine what is still missing, ``preview`` shows
what would change, and ``evolve`` applies it when the player chooses to.
"""
from dataclasses import dataclass, field

from monsters.monster_data import has_species, rules, species


@dataclass(frozen=True)
class EvolutionCheck:
    eligible: bool
    target: str                     # species id of the next stage ("" if none)
    requirements: list = field(default_factory=list)   # [(label, met)]

    @property
    def missing(self):
        return [label for label, met in self.requirements if not met]


def requirements_for(monster):
    cfg = dict(rules()["evolution"])
    cfg.update({k: v for k, v in monster.spec.evolution.items() if k in cfg})
    return cfg


def check(monster, profile):
    """``profile`` maps topic -> {"mastery": 0-100, "evidence": n}."""
    target = monster.spec.evolution.get("into", "")
    if not target or not has_species(target):
        return EvolutionCheck(False, "", [("This monster has no further stage yet.", False)])
    cfg = requirements_for(monster)
    topic = monster.mastery_topic
    stats = profile.get(topic, {})
    mastery, evidence = int(stats.get("mastery", 0)), int(stats.get("evidence", 0))
    label = topic.replace("_", " ").title()
    requirements = [
        (f"Level {cfg['min_level']} (now {monster.level})", monster.level >= cfg["min_level"]),
        (f"{label} mastery {cfg['min_mastery']} (now {mastery})", mastery >= cfg["min_mastery"]),
        (f"{cfg['min_evidence']} {label} questions answered (now {evidence})", evidence >= cfg["min_evidence"]),
    ]
    return EvolutionCheck(all(met for _, met in requirements), target, requirements)


def preview(monster):
    """What evolving would change: stats at the current level, and moves gained or lost."""
    target = species(monster.spec.evolution["into"])
    new_stats = target.stats_at(monster.level)
    old_stats = {"hp": monster.max_hp, "attack": monster.attack, "defence": monster.defence, "speed": monster.speed}
    old_moves, new_moves = set(monster.spec.moves), set(target.moves)
    return {
        "from": monster.spec, "to": target,
        "stats": {stat: (old_stats[stat], max(old_stats[stat], new_stats[stat])) for stat in old_stats},
        "gained_moves": [m for m in target.moves if m not in old_moves],
        "lost_moves": [m for m in monster.spec.moves if m not in new_moves],
        "power_bonus": target.power_bonus,
    }


def evolve(monster):
    """Turn ``monster`` into its next stage in place. Level, EXP and learning records are kept;
    stats rise to the new stage's values (never fall); current HP rises with max HP."""
    info = preview(monster)
    target = info["to"]
    stats = info["stats"]
    hp_gain = stats["hp"][1] - monster.max_hp
    monster.species_id = target.species_id
    monster.evolution_stage = target.stage
    monster.max_hp = stats["hp"][1]
    if not monster.fainted:
        monster.hp = min(monster.max_hp, monster.hp + hp_gain)
    monster.attack, monster.defence, monster.speed = stats["attack"][1], stats["defence"][1], stats["speed"][1]
    return info

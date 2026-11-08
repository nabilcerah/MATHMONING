"""A monster the player owns (or a wild/boss monster in battle): one row of the MONSTERS table."""
from dataclasses import dataclass

from monsters.monster_data import rules, species


def exp_to_next(level):
    """GDD 9.1: EXP Required = 60 + 20 x (Current Level - 1)."""
    exp = rules()["exp"]
    return exp["level_base"] + exp["level_step"] * (max(1, int(level)) - 1)


def max_level():
    return rules()["exp"]["max_level"]


@dataclass
class Monster:
    species_id: str
    level: int = 1
    exp: int = 0
    hp: int = 1
    max_hp: int = 1
    attack: int = 1
    defence: int = 1
    speed: int = 1
    evolution_stage: int = 1
    instance_id: int = None
    acquired_at: str = ""

    # ------------------------------------------------------------------ views
    @property
    def spec(self):
        return species(self.species_id)

    @property
    def name(self):
        return self.spec.name

    @property
    def element(self):
        return self.spec.element

    @property
    def mastery_topic(self):
        return self.spec.mastery_topic

    @property
    def fainted(self):
        return self.hp <= 0

    @property
    def next_level_exp(self):
        return exp_to_next(self.level)

    @property
    def at_max_level(self):
        return self.level >= max_level()

    def moves(self):
        return self.spec.move_list()

    # ------------------------------------------------------------------ changes
    def add_exp(self, amount):
        """Add EXP and level up as often as it allows. Returns a list of level-ups
        (each {"level", "gains"}), which is truthy when the monster levelled."""
        levels = []
        if self.at_max_level:
            self.exp = 0
            return levels
        self.exp += max(0, int(amount))
        while not self.at_max_level and self.exp >= self.next_level_exp:
            self.exp -= self.next_level_exp
            levels.append(self.level_up())
        if self.at_max_level:
            self.exp = 0
        return levels

    def level_up(self):
        """GDD 9.2: grow stats by the species' growth; current HP rises with max HP."""
        before = self.spec.stats_at(self.level)
        self.level += 1
        after = self.spec.stats_at(self.level)
        gains = {stat: after[stat] - before[stat] for stat in after}
        self.max_hp += gains["hp"]
        self.hp = min(self.max_hp, self.hp + gains["hp"]) if self.hp > 0 else self.hp
        self.attack += gains["attack"]
        self.defence += gains["defence"]
        self.speed += gains["speed"]
        return {"level": self.level, "gains": gains}

    def heal(self, amount):
        """Restore up to ``amount`` HP (not to fainted monsters). Returns HP restored."""
        if self.fainted:
            return 0
        healed = max(0, min(int(amount), self.max_hp - self.hp))
        self.hp += healed
        return healed

    def revive(self, fraction):
        if not self.fainted:
            return 0
        self.hp = max(1, round(self.max_hp * fraction))
        return self.hp

    def restore(self):
        self.hp = self.max_hp

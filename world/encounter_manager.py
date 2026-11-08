"""GDD 10.3: random encounters. ~8% per eligible step in encounter grass, a 7-step cooldown after
every battle, region tables with weights (rare monsters have low weights) and region level ranges.
Never in safe areas (the village and building interiors), menus, dialogue or boss arenas."""
from monsters.monster_data import encounters


class EncounterManager:
    def __init__(self, rng):
        self.rng = rng
        cfg = encounters()
        self.chance = float(cfg["step_chance"])
        self.cooldown_steps = int(cfg["cooldown_steps"])
        self.cooldown = 0

    @staticmethod
    def table(area_id):
        cfg = encounters()
        return cfg["areas"].get(area_id) or cfg["areas"][cfg["default_area"]]

    @staticmethod
    def is_safe(area_id):
        return area_id in encounters()["safe_areas"] or area_id not in encounters()["areas"]

    def after_battle(self):
        self.cooldown = self.cooldown_steps

    def step(self, area_id, in_grass, blocked=False):
        """Call once per tile walked. Returns True when a wild monster appears."""
        if self.cooldown:
            self.cooldown -= 1
            return False
        if blocked or not in_grass or self.is_safe(area_id):
            return False
        return self.rng.random() < self.chance

    def pick(self, area_id, exclude_rare=False):
        """(species_id, level) for ``area_id``."""
        table = self.table(area_id)
        entries = [(species, weight) for species, weight in table["table"] if weight > 0]
        if exclude_rare:
            common = [(s, w) for s, w in entries if w > 5]
            entries = common or entries
        species = self.rng.choices([s for s, _ in entries], weights=[w for _, w in entries])[0]
        low, high = table["levels"]
        return species, self.rng.randint(low, high)

"""Creates monster instances from species data."""
from monsters.monster import Monster, max_level
from monsters.monster_data import species


def create(species_id, level=1):
    """A fresh monster of ``species_id`` at ``level`` with full HP."""
    spec = species(species_id)
    level = max(1, min(max_level(), int(level)))
    stats = spec.stats_at(level)
    return Monster(species_id, level, 0, stats["hp"], stats["hp"], stats["attack"], stats["defence"],
                   stats["speed"], spec.stage)

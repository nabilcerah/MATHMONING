"""Loads the game's configurable data (data/*.json) once and exposes typed views of it.

Nothing here imports pygame, so every rule module (and its tests) can use the data directly.
"""
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from config import ROOT

DATA_DIR = ROOT / "data"
SPRITE_DIR = ROOT / "assets" / "sprites" / "monsters"


@lru_cache(maxsize=None)
def load(name):
    """Parsed contents of data/<name>.json (cached; the files are read-only at runtime)."""
    with open(Path(DATA_DIR) / f"{name}.json", encoding="utf-8") as handle:
        return json.load(handle)


def rules():
    return load("rules")


def elements():
    return load("elements")


def items():
    return load("items")["items"]


def shop_stock():
    return list(load("items")["shop"])


def quests():
    return load("quests")["quests"]


def challenges():
    return load("quests")["challenges"]


def encounters():
    return load("encounters")


@dataclass(frozen=True)
class Move:
    move_id: str
    name: str
    element: str
    topic: str
    power: int
    focus: int
    kind: str              # "normal", "special" or "support"
    description: str = ""
    effect: str = ""       # "shield", "debuff", "delay" for support moves

    @property
    def damaging(self):
        return self.power > 0 and self.kind != "support"


@lru_cache(maxsize=None)
def move(move_id):
    raw = load("moves")["moves"][move_id]
    return Move(move_id, raw["name"], raw["element"], raw["topic"], int(raw["power"]), int(raw["focus"]),
                raw["kind"], raw.get("description", ""), raw.get("effect", ""))


def all_moves():
    return {move_id: move(move_id) for move_id in load("moves")["moves"]}


def _sprite_exists(name):
    return bool(name) and (Path(SPRITE_DIR) / name / "manifest.json").exists()


@dataclass(frozen=True)
class Species:
    """One monster species. The display fields (sprite, size, shape, base, accent) are what
    ``game.creatures.draw_creature`` needs, so a Species can be drawn directly."""
    species_id: str
    name: str
    element: str
    role: str
    stage: int
    stats: dict
    growth: dict
    topics: tuple
    mastery_topic: str
    moves: tuple
    description: str = ""
    title: str = ""
    passive: dict = field(default_factory=dict)
    evolution: dict = field(default_factory=dict)
    evolves_from: str = ""
    power_bonus: int = 0
    boss: bool = False
    appearance: tuple = ()
    sprite: str = ""
    size: float = 1.0
    base: tuple = (120, 120, 160)
    accent: tuple = (220, 220, 240)
    shape: str = "blob"

    # Compatibility with code written for the old CreatureSpec.
    @property
    def topic(self):
        return self.mastery_topic

    @property
    def blurb(self):
        return self.description

    @property
    def hp(self):
        return self.stats["hp"]

    @property
    def attack(self):
        return self.stats["attack"]

    @property
    def display_name(self):
        return self.title or self.name

    def move_list(self):
        return [move(move_id) for move_id in self.moves]

    def stats_at(self, level):
        """Stats at ``level``: level-one stats plus growth for every level after the first."""
        level = max(1, int(level))
        return {stat: int(self.stats[stat] + self.growth.get(stat, 0) * (level - 1))
                for stat in ("hp", "attack", "defence", "speed")}


@lru_cache(maxsize=None)
def species(species_id):
    raw = load("monsters")["species"][species_id]
    sprite = raw.get("sprite", "")
    if not _sprite_exists(sprite):
        sprite = raw.get("base_sprite", "") if _sprite_exists(raw.get("base_sprite", "")) else ""
    colors = raw.get("colors", {})
    return Species(
        species_id, raw["name"], raw["element"], raw.get("role", ""), int(raw.get("stage", 1)),
        dict(raw["stats"]), dict(raw.get("growth", {})), tuple(raw.get("topics", ())), raw.get("mastery_topic", ""),
        tuple(raw.get("moves", ())), raw.get("description", ""), raw.get("title", ""), dict(raw.get("passive", {})),
        dict(raw.get("evolution", {})), raw.get("evolves_from", ""), int(raw.get("power_bonus", 0)),
        bool(raw.get("boss", False)), tuple(raw.get("appearance", ())), sprite, float(raw.get("size", 1.0)),
        tuple(colors.get("base", (120, 120, 160))), tuple(colors.get("accent", (220, 220, 240))))


def species_ids():
    return tuple(load("monsters")["species"])


def starter_ids():
    return tuple(load("monsters")["starters"])


def has_species(species_id):
    return species_id in load("monsters")["species"]


# Saves made before the GDD rebuild used these ids for evolved starters.
LEGACY_SPECIES = {"PYRONYX": "PYRON", "AQUACREST": "AQUABIT", "PYROX": "PYRON", "TERRABIT": "GEOMAX",
                  "TERRAVOLT": "GEOMAX"}


def canonical_species(species_id):
    species_id = LEGACY_SPECIES.get(species_id, species_id)
    return species_id if has_species(species_id) else "FRACTELLA"

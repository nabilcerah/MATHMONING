"""Load monster definitions from ``data/monsters/*.json`` and turn them into battle stats.

Adding a monster means adding one JSON file (and optionally a sprite folder); the engine does
not change. ``base_stats`` are the monster's numbers *at its reference ``level``*; other levels
scale with the formulas below, so nothing has to be hand-tuned per level.
"""
import json
from dataclasses import dataclass, field

from battle_engine.balance import BALANCE
from battle_engine.tiers import tier_by_id, tier_for_level
from config import ROOT

MONSTER_DIR = ROOT / "data" / "monsters"


@dataclass(frozen=True)
class AbilityDef:
    id: str
    name: str
    type: str                      # attack | charge | multistage | special | defend | counter
    power: float = 1.0
    cooldown: int = 0
    charge_turns: int = 1
    stages: tuple = ()             # multistage: ({"name", "text", "power"}, ...)
    effect: str = ""               # special/defend: the mechanic effect it triggers
    min_tier: str = "common"
    hp_below: float = 1.0          # only usable at or below this HP fraction
    phases: tuple = ()             # only usable in these phase ids (empty = any)
    interrupt_topics: tuple = ()   # questions that interrupt it (default: the monster's weakness)
    stun_on_interrupt: int = 1
    hits: int = 1
    description: str = ""
    warning: str = ""


@dataclass(frozen=True)
class MonsterDef:
    id: str
    name: str
    sprite: str
    level: int
    rarity: str
    element: str
    math_speciality: str
    weakness: tuple
    resistance: tuple
    base_stats: dict
    abilities: tuple
    mechanics: tuple = ()
    question_topics: tuple = ()
    phases: tuple = ()
    behaviour: dict = field(default_factory=dict)
    description: str = ""
    special_ability: str = ""
    defence_style: str = ""
    boss: bool = False
    color: tuple = (200, 200, 220)
    unlock: dict = field(default_factory=dict)
    min_rank: int = 1

    def ability(self, ability_id):
        return next((a for a in self.abilities if a.id == ability_id), None)


@dataclass
class MonsterStats:
    level: int
    max_hp: int
    attack: int
    defence: int
    speed: int
    crit_chance: float
    special_power: int
    exp_reward: int
    tier_id: str


def _ability(raw):
    return AbilityDef(
        raw["id"], raw.get("name", raw["id"].replace("_", " ").title()), raw.get("type", "attack"),
        float(raw.get("power", 1.0)), int(raw.get("cooldown", 0)), int(raw.get("charge_turns", 1)),
        tuple(raw.get("stages", ())), raw.get("effect", ""), raw.get("min_tier", "common"),
        float(raw.get("hp_below", 1.0)), tuple(raw.get("phases", ())), tuple(raw.get("interrupt_topics", ())),
        int(raw.get("stun_on_interrupt", 1)), int(raw.get("hits", 1)), raw.get("description", ""),
        raw.get("warning", ""))


def parse_monster(raw):
    return MonsterDef(
        raw["id"], raw["name"], raw.get("sprite", raw["id"].upper()), int(raw.get("level", 10)),
        raw.get("rarity", "common"), raw.get("element", ""), raw.get("math_speciality", ""),
        tuple(raw.get("weakness", ())), tuple(raw.get("resistance", ())), dict(raw["base_stats"]),
        tuple(_ability(a) for a in raw.get("abilities", ())), tuple(raw.get("mechanics", ())),
        tuple(raw.get("question_topics", ())), tuple(raw.get("phases", ())), dict(raw.get("behaviour", {})),
        raw.get("description", ""), raw.get("special_ability", ""), raw.get("defence_style", ""),
        bool(raw.get("boss", False)), tuple(raw.get("color", (200, 200, 220))), dict(raw.get("unlock", {})),
        int(raw.get("min_rank", 1)))


_CACHE = {}


def load_all(directory=None):
    directory = directory or MONSTER_DIR
    key = str(directory)
    if key not in _CACHE:
        monsters = {}
        for path in sorted(directory.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            monsters[raw["id"]] = parse_monster(raw)
        _CACHE[key] = dict(sorted(monsters.items(), key=lambda item: (item[1].boss, item[1].level, item[0])))
    return _CACHE[key]


def get(monster_id):
    return load_all()[monster_id]


def _scaled(base, growth, level, reference):
    return base * (1 + growth * (level - 1)) / (1 + growth * (reference - 1))


def build_stats(defn, level, balance=None):
    """Balanced stats for ``defn`` at ``level``: reference stats x level growth x tier multiplier."""
    balance = balance or BALANCE
    level = max(1, int(level))
    growth = balance["growth"]
    tier, home = tier_for_level(level, balance), tier_for_level(defn.level, balance)
    rarity = tier.stat_mult / home.stat_mult  # the JSON numbers already include the home tier
    base = defn.base_stats

    def stat(name):
        return _scaled(base[name], growth.get(name, 0.03), level, defn.level) * rarity

    speed = round(_scaled(base.get("speed", 10), growth["speed"], level, defn.level))
    crit = balance["crit"]
    crit_chance = min(crit["cap"], crit["base"] + speed * crit["per_speed"])
    attack = round(stat("attack"))
    exp = (balance["exp"]["base"] + balance["exp"]["per_level"] * level) * tier.exp_mult
    if defn.boss:
        exp *= balance["exp"]["boss_mult"]
    return MonsterStats(level, max(10, round(stat("hp") * balance.get("monster_hp_mult", 1.0))), max(1, attack), max(0, round(stat("defence"))), speed,
                        round(crit_chance, 3), round(attack * balance["special_power"]), round(exp), tier.id)


def tier_allows(defn_tier_id, current_tier_id, balance=None):
    """True when ``current_tier_id`` is at least ``defn_tier_id`` (ability/mechanic gating)."""
    return tier_by_id(current_tier_id, balance).rank >= tier_by_id(defn_tier_id, balance).rank

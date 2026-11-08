"""The five monster tiers: Common 1-9, Uncommon 10-20, Rare 21-35, Epic 36-49, Mythical 50+."""
from dataclasses import dataclass

from battle_engine.balance import BALANCE


@dataclass(frozen=True)
class Tier:
    id: str
    name: str
    min_level: int
    max_level: int
    question_level: int
    stat_mult: float
    exp_mult: float
    color: tuple
    rank: int  # 1..5

    @property
    def difficulty_name(self):
        return ("Beginner", "Easy-Intermediate", "Intermediate", "Advanced", "Expert")[self.rank - 1]


def tiers(balance=None):
    rows = (balance or BALANCE)["tiers"]
    return [Tier(r["id"], r["name"], r["min_level"], r["max_level"], r["question_level"], r["stat_mult"],
                 r["exp_mult"], tuple(r["color"]), index + 1) for index, r in enumerate(rows)]


def tier_for_level(level, balance=None):
    level = max(1, int(level))
    found = tiers(balance)[0]
    for tier in tiers(balance):
        if level >= tier.min_level:
            found = tier
    return found


def tier_by_id(tier_id, balance=None):
    for tier in tiers(balance):
        if tier.id == tier_id:
            return tier
    raise KeyError(tier_id)


def tier_rank(tier_id, balance=None):
    return tier_by_id(tier_id, balance).rank


def level_for_rank(rank, player_level, balance=None):
    """The level a monster fights at for a chosen tier: a little above the player, inside the tier."""
    tier = tiers(balance)[max(1, min(5, rank)) - 1]
    return max(tier.min_level, min(tier.max_level, int(player_level) + 2))

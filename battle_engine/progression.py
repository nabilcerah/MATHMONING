"""Trainer progression, the monster collection and rewards.

- Trainer XP / level: earned from every advanced battle (more for wins, something for trying).
  Trainer levels unlock skills (battle_engine/skills.py) and add a little attack.
- Monster records: each monster has a mastery rank 0..5. Beating it at rank r unlocks rank r+1,
  so the same monster returns in a stronger tier (its upgrade path) with harder maths and more
  abilities. Rank 0 means "not collected yet".
- Unlocks: a monster's JSON may require other monsters to be beaten first (Infinity Zero).
- Rewards: boss and first-clear bonuses give items; the fighting team member gets EXP too.

Everything here is pure except ``ProgressStore``, which reads and writes the save file.
"""
from dataclasses import dataclass, field

from battle_engine.balance import BALANCE
from battle_engine.skills import newly_unlocked
from battle_engine.tiers import tiers

RANK_NAMES = ("Not collected", "Common", "Uncommon", "Rare", "Epic", "Mythical")


def xp_to_next(level, balance=None):
    trainer = (balance or BALANCE)["trainer"]
    return round(trainer["xp_first_level"] * trainer["xp_growth"] ** (max(1, level) - 1))


@dataclass
class Trainer:
    xp: int = 0
    level: int = 1

    @property
    def next_level_xp(self):
        return xp_to_next(self.level)

    def add_xp(self, amount):
        """Returns how many levels were gained."""
        self.xp += max(0, int(amount))
        gained = 0
        while self.xp >= self.next_level_xp:
            self.xp -= self.next_level_xp
            self.level += 1
            gained += 1
        return gained


def new_record(monster_id):
    return {"monster_id": monster_id, "rank": 0, "wins": 0, "losses": 0, "best_turns": 0}


def available_ranks(defn, record):
    """Ranks the player may challenge: from the monster's minimum up to one above its best."""
    low = max(1, defn.min_rank)
    high = min(5, max(low, record.get("rank", 0) + 1))
    return list(range(low, high + 1))


def collected_count(records, exclude=None):
    return sum(1 for monster_id, record in records.items() if record.get("wins") and monster_id != exclude)


def is_unlocked(defn, records):
    need = int(defn.unlock.get("defeated_monsters", 0))
    return collected_count(records, defn.id) >= need


def unlock_text(defn, records):
    need = int(defn.unlock.get("defeated_monsters", 0))
    have = collected_count(records, defn.id)
    return f"Defeat {need} different monsters to unlock ({have}/{need})." if have < need else ""


@dataclass
class Reward:
    won: bool
    trainer_xp: int = 0
    member_exp: int = 0
    trainer_levels: int = 0
    new_skills: list = field(default_factory=list)
    items: dict = field(default_factory=dict)
    rank_up: int = 0           # the new mastery rank, or 0
    first_clear: bool = False
    lines: list = field(default_factory=list)


def battle_reward(engine, rank, record, trainer, balance=None):
    """Work out (and apply to ``record`` / ``trainer``) what a finished battle earns."""
    balance = balance or BALANCE
    won = engine.outcome == "won"
    correct = sum(1 for _, ok in engine.answers if ok)
    reward = Reward(won)
    if won:
        reward.first_clear = record["wins"] == 0
        base = engine.stats.exp_reward
        reward.trainer_xp = round(base * (1.5 if reward.first_clear else 1.0)) + 2 * correct
        record["wins"] += 1
        turns = engine.turn or 1
        record["best_turns"] = turns if not record.get("best_turns") else min(record["best_turns"], turns)
        if rank > record["rank"]:
            record["rank"] = rank
            reward.rank_up = rank
            reward.items["Health Potion"] = reward.items.get("Health Potion", 0) + 1
            reward.lines.append(f"MASTERY UP! {engine.name} is now {RANK_NAMES[rank]} rank - "
                                f"{RANK_NAMES[rank + 1] + ' rank unlocked!' if rank < 5 else 'fully mastered!'}")
        if engine.defn.boss:
            reward.items["Learning Crystal"] = reward.items.get("Learning Crystal", 0) + 1
            reward.items["Health Potion"] = reward.items.get("Health Potion", 0) + 2
            reward.lines.append("BOSS REWARD: a Learning Crystal and two Health Potions!")
        if reward.first_clear and engine.tier.rank >= 4:
            reward.items["EXP Booster"] = reward.items.get("EXP Booster", 0) + 1
    else:
        record["losses"] += 1
        reward.trainer_xp = 4 * correct  # trying still teaches something
    reward.member_exp = round(reward.trainer_xp * balance["trainer"]["member_exp_share"])
    old_level = trainer.level
    reward.trainer_levels = trainer.add_xp(reward.trainer_xp)
    reward.new_skills = newly_unlocked(old_level, trainer.level)
    if reward.trainer_levels:
        reward.lines.append(f"TRAINER LEVEL UP! You are now Trainer Lv {trainer.level}.")
    for skill in reward.new_skills:
        reward.lines.append(f"New skill unlocked: {skill.name} - {skill.description}")
    return reward


class ProgressStore:
    """Save-file access for trainer progress and monster records."""

    def __init__(self, repository, player_id):
        self.repository, self.player_id = repository, player_id

    def trainer(self):
        data = self.repository.trainer_progress(self.player_id)
        return Trainer(data["xp"], data["level"])

    def save_trainer(self, trainer):
        self.repository.save_trainer_progress(self.player_id, trainer.xp, trainer.level)

    def records(self):
        return self.repository.monster_records(self.player_id)

    def record(self, monster_id):
        return self.records().get(monster_id) or new_record(monster_id)

    def save_record(self, record):
        self.repository.save_monster_record(self.player_id, record)

    def apply(self, engine, rank):
        """Finish a battle: compute rewards and persist trainer, record and items."""
        trainer, record = self.trainer(), self.record(engine.defn.id)
        reward = battle_reward(engine, rank, record, trainer)
        self.save_trainer(trainer)
        self.save_record(record)
        for item, count in reward.items.items():
            self.repository.add_item(self.player_id, item, count)
        return reward


def tier_name_for_rank(rank):
    return tiers()[max(1, min(5, rank)) - 1].name

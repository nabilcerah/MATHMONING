"""INVENTORY / BAG (GDD 26): items, quantities, descriptions and out-of-battle use."""
from config import PALETTE
from game.ui import meter, panel, text, wrapped
from monsters.monster_data import items as item_data
from states.base import Screen


class InventoryScreen(Screen):
    def __init__(self, game):
        super().__init__(game)
        self.choosing_target = None   # item being used, while picking a monster

    def items(self):
        if self.choosing_target:
            return self.party.party
        bag = self.repo.inventory(self.player_id)
        return [name for name in item_data() if bag.get(name)]

    def rows(self):
        return 34, 16, 6, 160

    def back(self):
        if self.choosing_target:
            self.choosing_target = None
            self.selected = 0
        else:
            self.close()

    def activate(self, index):
        if self.choosing_target:
            self.use_on(self.choosing_target, self.party.party[index])
            return
        name = self.items()[index]
        info = item_data()[name]
        if (info["use"] == "both" and info["effect"] in ("heal", "revive")) or info["use"] == "field":
            self.choosing_target, self.selected = name, 0
            self.notice = f"Use {name} on which monster?"
        elif info["use"] == "battle":
            self.notice = f"{name} can only be used in battle."
        else:
            self.notice = f"{name} is a key item. {info['description']}"

    def tome_exp(self, info):
        """Knowledge Tome: rewards what you have learned - more EXP for every Proficient maths topic."""
        profile = self.repo.learning_profile(self.player_id)
        proficient = sum(1 for stats in profile.values() if stats["mastery"] >= 70 and stats["sufficient"])
        return int(info["base"]) + int(info["per_topic"]) * proficient

    def use_on(self, item, monster):
        info = item_data()[item]
        if info["effect"] == "heal":
            if monster.fainted or monster.hp >= monster.max_hp:
                self.notice = f"{monster.name} doesn't need that."
                return
            if not self.repo.use_item(self.player_id, item):
                return
            healed = monster.heal(round(monster.max_hp * info["amount"]))
            self.notice = f"{monster.name} recovered {healed} HP."
        elif info["effect"] in ("tome", "exp_star"):
            if monster.at_max_level:
                self.notice = f"{monster.name} is already at the top level."
                return
            exp = self.tome_exp(info) if info["effect"] == "tome" else monster.next_level_exp - monster.exp
            if not self.repo.use_item(self.player_id, item):
                return
            levels = monster.add_exp(exp)
            self.notice = f"{monster.name} gained {exp} EXP" + (f" and reached Lv {monster.level}!" if levels else ".")
        else:
            if not monster.fainted:
                self.notice = f"{monster.name} hasn't fainted."
                return
            if not self.repo.use_item(self.player_id, item):
                return
            monster.revive(info["amount"])
            self.notice = f"{monster.name} is back on its feet!"
        self.game.save_party()
        self.choosing_target = None
        self.selected = 0

    def draw(self, surface, frame=0):
        self.draw_frame(surface, "BAG")
        coins = self.repo.coins(self.player_id)
        text(surface, f"NUMERA COINS: {coins}", (314, 28), 10, PALETTE["gold"], align="right")
        if self.choosing_target:
            labels = [f"{m.name} Lv{m.level}  {m.hp}/{m.max_hp}" for m in self.party.party]
            self.draw_list(surface, labels, frame, 34, 16, 6, 160)
            text(surface, f"Use {self.choosing_target} on...", (6, 24 + 2), 9, PALETTE["sky"])
            return
        bag = self.repo.inventory(self.player_id)
        names = self.items()
        if not names:
            text(surface, "Your bag is empty. Visit the shop in Starter Village.", (10, 40), 10, PALETTE["muted"])
            return
        self.draw_list(surface, [f"{n}" for n in names], frame, 34, 16, 6, 160)
        for index, name in enumerate(names):
            text(surface, f"x{bag[name]}", (162, 34 + index * 16), 10, PALETTE["cream"], align="right")
        name = names[min(self.selected, len(names) - 1)]
        info = item_data()[name]
        panel(surface, (172, 34, 142, 120), PALETTE["night"])
        text(surface, name, (178, 38), 11, PALETTE["gold"])
        use = {"battle": "Battle only", "both": "Battle or field", "key": "Key item"}[info["use"]]
        text(surface, use, (178, 52), 9, PALETTE["sky"])
        wrapped(surface, info["description"], (178, 66, 130, 80), 9, PALETTE["white"], 10, 7)
        if self.party.party:
            text(surface, "PARTY", (178, 160), 9, PALETTE["muted"])
            for i, monster in enumerate(self.party.party):
                meter(surface, 178, 172 + i * 10, 80, 5, monster.hp, monster.max_hp, PALETTE["mint"], warn=True)
                text(surface, monster.name[:8], (262, 170 + i * 10), 8, PALETTE["white"])

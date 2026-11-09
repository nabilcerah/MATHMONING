"""PARTY screen (GDD 4.1, 26): three party slots with HP, level, EXP and mastery; ENTER makes the
chosen monster the lead (it battles first). Up to three companions walk behind you on the map:
F toggles whether the chosen one walks with you or rests in its Mathball. From the trainer menu."""
import pygame

from config import PALETTE
from game.ui import meter, text
from monsters.monster_party import PartyError
from states.base import Screen
from states.monster_card import draw_card, element_badge


class PartyScreen(Screen):
    title = "PARTY"

    def __init__(self, game):
        super().__init__(game)
        self.profile = self.repo.learning_profile(self.player_id)

    def items(self):
        return self.party.party

    def rows(self):
        return 34, 30, 6, 140

    def handle_key(self, key, unicode=""):
        if key == pygame.K_f and self.party.party:
            self.toggle_follow(min(self.selected, len(self.party.party) - 1))
        else:
            super().handle_key(key, unicode)

    def following(self, monster):
        world = self.game.world
        return world is None or world.stay_flag(monster) not in world.flags

    def toggle_follow(self, index):
        world = self.game.world
        if world is None:
            return
        monster = self.party.party[index]
        flag = world.stay_flag(monster)
        if self.following(monster):
            world.set_flag(flag)
            self.notice = f"{monster.name} rests in its Mathball."
        else:
            world.clear_flag(flag)
            self.notice = f"{monster.name} walks with you!"

    def activate(self, index):
        if index == 0:
            self.notice = f"{self.party.party[0].name} already leads your party."
            return
        try:
            monster = self.party.set_lead(index)
        except PartyError as error:
            self.notice = str(error)
            return
        self.selected = 0
        self.game.save_party()
        self.notice = f"{monster.name} now leads your party."

    def draw(self, surface, frame=0):
        self.draw_frame(surface, "PARTY", footer="ENTER: MAKE LEAD   F: WALK WITH ME / REST   ESC: BACK")
        for index in range(self.party.max_party):
            y = 34 + index * 30
            chosen = index == self.selected
            from game.ui import panel
            panel(surface, (6, y, 134, 26), PALETTE["deep"] if chosen else PALETTE["night"],
                  PALETTE["gold"] if chosen else None)
            if index >= len(self.party.party):
                text(surface, "- empty slot -", (14, y + 9), 9, PALETTE["muted"])
                continue
            monster = self.party.party[index]
            text(surface, f"{index + 1}. {monster.name}", (12, y + 4), 10, PALETTE["gold"] if chosen else PALETTE["white"])
            text(surface, f"Lv {monster.level}", (134, y + 4), 9, PALETTE["cream"], align="right")
            meter(surface, 12, y + 16, 52, 5, monster.hp, monster.max_hp, PALETTE["mint"], warn=True)
            element_badge(surface, monster.element, (96, y + 15), 38)
            if index == 0:
                text(surface, "LEAD", (110, y + 5), 7, PALETTE["gold"], align="right")
            walking = self.following(monster)
            text(surface, "WALKS" if walking else "REST", (67, y + 14), 7,
                 PALETTE["mint"] if walking else PALETTE["muted"])
        text(surface, f"Sanctuary: {len(self.party.storage)}/{self.party.capacity}", (8, 128), 9, PALETTE["muted"])
        if self.party.party:
            monster = self.party.party[min(self.selected, len(self.party.party) - 1)]
            draw_card(surface, monster, (146, 30, 168, 186), self.profile, frame)

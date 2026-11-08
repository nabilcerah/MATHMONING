"""PARTY screen (GDD 4.1, 26): three party slots with HP, level, EXP and mastery; ENTER makes the
chosen monster the lead (it battles first and follows you). Available from the trainer menu."""
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
        self.draw_frame(surface, "PARTY", footer="ENTER: MAKE LEAD   ESC: BACK   (Swap with stored monsters at the Sanctuary)")
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
            meter(surface, 12, y + 16, 80, 5, monster.hp, monster.max_hp, PALETTE["mint"], warn=True)
            element_badge(surface, monster.element, (96, y + 15), 38)
            if index == 0:
                text(surface, "LEAD", (110, y + 5), 7, PALETTE["gold"], align="right")
        text(surface, f"Sanctuary: {len(self.party.storage)}/{self.party.capacity}", (8, 128), 9, PALETTE["muted"])
        if self.party.party:
            monster = self.party.party[min(self.selected, len(self.party.party) - 1)]
            draw_card(surface, monster, (146, 30, 168, 186), self.profile, frame)

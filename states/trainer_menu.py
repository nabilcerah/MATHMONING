"""The TRAINER MENU (TAB): party, bag, quests, MathDex, learning profile and save."""
import pygame

from config import PALETTE
from game.ui import menu, panel, text
from states.base import Screen

CHOICES = ("PARTY", "BAG", "QUESTS", "CODEX", "MATHDEX", "PROFILE", "SAVE", "CLOSE")
RECT = (214, 24, 100, 127)


class TrainerMenu(Screen):
    opaque = False

    def items(self):
        return CHOICES

    def rows(self):
        return RECT[1] + 5, 15, RECT[0], RECT[0] + RECT[2]

    def handle_key(self, key, unicode=""):
        if key == pygame.K_TAB:
            self.close()
            return
        super().handle_key(key, unicode)

    def activate(self, index):
        choice = CHOICES[index]
        if choice in ("CLOSE",):
            self.close()
        elif choice == "SAVE":
            self.game.save_all()
            self.notice = "Saved!"
        else:
            self.game.open_screen(choice.lower())

    def draw(self, surface, frame=0):
        menu(surface, RECT, CHOICES, self.selected, 11, frame)
        coins = self.game.repository.coins(self.game.player.player_id)
        panel(surface, (214, 156, 100, 42), PALETTE["night"])
        text(surface, self.game.player.name[:12], (220, 159), 9, PALETTE["white"])
        text(surface, f"{coins} coins", (220, 170), 9, PALETTE["gold"])
        if self.game.story:
            chapter = self.game.story.chapter()
            text(surface, chapter["number"][:14], (220, 181), 8, PALETTE["sky"])
        if self.notice:
            text(surface, self.notice, (264, 206), 9, PALETTE["mint"], center=True)

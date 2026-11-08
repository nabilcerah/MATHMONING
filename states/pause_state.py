"""PAUSE (GDD 26): Resume, Save, Settings, Main Menu."""
from config import PALETTE
from game import ui
from game.ui import menu, text
from states.base import Screen

CHOICES = ("RESUME", "SAVE", "SETTINGS", "MAIN MENU")
RECT = (100, 70, 120, 72)


class PauseScreen(Screen):
    opaque = False

    def items(self):
        return CHOICES

    def rows(self):
        return RECT[1] + 5, 15, RECT[0], RECT[0] + RECT[2]

    def activate(self, index):
        choice = CHOICES[index]
        if choice == "RESUME":
            self.close()
        elif choice == "SAVE":
            self.game.save_all()
            self.notice = "Game saved."
        elif choice == "SETTINGS":
            self.game.scanlines = not self.game.scanlines
            self.notice = "Scanlines " + ("on." if self.game.scanlines else "off.") + "  F11: fullscreen"
        else:
            self.game.save_all()
            self.close("main_menu")

    def draw(self, surface, frame=0):
        shade = __import__("pygame").Surface(surface.get_size(), __import__("pygame").SRCALPHA)
        shade.fill((*PALETTE["ink"], 170))
        surface.blit(shade, (0, 0))
        ui.begin_frame()
        text(surface, "PAUSED", (160, 56), 18, PALETTE["gold"], center=True)
        menu(surface, RECT, CHOICES, self.selected, 11, frame)
        text(surface, self.notice or "Your progress also saves automatically.", (160, 156), 9, PALETTE["cream"], center=True)
        text(surface, "ESC: RESUME", (160, 170), 9, PALETTE["muted"], center=True)

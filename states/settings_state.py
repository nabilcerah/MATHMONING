"""SETTINGS (from the title screen and the pause menu): sound on/off, music volume, sound-effect
volume and the scanline effect. LEFT/RIGHT (or tapping the < > ends of a slider) changes a volume;
ENTER switches an option. Everything is saved straight away (game/settings.py)."""
import pygame

from config import PALETTE
from game import audio, settings as store, ui
from game.ui import cursor, panel, text
from states.base import CONFIRM, LEFT, RIGHT, Screen

ROWS = ("sound", "music", "sfx", "scanlines", "back")
TOP, ROW_H, X0, X1 = 70, 22, 40, 280


class SettingsScreen(Screen):
    title = "SETTINGS"

    def __init__(self, game):
        super().__init__(game)
        self.folder = getattr(game, "settings_folder", None)
        self.values = store.load(self.folder)
        store.apply(game, self.values)

    def items(self):
        return ROWS

    def rows(self):
        return TOP, ROW_H, X0, X1

    # ------------------------------------------------------------------ changes
    def change(self, row, step):
        if row in ("music", "sfx"):
            self.values[row] = max(0, min(10, self.values[row] + step))
        elif row in ("sound", "scanlines"):
            self.values[row] = not self.values[row]
        store.apply(self.game, self.values)
        store.save(self.values, self.folder)
        if row == "sfx" or (row == "sound" and self.values["sound"]):
            audio.play("select")             # hear the new level straight away

    def activate(self, index):
        row = ROWS[index]
        if row == "back":
            self.close()
        elif row in ("music", "sfx"):
            self.change(row, 1 if self.values[row] < 10 else -10)
        else:
            self.change(row, 0)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = ui.to_virtual(event.pos)
            index = ui.row_index(TOP, ROW_H, len(ROWS), (x, y), X0, X1)
            if index is not None:
                self.selected = index
                row = ROWS[index]
                if row in ("music", "sfx"):
                    self.change(row, -1 if x < 200 else 1)   # left half: quieter, right half: louder
                else:
                    self.activate(index)
            return
        super().handle_event(event)

    def handle_key(self, key, unicode=""):
        row = ROWS[self.selected]
        if key in LEFT and row != "back":
            self.change(row, -1)
        elif key in RIGHT and row != "back":
            self.change(row, 1)
        elif key == pygame.K_ESCAPE:
            self.close()
        else:
            super().handle_key(key, unicode)

    # ------------------------------------------------------------------ drawing
    def draw(self, surface, frame=0):
        self.draw_frame(surface, "SETTINGS", footer="UP/DOWN: CHOOSE   LEFT/RIGHT: VOLUME   ENTER: SWITCH   ESC: BACK")
        labels = {"sound": "SOUND", "music": "MUSIC VOLUME", "sfx": "SOUND EFFECTS", "scanlines": "SCANLINE EFFECT",
                  "back": "BACK"}
        panel(surface, (X0 - 8, TOP - 10, X1 - X0 + 16, ROW_H * len(ROWS) + 14), PALETTE["night"], PALETTE["gold"])
        for index, row in enumerate(ROWS):
            y = TOP + index * ROW_H
            chosen = index == self.selected
            if chosen:
                pygame.draw.rect(surface, PALETTE["deep"], (X0 - 4, y - 3, X1 - X0 + 8, ROW_H - 4))
                cursor(surface, X0 - 2, y + 4, PALETTE["gold"], frame)
            color = PALETTE["gold"] if chosen else PALETTE["white"]
            text(surface, labels[row], (X0 + 10, y + 1), 10, color)
            if row in ("sound", "scanlines"):
                on = self.values[row]
                text(surface, "ON" if on else "OFF", (X1 - 6, y + 1), 10, PALETTE["mint"] if on else PALETTE["coral"],
                     align="right")
            elif row in ("music", "sfx"):
                muted = not self.values["sound"]
                level = self.values[row]
                text(surface, "<", (162, y + 1), 10, PALETTE["cream"])
                for step in range(10):
                    filled = step < level
                    tone = (PALETTE["muted"] if muted else PALETTE["mint"]) if filled else PALETTE["ink"]
                    pygame.draw.rect(surface, tone, (172 + step * 8, y + 2 + (9 - step) // 2, 6, 9 - (9 - step) // 2))
                text(surface, ">", (X1 - 6, y + 1), 10, PALETTE["cream"], align="right")
        hint = "Sound is OFF - switch SOUND on to hear the music." if not self.values["sound"] else \
            f"AI MODE: {self.game.llm.label}   F11 / ALT+ENTER: fullscreen"
        text(surface, hint, (160, TOP + ROW_H * len(ROWS) + 12), 8, PALETTE["sky"], center=True)

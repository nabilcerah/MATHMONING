"""Shared behaviour for overlay screens: keyboard + mouse list navigation and a closing flag."""
import pygame

from config import PALETTE, VIRTUAL_HEIGHT, VIRTUAL_WIDTH
from game import ui
from game.ui import text

CONFIRM = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_e)
UP = (pygame.K_UP, pygame.K_w)
DOWN = (pygame.K_DOWN, pygame.K_s)
LEFT = (pygame.K_LEFT, pygame.K_a)
RIGHT = (pygame.K_RIGHT, pygame.K_d)


class Screen:
    opaque = True          # draws the whole canvas (False = drawn over the state below)
    title = ""

    def __init__(self, game):
        self.game = game
        self.closed = False
        self.selected = 0
        self.notice = ""
        self.result = None

    # ------------------------------------------------------------------ shortcuts
    @property
    def repo(self):
        return self.game.repository

    @property
    def player_id(self):
        return self.game.player.player_id

    @property
    def party(self):
        return self.game.party

    def close(self, result=None):
        self.result = result
        self.closed = True

    # ------------------------------------------------------------------ input
    def items(self):
        return []

    def rows(self):
        """(top, row_height, left, right) of the clickable list, for the mouse."""
        return 40, 16, 8, 200

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = ui.to_virtual(event.pos)
            top, height, left, right = self.rows()
            index = ui.row_index(top, height, len(self.items()), pos, left, right)
            if index is not None:
                self.selected = index
                self.activate(index)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self.back()
            return
        if event.type == pygame.KEYDOWN:
            self.handle_key(event.key, getattr(event, "unicode", ""))

    def handle_key(self, key, unicode=""):
        count = len(self.items())
        if key == pygame.K_ESCAPE:
            self.back()
        elif key in UP and count:
            self.selected = (self.selected - 1) % count
        elif key in DOWN and count:
            self.selected = (self.selected + 1) % count
        elif pygame.K_1 <= key <= pygame.K_9 and key - pygame.K_1 < count:
            self.selected = key - pygame.K_1
            self.activate(self.selected)
        elif key in CONFIRM and count:
            self.activate(self.selected)

    def activate(self, index):
        pass

    def back(self):
        self.close()

    def update(self):
        pass

    # ------------------------------------------------------------------ drawing helpers
    def draw_frame(self, surface, title, color=None, footer="ARROWS: CHOOSE   ENTER: SELECT   ESC: BACK"):
        surface.fill(PALETTE["ink"])
        pygame.draw.rect(surface, PALETTE["night"], (0, 0, VIRTUAL_WIDTH, 24))
        text(surface, title, (VIRTUAL_WIDTH // 2, 12), 16, color or PALETTE["gold"], center=True)
        pygame.draw.rect(surface, PALETTE["night"], (0, VIRTUAL_HEIGHT - 16, VIRTUAL_WIDTH, 16))
        text(surface, footer, (VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT - 8), 9, PALETTE["cream"], center=True)
        if self.notice:
            text(surface, self.notice[:70], (VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT - 24), 9, PALETTE["mint"], center=True)

    def draw_list(self, surface, labels, frame, top=40, height=16, left=8, width=192, disabled=()):
        for index, label in enumerate(labels):
            y = top + index * height
            chosen = index == self.selected
            if chosen:
                pygame.draw.rect(surface, PALETTE["deep"], (left, y - 2, width, height - 2))
                ui.cursor(surface, left + 3, y + 2, PALETTE["gold"], frame)
            color = PALETTE["gold"] if chosen else (PALETTE["muted"] if index in disabled else PALETTE["white"])
            text(surface, label, (left + 12, y), 10, color)

"""CATALOG (TAB > CATALOG, or M / T on the map): one place for your collection, with two tabs -

    MATHDEX  every MathMon species you have seen or caught (ENTER makes one your companion)
    TRIALS   the twelve Trial monsters (bosses): the ones you have met, and hints for the rest

Q / E (or [ / ], or clicking a tab) switches tabs; ESC closes the catalog.
"""
import pygame

from config import PALETTE, VIRTUAL_WIDTH
from game import ui
from game.trials_screen import TrialsScreen
from game.ui import text
from states.base import Screen
from states.dex_state import DexScreen

TABS = ("MATHDEX", "TRIALS")
STRIP = 14                      # height of the tab strip drawn over the top of each page


class CatalogScreen(Screen):
    title = "CATALOG"

    def __init__(self, game, tab="MATHDEX"):
        super().__init__(game)
        self.tab = TABS.index(tab) if tab in TABS else 0
        self.dex = DexScreen(game)
        self.trials = TrialsScreen(game.repository, game.player, game._team())

    @property
    def page(self):
        return self.dex if self.tab == 0 else self.trials

    def switch(self, step):
        self.tab = (self.tab + step) % len(TABS)
        if self.tab == 1:
            self.trials.refresh()

    # ------------------------------------------------------------------ input
    def tab_rects(self):
        return [pygame.Rect(4 + i * 74, 1, 70, STRIP - 2) for i in range(len(TABS))]

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = ui.to_virtual(event.pos)
            for index, rect in enumerate(self.tab_rects()):
                if rect.collidepoint(pos):
                    if index != self.tab:
                        self.switch(index - self.tab)
                    return
            if self.tab == 0:
                self.dex.handle_event(event)
            return
        if event.type == pygame.KEYDOWN:
            self.handle_key(event.key, getattr(event, "unicode", ""))

    def handle_key(self, key, unicode=""):
        if key in (pygame.K_q, pygame.K_LEFTBRACKET):
            self.switch(-1)
        elif key in (pygame.K_e, pygame.K_RIGHTBRACKET):
            self.switch(1)
        elif key == pygame.K_ESCAPE:
            self.close()
        elif self.tab == 0:
            self.dex.handle_key(key, unicode)
            if self.dex.closed:              # the MathDex asked to close: close the whole catalog
                self.close()
        else:
            if key != pygame.K_t:            # T would close the old Trials state; here only ESC does
                self.trials.handle_key(key)
            self.trials.closed = False

    def update(self):
        if self.tab == 1:
            self.trials.update()

    # ------------------------------------------------------------------ drawing
    def draw(self, surface, frame=0):
        self.page.draw(surface, frame)
        ui.drop_text_in((0, 0, VIRTUAL_WIDTH, STRIP))         # the page's own title sits under the tabs
        pygame.draw.rect(surface, PALETTE["ink"], (0, 0, VIRTUAL_WIDTH, STRIP))
        pygame.draw.line(surface, PALETTE["gold"], (0, STRIP - 1), (VIRTUAL_WIDTH, STRIP - 1))
        for index, (label, rect) in enumerate(zip(TABS, self.tab_rects())):
            chosen = index == self.tab
            pygame.draw.rect(surface, PALETTE["deep"] if chosen else PALETTE["night"], rect)
            if chosen:
                pygame.draw.rect(surface, PALETTE["gold"], rect, 1)
            text(surface, label, rect.center, 8, PALETTE["gold"] if chosen else PALETTE["muted"], center=True)
        if self.tab == 0:
            records = self.dex.records
            ids = self.dex.ids
            caught = sum(1 for sid in ids if records.get(sid, {}).get("captured"))
            seen = sum(1 for sid in ids if records.get(sid, {}).get("seen") or records.get(sid, {}).get("captured"))
            summary = f"SEEN {seen}  CAUGHT {caught}/{len(ids)}"
        else:
            met = sum(1 for m in self.trials.monsters if self.trials.seen(m))
            summary = f"TRIAL MONSTERS MET {met}/{len(self.trials.monsters)}"
        text(surface, summary + "   Q/E: TAB", (VIRTUAL_WIDTH - 4, 3), 7, PALETTE["cream"], align="right")

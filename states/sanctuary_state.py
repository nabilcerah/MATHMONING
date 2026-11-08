"""MONSTER SANCTUARY (GDD 4.1, 26): stored monsters, their information, and transfers.

LEFT/RIGHT switches between your party and the boxes. ENTER on a party monster stores it; ENTER
on a stored monster brings it into the party (or swaps it with the party slot you last chose
when the party is full). The keeper also heals your party when you arrive.
"""
import pygame

from config import PALETTE
from game.ui import panel, text
from monsters.monster_party import PartyError
from states.base import CONFIRM, DOWN, LEFT, RIGHT, UP, Screen
from states.monster_card import draw_card


class SanctuaryScreen(Screen):
    VISIBLE = 9

    def __init__(self, game):
        super().__init__(game)
        self.column = 0          # 0 = party, 1 = storage
        self.party_cursor = 0
        self.box_cursor = 0
        self.scroll = 0
        self.profile = self.repo.learning_profile(self.player_id)

    def items(self):
        return self.party.party if self.column == 0 else self.party.storage

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            from game import ui
            x, y = ui.to_virtual(event.pos)
            if x < 96:
                index = ui.row_index(36, 20, len(self.party.party), (x, y), 4, 94)
                if index is not None:
                    self.column, self.party_cursor = 0, index
                    self.transfer()
            elif x < 174:
                index = ui.row_index(36, 15, min(self.VISIBLE, len(self.party.storage)), (x, y), 98, 172)
                if index is not None:
                    self.column, self.box_cursor = 1, index + self.scroll
                    self.transfer()
            return
        super().handle_event(event)

    def handle_key(self, key, unicode=""):
        if key == pygame.K_ESCAPE:
            self.close()
        elif key in LEFT + RIGHT:
            self.column = 1 - self.column if self.party.storage or self.column == 1 else 0
        elif key in UP + DOWN:
            step = -1 if key in UP else 1
            if self.column == 0 and self.party.party:
                self.party_cursor = (self.party_cursor + step) % len(self.party.party)
            elif self.party.storage:
                self.box_cursor = (self.box_cursor + step) % len(self.party.storage)
                self.scroll = min(max(self.scroll, self.box_cursor - self.VISIBLE + 1), self.box_cursor)
        elif key in CONFIRM:
            self.transfer()

    def transfer(self):
        try:
            if self.column == 0:
                monster = self.party.deposit(self.party_cursor)
                self.party_cursor = min(self.party_cursor, len(self.party.party) - 1)
                self.notice = f"{monster.name} is resting in the Sanctuary."
            elif not self.party.storage:
                return
            elif self.party.party_full:
                incoming, outgoing = self.party.swap(self.party_cursor, self.box_cursor)
                self.notice = f"{incoming.name} joins the party; {outgoing.name} rests here."
            else:
                monster = self.party.withdraw(self.box_cursor)
                self.box_cursor = max(0, min(self.box_cursor, len(self.party.storage) - 1))
                self.notice = f"{monster.name} joins your party."
        except PartyError as error:
            self.notice = str(error)
            return
        self.game.save_party()

    def focused(self):
        if self.column == 0 and self.party.party:
            return self.party.party[min(self.party_cursor, len(self.party.party) - 1)]
        if self.column == 1 and self.party.storage:
            return self.party.storage[min(self.box_cursor, len(self.party.storage) - 1)]
        return None

    def draw(self, surface, frame=0):
        self.draw_frame(surface, "MONSTER SANCTUARY", PALETTE["mint"],
                        "LEFT/RIGHT: PARTY/BOXES   ENTER: STORE / TAKE / SWAP   ESC: LEAVE")
        panel(surface, (4, 28, 90, 72), PALETTE["night"], PALETTE["gold"] if self.column == 0 else None)
        text(surface, f"PARTY {len(self.party.party)}/3", (10, 30), 9, PALETTE["gold"])
        for index, monster in enumerate(self.party.party):
            y = 40 + index * 20
            chosen = self.column == 0 and index == self.party_cursor
            if chosen or (self.column == 1 and index == self.party_cursor and self.party.party_full):
                pygame.draw.rect(surface, PALETTE["deep"], (8, y - 2, 82, 18))
            text(surface, f"{monster.name[:9]} {monster.level}", (12, y), 10,
                 PALETTE["gold"] if chosen else PALETTE["white"])
            text(surface, f"{monster.hp}/{monster.max_hp}", (88, y + 8), 7, PALETTE["muted"], align="right")
        panel(surface, (98, 28, 74, 166), PALETTE["night"], PALETTE["gold"] if self.column == 1 else None)
        text(surface, f"BOXES {len(self.party.storage)}/{self.party.capacity}", (102, 30), 9, PALETTE["gold"])
        if not self.party.storage:
            text(surface, "Empty. Capture", (102, 46), 8, PALETTE["muted"])
            text(surface, "more monsters!", (102, 56), 8, PALETTE["muted"])
        for row, monster in enumerate(self.party.storage[self.scroll:self.scroll + self.VISIBLE]):
            index = row + self.scroll
            y = 40 + row * 15
            chosen = self.column == 1 and index == self.box_cursor
            if chosen:
                pygame.draw.rect(surface, PALETTE["deep"], (101, y - 2, 68, 14))
            text(surface, f"{monster.name[:9]} {monster.level}", (104, y), 9, PALETTE["gold"] if chosen else PALETTE["white"])
        if self.column == 1 and self.party.party_full and self.party.storage:
            text(surface, "Party full: ENTER swaps", (8, 104), 8, PALETTE["cream"])
            text(surface, "with the highlighted", (8, 113), 8, PALETTE["cream"])
            text(surface, "party monster.", (8, 122), 8, PALETTE["cream"])
        monster = self.focused()
        if monster:
            draw_card(surface, monster, (176, 28, 140, 190), self.profile, frame, show_moves=False)

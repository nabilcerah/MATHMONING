"""PARTY screen (GDD 4.1, 26): three party slots with HP, level, EXP and mastery; ENTER makes the
chosen monster the lead (it battles first). Up to three companions walk behind you on the map:
F toggles whether the chosen one walks with you or rests in its Numeris Core.
R REPLACES the chosen companion with any MathMon you have caught (from the Sanctuary) - anywhere,
no trip to the Sanctuary needed. With a free slot, the chosen MathMon simply joins. From the trainer menu."""
import pygame

from config import PALETTE
from game.ui import meter, text, wrapped
from monsters.monster_party import PartyError
from states.base import Screen
from states.monster_card import draw_card, element_badge


class PartyScreen(Screen):
    title = "PARTY"

    PICK_TOP, PICK_ROW, PICK_ROWS = 50, 18, 8

    def __init__(self, game):
        super().__init__(game)
        self.profile = self.repo.learning_profile(self.player_id)
        self.picking = False          # choosing who replaces the companion in slot ``self.slot``
        self.slot = 0
        self.pick_top = 0

    def items(self):
        return self.party.storage if self.picking else self.party.party

    def rows(self):
        if self.picking:
            return self.PICK_TOP, self.PICK_ROW, 150, 312
        return 34, 30, 6, 140

    def handle_key(self, key, unicode=""):
        if self.picking:
            if key == pygame.K_ESCAPE:
                self.stop_picking()
                return
            super().handle_key(key, unicode)
            self.pick_top = min(max(self.pick_top, self.selected - self.PICK_ROWS + 1), self.selected)
            return
        if key == pygame.K_f and self.party.party:
            self.toggle_follow(min(self.selected, len(self.party.party) - 1))
        elif key == pygame.K_r:
            self.start_picking()
        else:
            super().handle_key(key, unicode)

    # ------------------------------------------------------------------ REPLACE a companion
    def start_picking(self):
        if not self.party.storage:
            self.notice = "No other MathMon yet - catch one with a Numeris Core first!"
            return
        self.slot = min(self.selected, max(0, len(self.party.party) - 1))
        self.picking, self.selected, self.pick_top = True, 0, 0
        self.notice = ""

    def stop_picking(self):
        self.picking = False
        self.selected = self.slot

    def replace(self, box_index):
        """Swap the chosen companion with a stored MathMon (or add it if the party has room)."""
        party = self.party
        try:
            if party.party_full:
                incoming, outgoing = party.swap(self.slot, box_index)
                self.notice = f"{incoming.name} joins your party! {outgoing.name} rests in the Sanctuary."
            else:
                incoming = party.withdraw(box_index)
                self.notice = f"{incoming.name} joins your party!"
        except PartyError as error:
            self.notice = str(error)
            return False
        self.game.save_party()
        self.picking = False
        self.selected = party.party.index(incoming)
        return True

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
            self.notice = f"{monster.name} rests in its Numeris Core."
        else:
            world.clear_flag(flag)
            self.notice = f"{monster.name} walks with you!"

    def activate(self, index):
        if self.picking:
            self.replace(index)
            return
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
        footer = ("UP/DOWN: CHOOSE   ENTER: SWAP IN   ESC: CANCEL" if self.picking else
                  "ENTER: LEAD   R: REPLACE   F: WALK / REST   ESC: BACK")
        self.draw_frame(surface, "PARTY", footer=footer)
        for index in range(self.party.max_party):
            y = 34 + index * 30
            chosen = index == (self.slot if self.picking else self.selected)
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
        if not self.picking:
            text(surface, "R: replace with a caught MathMon", (8, 140), 8, PALETTE["sky"])
        if self.notice:
            wrapped(surface, self.notice, (8, 154, 132, 40), 8, PALETTE["mint"], 9, 4)
        if self.picking:
            self._draw_picker(surface, frame)
        elif self.party.party:
            monster = self.party.party[min(self.selected, len(self.party.party) - 1)]
            draw_card(surface, monster, (146, 30, 168, 186), self.profile, frame)

    def _draw_picker(self, surface, frame):
        """Every caught MathMon resting in the Sanctuary: pick who joins the party."""
        from game.creatures import draw_creature
        from game.ui import cursor, panel
        panel(surface, (146, 30, 168, 186), PALETTE["night"], PALETTE["gold"])
        outgoing = self.party.party[self.slot].name if self.party.party_full else "a free slot"
        text(surface, f"REPLACE {outgoing}" if self.party.party_full else "ADD TO YOUR PARTY", (152, 35), 9,
             PALETTE["gold"])
        storage = self.party.storage
        for row, monster in enumerate(storage[self.pick_top:self.pick_top + self.PICK_ROWS]):
            index = row + self.pick_top
            y = self.PICK_TOP + row * self.PICK_ROW
            chosen = index == self.selected
            if chosen:
                pygame.draw.rect(surface, PALETTE["deep"], (150, y - 2, 160, self.PICK_ROW - 2))
                cursor(surface, 151, y + 4, PALETTE["gold"], frame)
            draw_creature(surface, monster.spec, (166, y + 14), 14, "hurt" if monster.fainted else "idle")
            text(surface, f"{monster.name[:10]}", (178, y), 9, PALETTE["gold"] if chosen else PALETTE["white"])
            text(surface, f"Lv {monster.level}", (306, y), 8, PALETTE["cream"], align="right")
            meter(surface, 178, y + 10, 70, 4, monster.hp, monster.max_hp, PALETTE["mint"], warn=True)
            element_badge(surface, monster.element, (252, y + 8), 54)
        if self.pick_top > 0:
            pygame.draw.polygon(surface, PALETTE["gold"], [(305, 46), (308, 42), (311, 46)])
        if self.pick_top + self.PICK_ROWS < len(storage):
            pygame.draw.polygon(surface, PALETTE["gold"], [(305, 208), (308, 212), (311, 208)])

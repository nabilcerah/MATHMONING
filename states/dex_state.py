"""MATHDEX: the collection record (GDD 8.3) - every species, whether you've seen or captured it,
its element, role and maths affinity."""
from config import PALETTE
from game.creatures import draw_creature
from game.ui import panel, text, wrapped
from mathematics import curriculum
from monsters import elemental_system
from monsters.monster_data import species, species_ids
from states.base import Screen
from states.monster_card import element_badge


class DexScreen(Screen):
    VISIBLE = 11

    def __init__(self, game):
        super().__init__(game)
        self.records = self.repo.capture_records(self.player_id)
        self.ids = [sid for sid in species_ids() if not species(sid).boss]
        self.scroll = 0

    def items(self):
        return self.ids

    def rows(self):
        return 34, 15, 4, 120

    def handle_key(self, key, unicode=""):
        super().handle_key(key, unicode)
        self.scroll = min(max(self.scroll, self.selected - self.VISIBLE + 1), self.selected)

    def owned(self, species_id):
        """Your monsters of this species (or its evolved forms), strongest first."""
        mine = [m for m in self.party.all_monsters()
                if m.species_id == species_id or m.spec.evolves_from == species_id]
        return sorted(mine, key=lambda m: -m.level)

    def activate(self, index):
        """Make the chosen species your companion: it leads your party and follows you around."""
        sid = self.ids[index]
        mine = self.owned(sid)
        if not mine:
            self.notice = "Catch one first - then it can be your companion."
            return
        monster = next((m for m in mine if not m.fainted), None)
        if monster is None:
            self.notice = f"{mine[0].name} needs healing before it can lead."
            return
        party = self.party
        if monster in party.storage:
            box = party.storage.index(monster)
            try:
                if party.party_full:
                    party.swap(len(party.party) - 1, box)     # the last party slot rests in the Sanctuary
                else:
                    party.withdraw(box)
            except Exception as error:
                self.notice = str(error)
                return
        party.set_lead(party.party.index(monster))
        self.game.save_party()
        self.notice = f"{monster.name} is now your companion!"

    def draw(self, surface, frame=0):
        caught = sum(1 for sid in self.ids if self.records.get(sid, {}).get("captured"))
        seen = sum(1 for sid in self.ids if self.records.get(sid, {}).get("seen") or self.records.get(sid, {}).get("captured"))
        self.draw_frame(surface, f"MATHDEX   seen {seen}   caught {caught}/{len(self.ids)}",
                        footer="ARROWS: CHOOSE   ENTER: MAKE COMPANION   ESC: BACK")
        lead = self.party.lead if self.party and self.party.party else None
        for row, sid in enumerate(self.ids[self.scroll:self.scroll + self.VISIBLE]):
            index = row + self.scroll
            record = self.records.get(sid, {})
            known = record.get("seen") or record.get("captured")
            y = 34 + row * 15
            chosen = index == self.selected
            if chosen:
                import pygame
                pygame.draw.rect(surface, PALETTE["deep"], (4, y - 2, 118, 14))
            name = species(sid).name if known else "?????"
            mark = "C" if record.get("captured") else ("S" if known else " ")
            if lead and sid in (lead.species_id, lead.spec.evolves_from):
                mark = "*"          # your companion
            text(surface, f"{index + 1:02d} {name}", (8, y), 9, PALETTE["gold"] if chosen else PALETTE["white"])
            text(surface, mark, (118, y), 8, PALETTE["gold"] if mark == "*" else PALETTE["mint"] if mark == "C" else PALETTE["muted"], align="right")
        sid = self.ids[min(self.selected, len(self.ids) - 1)]
        spec = species(sid)
        record = self.records.get(sid, {})
        known = record.get("seen") or record.get("captured")
        panel(surface, (126, 30, 190, 186), PALETTE["night"])
        draw_creature(surface, spec, (220, 100), 60, "idle", tint=None if known else PALETTE["ink"])
        if not known:
            text(surface, "Not yet seen. Explore to find it!", (221, 112), 9, PALETTE["muted"], center=True)
            return
        text(surface, spec.name, (132, 106), 12, PALETTE["gold"])
        element_badge(surface, spec.element, (132, 120))
        text(surface, f"Beats {elemental_system.strong_against(spec.element)}", (178, 120), 8, PALETTE["mint"])
        text(surface, f"Role: {spec.role}", (132, 132), 8, PALETTE["white"])
        topics = ", ".join(curriculum.label(t) for t in spec.topics)
        text(surface, f"Maths: {topics}", (132, 142), 8, PALETTE["sky"])
        text(surface, f"Seen {record.get('seen', 0)}   Caught {record.get('captured', 0)}", (132, 152), 8, PALETTE["cream"])
        wrapped(surface, spec.description, (132, 164, 178, 48), 8, PALETTE["white"], 9, 5)

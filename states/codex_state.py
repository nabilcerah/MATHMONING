"""The CODEX / lore journal (lore spec section 10): World History, Characters, MathMon, Regions,
Historical Records and Main Story. Entries unlock as you discover things; parts you haven't
found yet show as '???', so you can tell a story is incomplete."""
import pygame

from config import PALETTE
from game.ui import panel, text, wrap_lines
from states.base import LEFT, RIGHT, Screen
from world.story_manager import lore

SECTIONS = ("world", "characters", "monsters", "regions", "records", "story", "trials")
VISIBLE = 11


class CodexScreen(Screen):
    def __init__(self, game):
        super().__init__(game)
        self.story = game.story
        self.section = 0
        self.scroll = 0
        self.text_scroll = 0
        records = self.repo.capture_records(self.player_id)
        self.seen = {sid for sid, r in records.items() if r.get("seen") or r.get("captured")}
        self.caught = {sid for sid, r in records.items() if r.get("captured")}
        for monster in self.party.all_monsters():
            self.caught.add(monster.species_id)
            self.seen.add(monster.species_id)
        # The story bosses are Monster Trials creatures now: they live in the TRIAL section, not here.
        self._load()

    def _load(self):
        self.entries = self.story.codex(SECTIONS[self.section], self.seen, self.caught)
        self.selected = min(self.selected, max(0, len(self.entries) - 1))
        self.scroll = 0
        self.text_scroll = 0

    def items(self):
        return self.entries

    def rows(self):
        return 46, 14, 4, 116

    def handle_key(self, key, unicode=""):
        if key in LEFT + RIGHT:
            self.section = (self.section + (1 if key in RIGHT else -1)) % len(SECTIONS)
            self.selected = 0
            self._load()
            return
        if key in (pygame.K_PAGEDOWN, pygame.K_x):
            self.text_scroll += 3
            return
        if key in (pygame.K_PAGEUP, pygame.K_z):
            self.text_scroll = max(0, self.text_scroll - 3)
            return
        before = self.selected
        super().handle_key(key, unicode)
        if self.selected != before:
            self.text_scroll = 0
        self.scroll = min(max(self.scroll, self.selected - VISIBLE + 1), self.selected)

    def draw(self, surface, frame=0):
        titles = lore()["section_titles"]
        found = len(self.story.records_found())
        total = sum(1 for e in lore()["entries"].values() if e.get("section") == "records")
        self.draw_frame(surface, "CODEX", footer="LEFT/RIGHT: SECTION   UP/DOWN: ENTRY   Z/X: SCROLL   ESC: BACK")
        for i, key in enumerate(SECTIONS):
            label = titles[key].split()[0] if key != "monsters" else "MATHMON"
            text(surface, label, (4 + i * 45, 30), 8, PALETTE["gold"] if i == self.section else PALETTE["muted"])
        pygame.draw.line(surface, PALETTE["deep"], (4, 40), (316, 40))
        chapter = self.story.chapter()
        text(surface, f"{chapter['number']}: {chapter['title']}", (316, 214), 7, PALETTE["sky"], align="right")
        text(surface, f"Records {found}/{total}", (4, 214), 7, PALETTE["cream"])
        if not self.entries:
            text(surface, "Nothing discovered here yet. Explore, talk and read!", (10, 54), 9, PALETTE["muted"])
            return
        for row, (title, parts) in enumerate(self.entries[self.scroll:self.scroll + VISIBLE]):
            index = row + self.scroll
            y = 46 + row * 14
            chosen = index == self.selected
            if chosen:
                pygame.draw.rect(surface, PALETTE["deep"], (4, y - 2, 112, 13))
            complete = all(p is not None for p in parts)
            text(surface, title[:19], (8, y), 8, PALETTE["gold"] if chosen else PALETTE["white"])
            if not complete:
                text(surface, "...", (114, y), 8, PALETTE["muted"], align="right")
        title, parts = self.entries[self.selected]
        panel(surface, (120, 44, 196, 164), PALETTE["night"])
        text(surface, title[:30], (126, 48), 10, PALETTE["gold"])
        lines = []
        for part in parts:
            if part is None:
                lines += ["???  (not yet discovered)", ""]
            else:
                lines += wrap_lines(part, 182, 8) + [""]
        self.text_scroll = min(self.text_scroll, max(0, len(lines) - 14))
        for i, line in enumerate(lines[self.text_scroll:self.text_scroll + 14]):
            color = PALETTE["muted"] if line.startswith("???") else PALETTE["white"]
            text(surface, line, (126, 62 + i * 10), 8, color)
        if len(lines) > 14:
            text(surface, "Z/X: scroll", (310, 198), 7, PALETTE["sky"], align="right")


class ChapterCard(Screen):
    """A chapter title card: CHAPTER 2 / THE FRACTURED EQUATIONS."""

    def __init__(self, game, chapter):
        super().__init__(game)
        self.chapter = chapter
        self.age = 0

    def update(self):
        self.age += 1
        if self.age > 240:
            self.close()

    def handle_key(self, key, unicode=""):
        if self.age > 20:
            self.close()

    def handle_event(self, event):
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.handle_key(getattr(event, "key", 0))

    def draw(self, surface, frame=0):
        surface.fill(PALETTE["ink"])
        fade = min(1.0, self.age / 30)
        gold = tuple(int(c * fade) for c in PALETTE["gold"])
        cream = tuple(int(c * fade) for c in PALETTE["cream"])
        text(surface, self.chapter["number"], (160, 80), 14, cream, center=True)
        pygame.draw.line(surface, gold, (90, 96), (230, 96))
        text(surface, self.chapter["title"], (160, 112), 20, gold, center=True)
        text(surface, self.chapter["region"], (160, 136), 10, cream, center=True)
        if self.age > 40:
            lines = wrap_lines(self.chapter["objective"], 260, 9)
            for i, line in enumerate(lines[:3]):
                text(surface, line, (160, 162 + i * 11), 9, PALETTE["sky"], center=True)
        if self.age > 60 and frame % 50 < 34:
            text(surface, "PRESS ANY KEY", (160, 214), 8, PALETTE["muted"], center=True)

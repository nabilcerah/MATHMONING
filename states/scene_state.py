"""The story dialogue screen (lore spec section 8). Text only - no audio narration.

* Pixel dialogue box with the speaker's portrait, name and a category label (STORY, PROFESSOR,
  BOSS, HISTORICAL RECORD, NUM-LINK, ...), each with its own colour.
* Typewriter text: ENTER/E/SPACE/click first finishes the line, then moves on. ESC skips ahead
  to the next choice (or the end). A blinking arrow shows when there is more.
* Choices: 'explore' choices let you ask several questions, then leave; 'decide' choices pick
  one path and may change the story. Options can be locked behind flags.
* Num-Link messages appear as a communicator at the top of the screen; historical records as
  parchment. The box slides in when a scene starts.
"""
import pygame

from config import PALETTE
from game import audio, monster_sprites, ui
from game.ui import panel, text, wrapped
from states.base import CONFIRM, DOWN, UP, Screen
from world.story_manager import categories, characters

REVEAL_SPEED = 2
SLIDE_FRAMES = 8


class SceneScreen(Screen):
    opaque = False

    def __init__(self, game, story, scene, avatar_sheet=None):
        super().__init__(game)
        self.story, self.scene = story, scene
        self.avatar_sheet = avatar_sheet
        self.category = scene.get("category", "npc")
        self.queue = list(scene.get("lines", []))
        self.line = None
        self.age = 0
        self.frames = 0
        self.choices = scene.get("choices")
        self.used = set()           # explore options already asked
        self.in_choice = False
        self.after_done = False
        self.actions, self.quests, self.new_flags = [], [], []
        self.last_line = None
        self.opaque = bool(scene.get("backdrop"))     # e.g. the opening: a full dark backdrop
        self._next_line()

    # ------------------------------------------------------------------ flow
    def _next_line(self):
        if self.queue:
            self.line = self.last_line = self.queue.pop(0)
            self.age = 0
            return
        if self.choices and not self._choices_finished():
            self.in_choice, self.selected = True, 0
            return
        if not self.after_done and self.scene.get("after"):
            self.after_done = True
            self.queue = list(self.scene["after"])
            self._next_line()
            return
        self._finish()

    def _choices_finished(self):
        if self.choices["mode"] == "decide":
            return getattr(self, "decided", False)
        return getattr(self, "explored", False)

    def options(self):
        """Visible options (locked ones are hidden) plus the 'exit' entry for explore menus."""
        visible = [o for o in self.choices["options"] if self.story.option_visible(o)]
        if self.choices["mode"] == "explore":
            visible = visible + [{"label": self.choices.get("exit", "That's all."), "exit": True}]
        return visible

    def choose(self, index):
        option = self.options()[index]
        self.in_choice = False
        audio.play("select")
        if option.get("exit"):
            self.explored = True
            self._next_line()
            return
        if self.choices["mode"] == "decide":
            self.decided = True
        else:
            self.used.add(option["label"])
        flags, actions, quest = self.story.apply(option)
        self.new_flags += flags
        self.actions += actions
        if quest:
            self.quests.append(quest)
        self.queue = list(option.get("lines", []))
        self.line = None
        self._next_line()

    def _finish(self):
        flags, actions, quest = self.story.finish(self.scene)
        self.new_flags += flags
        self.actions += actions
        if quest:
            self.quests.append(quest)
        self.close({"actions": self.actions, "quests": self.quests, "flags": self.new_flags,
                    "chapter_card": self.scene.get("chapter_card")})

    @property
    def revealed(self):
        return self.line is None or self.age * REVEAL_SPEED >= len(self.line["t"])

    # ------------------------------------------------------------------ input
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.in_choice:
                x, y = ui.to_virtual(event.pos)
                index = ui.row_index(self._choice_top(), 13, len(self.options()), (x, y), 150, 316)
                if index is not None:
                    self.choose(index)
            else:
                self.handle_key(pygame.K_RETURN)
            return
        if event.type == pygame.KEYDOWN:
            self.handle_key(event.key, getattr(event, "unicode", ""))

    def handle_key(self, key, unicode=""):
        if self.in_choice:
            options = self.options()
            if key in UP:
                self.selected = (self.selected - 1) % len(options)
            elif key in DOWN:
                self.selected = (self.selected + 1) % len(options)
            elif pygame.K_1 <= key <= pygame.K_9 and key - pygame.K_1 < len(options):
                self.choose(key - pygame.K_1)
            elif key in CONFIRM:
                self.choose(self.selected)
            return
        if key == pygame.K_ESCAPE:
            # Skip: everything up to the next choice (or the end) - nothing important is decided by skipping.
            self.queue.clear()
            self.line = None
            self._next_line()
        elif key in CONFIRM:
            if not self.revealed:
                self.age = 10 ** 6          # show the whole line at once
            else:
                self._next_line()

    def update(self):
        self.age += 1
        self.frames += 1

    # ------------------------------------------------------------------ drawing
    def _choice_top(self):
        return 132 - 13 * len(self.options())

    def _style(self):
        style = categories().get(self.category, categories()["npc"])
        return style["label"], tuple(style["color"])

    def _portrait(self, surface, speaker, rect):
        info = characters().get(speaker, {})
        sheet = self.avatar_sheet if info.get("portrait") == "player" else info.get("portrait")
        pygame.draw.rect(surface, PALETTE["deep"], rect)
        if sheet and monster_sprites.available(sheet):
            surface.set_clip(rect)
            monster_sprites.draw(surface, sheet, (rect[0] + rect[2] // 2, rect[1] + 58), 56, 0)
            surface.set_clip(None)
        else:   # a simple silhouette for characters without portrait art
            color = tuple(info.get("color", (200, 200, 200)))
            pygame.draw.circle(surface, color, (rect[0] + rect[2] // 2, rect[1] + 13), 7)
            pygame.draw.rect(surface, color, (rect[0] + 8, rect[1] + 22, rect[2] - 16, rect[3] - 22))

    def draw(self, surface, frame=0):
        label, color = self._style()
        slide = max(0, SLIDE_FRAMES - self.frames) * 6
        if self.opaque:
            ui.begin_frame()
            surface.fill(PALETTE["ink"])
            for i in range(24):        # a few still stars: the Null before counting began
                x, y = (i * 97) % 320, (i * 53) % 140
                pygame.draw.rect(surface, PALETTE["deep"] if i % 3 else PALETTE["muted"], (x, y, 1, 1))
        elif self.category in ("main", "record", "secret", "boss_intro", "boss_defeat"):
            shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            shade.fill((*PALETTE["ink"], min(150, self.frames * 20)))
            surface.blit(shade, (0, 0))
        if self.in_choice:
            self._draw_choices(surface, frame, color)
        line = self.line or (self.last_line if self.in_choice else None)
        if line is None:
            return
        speaker = line.get("s", "narrator")
        info = characters().get(speaker, {})
        shown = line["t"][:max(1, self.age * REVEAL_SPEED)]
        if self.category == "comm" or speaker == "numlink":
            self._draw_comm(surface, info, shown, frame, slide)
            return
        record = self.category == "record"
        rect = pygame.Rect(6, 150 + slide, 308, 64)
        fill = (236, 220, 180) if record else PALETTE["night"]
        ink = (70, 50, 30) if record else PALETTE["white"]
        panel(surface, rect, fill, color)
        left = rect.x + 8
        if info.get("portrait") or (speaker not in ("narrator", "inscription") and not record):
            self._portrait(surface, speaker, (rect.x + 6, rect.y + 8, 36, 36))
            left = rect.x + 48
        if info.get("name"):
            name_w = ui.measure(info["name"], 10)[0] + 12
            panel(surface, (left - 4, rect.y - 15, name_w, 16), PALETTE["ink"], tuple(info.get("color", color)))
            text(surface, info["name"], (left + 2, rect.y - 13), 10, tuple(info.get("color", color)))
        if label:
            text(surface, label, (rect.right - 8, rect.y + 4), 7, color, align="right")
        if record and self.scene.get("title"):
            text(surface, self.scene["title"].upper(), (left, rect.y + 5), 9, (120, 80, 40))
        top = rect.y + (16 if record else 14)
        italic_narration = speaker == "narrator"
        wrapped(surface, shown, (left, top, rect.right - left - 10, 46), 10,
                PALETTE["cream"] if italic_narration and not record else ink, 11, 4)
        if self.revealed and frame % 40 < 26 and not self.in_choice:
            x, y = rect.right - 12, rect.bottom - 9
            pygame.draw.polygon(surface, color, [(x, y), (x + 6, y), (x + 3, y + 4)])

    def _draw_comm(self, surface, info, shown, frame, slide):
        rect = pygame.Rect(30, 28 - slide, 260, 52)
        panel(surface, rect, (20, 34, 52), PALETTE["sky"])
        blink = PALETTE["mint"] if frame % 30 < 18 else PALETTE["deep"]
        pygame.draw.circle(surface, blink, (rect.x + 8, rect.y + 7), 3)
        text(surface, "NUM-LINK", (rect.x + 14, rect.y + 3), 8, PALETTE["sky"])
        text(surface, "PROF. NUMERIS", (rect.right - 8, rect.y + 3), 8, PALETTE["gold"], align="right")
        self._portrait(surface, "professor", (rect.x + 6, rect.y + 14, 30, 32))
        wrapped(surface, shown, (rect.x + 42, rect.y + 14, rect.w - 50, 36), 9, PALETTE["white"], 10, 4)
        if self.revealed and frame % 40 < 26:
            x, y = rect.right - 10, rect.bottom - 8
            pygame.draw.polygon(surface, PALETTE["sky"], [(x, y), (x + 5, y), (x + 2, y + 3)])

    def _draw_choices(self, surface, frame, color):
        options = self.options()
        top = self._choice_top()
        height = 13 * len(options) + 10
        panel(surface, (146, top - 6, 168, height), PALETTE["night"], color)
        prompt = self.choices.get("prompt")
        if prompt:
            text(surface, prompt, (150, top - 17), 9, PALETTE["gold"], shadow=PALETTE["ink"])
        for index, option in enumerate(options):
            y = top + index * 13
            chosen = index == self.selected
            if chosen:
                pygame.draw.rect(surface, PALETTE["deep"], (150, y - 2, 160, 12))
                ui.cursor(surface, 152, y + 1, PALETTE["gold"], frame)
            asked = option["label"] in self.used
            tone = PALETTE["gold"] if chosen else (PALETTE["muted"] if asked else PALETTE["white"])
            text(surface, f"{index + 1}. {option['label']}"[:34], (161, y), 9, tone)

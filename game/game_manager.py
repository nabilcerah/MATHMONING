"""Pygame loop and top-level state transitions for MATHMON."""
import random
import sys

import pygame

from ai.game_master import GameMasterAgent
from ai.llm_provider import LLMProvider
from ai.orchestrator import AgentOrchestrator
from config import FPS, PALETTE, TITLE, VIRTUAL_HEIGHT, VIRTUAL_WIDTH, WINDOW_SCALE
from database.database import Database
from database.player_repository import PlayerRepository
from game.battle import Battle
from game.creatures import ENEMIES, STARTERS, WILD_BY_NAME, canonical_name, creature_spec, draw_creature, encounter_for
from game.mathdex import MathDex
from game.worldmap_screen import WorldMapScreen
from game.overworld import Overworld
from game.player import Player
from game import ui
from game.ui import menu, meter, panel, text, wrapped


class GameManager:
    MENU_CHOICES = ("NEW GAME", "CONTINUE", "PLAYER PROFILE", "SETTINGS", "EXIT")
    FADE_FRAMES = 14

    def __init__(self, database_path=None):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.fullscreen = False
        self.window = pygame.display.set_mode((VIRTUAL_WIDTH * WINDOW_SCALE, VIRTUAL_HEIGHT * WINDOW_SCALE),
                                              pygame.RESIZABLE)
        self.canvas = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT))
        ui.set_text_layer(self.canvas)
        self.menu_hint = "A little practice can unlock a mighty adventure."
        self.profile_summary = None
        self.fade = 0
        self._last_state = None
        self.clock = pygame.time.Clock()
        self.database = Database(database_path)
        self.repository = PlayerRepository(self.database)
        self.orchestrator = AgentOrchestrator(self.repository)
        self.llm = LLMProvider()
        self.saved_record = self.repository.load_player()
        self.player = None
        self.world = None
        self.battle = None
        self.dex = None
        self.map_screen = None
        self.state = "menu"
        self.menu_selected = 0
        self.starter_selected = 0
        self.avatar_selected = 0
        self.settings_selected = 0
        self.scanlines = False
        self.player_name = ""
        self.frame = 0
        self.running = True
        self.menu_time = 0
        self.rng = random.Random()
        pygame.key.set_repeat(220, 105)

    def run(self):
        while self.running:
            self.frame += 1
            for event in pygame.event.get():
                self._handle_event(event)
            self._update()
            self._draw()
            self._present()
            self.clock.tick(FPS)
        self._shutdown()

    def _handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.KEYDOWN and (event.key == pygame.K_F11 or
                                             (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT)):
            self._toggle_fullscreen()
            return
        if self.state == "battle" and self.battle:
            self.battle.handle_event(event)
            return
        if event.type != pygame.KEYDOWN:
            return
        if self.state == "menu":
            self._menu_key(event)
        elif self.state == "name":
            if event.key == pygame.K_RETURN:
                self.state = "avatar"
            elif event.key == pygame.K_ESCAPE:
                self.state = "menu"
            elif event.key == pygame.K_BACKSPACE:
                self.player_name = self.player_name[:-1]
            elif event.unicode and event.unicode.isprintable() and event.unicode not in "\r\n" and len(self.player_name) < 18:
                self.player_name += event.unicode
        elif self.state == "confirm_new":
            if event.key in (pygame.K_y, pygame.K_RETURN):
                self.player_name, self.state = "", "name"
            elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                self.state = "menu"
        elif self.state == "avatar":
            if event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                self.avatar_selected = 1 - self.avatar_selected
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.state = "starter"
            elif event.key == pygame.K_ESCAPE:
                self.state = "name"
        elif self.state == "starter":
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.starter_selected = (self.starter_selected - 1) % len(STARTERS)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.starter_selected = (self.starter_selected + 1) % len(STARTERS)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._create_new_player()
            elif event.key == pygame.K_ESCAPE:
                self.state = "menu"
        elif self.state in ("profile", "settings"):
            if event.key == pygame.K_ESCAPE:
                self.state = "menu"
            elif self.state == "profile" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.state = "menu"
            elif self.state == "settings":
                if event.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                    self.settings_selected = (self.settings_selected + 1) % 2
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.settings_selected == 0:
                        self.scanlines = not self.scanlines
                    else:
                        self.state = "menu"
        elif self.state == "overworld":
            self._overworld_key(event)
        elif self.state == "worldmap" and self.map_screen:
            self.map_screen.handle_key(event.key)
            if self.map_screen.closed:
                if self.map_screen.travel_to:
                    cell, name = self.map_screen.travel_to
                    self.world.teleport(cell)
                    self.repository.save_player(self.player)
                    self.world.set_message(f"You travel to {name}.", 150)
                self.map_screen = None
                self.state = "overworld"
        elif self.state == "dex" and self.dex:
            self.dex.handle_key(event.key)
            if self.dex.closed:
                self.dex = None
                self.world.refresh_flags()
                self.state = "overworld"

    def _menu_key(self, event):
        if event.key in (pygame.K_UP, pygame.K_w):
            self.menu_selected = (self.menu_selected - 1) % len(self.MENU_CHOICES)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.menu_selected = (self.menu_selected + 1) % len(self.MENU_CHOICES)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            choice = self.MENU_CHOICES[self.menu_selected]
            if choice == "NEW GAME":
                if self.saved_record:
                    self.state = "confirm_new"
                else:
                    self.player_name, self.state = "", "name"
            elif choice == "CONTINUE":
                if self.saved_record:
                    self._continue_game()
                else:
                    self.menu_hint = "No saved journey yet. Choose NEW GAME to begin."
            elif choice == "PLAYER PROFILE":
                if self.saved_record:
                    self.profile_summary = None
                    self.state = "profile"
                else:
                    self.menu_hint = "Begin a new journey to create your profile."
            elif choice == "SETTINGS":
                self.state = "settings"
            elif choice == "EXIT":
                self.running = False

    def _create_new_player(self):
        creature = tuple(STARTERS)[self.starter_selected]
        spec = STARTERS[creature]
        player_id = self.repository.create_player(self.player_name or "Rookie", creature, spec.hp)
        self.repository.set_world_flag(player_id, f"avatar:{Overworld.AVATARS[self.avatar_selected]}")
        record = self.repository.load_player()
        self.player = self._to_player(record)
        self.saved_record = record
        self._enter_world()
        self.world.set_message(f"{creature} joins your journey! Find Rowan in Lakeside Village for a friendly first battle.")

    def _continue_game(self):
        record = self.repository.load_player()
        if record:
            self.player = self._to_player(record)
            self._enter_world()
            self.world.set_message(f"Welcome back, {self.player.name}. Your trail is waiting.")
        else:
            self.player_name, self.state = "", "name"

    @staticmethod
    def _to_player(record):
        # canonical_name upgrades saves made with the old starter ids (PYROX, TERRABIT).
        return Player(record.name, canonical_name(record.creature), record.level, record.hp, record.max_hp,
                      record.exp, record.x, record.y, record.player_id)

    def _enter_world(self):
        self.world = Overworld(self.player, self.rng, self.repository)
        self._refresh_boss_gate()
        self.save_timer = 0
        self.state = "overworld"

    def _refresh_boss_gate(self):
        if self.world and self.player:
            profile = self.repository.get_learning_profile(self.player.player_id)
            self.world.boss_ready = GameMasterAgent().boss_ready(profile, self.player.level)

    def _overworld_key(self, event):
        if event.key == pygame.K_ESCAPE and not self.world.dialogue:
            self.repository.save_player(self.player)
            self.saved_record = self.repository.load_player()
            self.state, self.battle = "menu", None
            return
        if event.key == pygame.K_b and not self.world.dialogue:
            self._start_battle(self._wild())
            return
        if event.key == pygame.K_n and not self.world.dialogue:
            self.map_screen = WorldMapScreen(self.world)
            self.state = "worldmap"
            return
        if event.key in (pygame.K_m, pygame.K_TAB) and not self.world.dialogue:
            names = {area_id: name for area_id, name, _ in self.world.world.areas}
            self.dex = MathDex(self.repository, self.player, names)
            self.state = "dex"
            return
        action = self.world.handle_key(event.key)
        if action == "battle":
            # Trainers like Rex send out their own MATHMON; practice battles pick a local wild one.
            rival = WILD_BY_NAME.get(self.world.duel_spec or "")
            self.world.duel_spec = None
            self._start_battle(rival or self._wild())
            if rival:
                self.battle.is_trainer = True
                self.battle.feedback = f"Your rival sends out {rival.name}! Show what you've learned."
        elif action == "boss":
            self._refresh_boss_gate()
            if self.world.boss_ready:
                self._start_battle(ENEMIES[3])
            else:
                master = GameMasterAgent()
                profile = self.repository.get_learning_profile(self.player.player_id)
                progress = master.boss_progress(profile, self.player.level)
                ready = sum(1 for line in progress if line.endswith("READY"))
                pages = ["The gate hums, but its stones stay dark. Three READY number skills will open the seal "
                         f"(you have {ready}/{master.SKILLS_NEEDED}).",
                         "   ".join(progress[:2]), "   ".join(progress[2:])]
                if self.player.level < master.BOSS_LEVEL:
                    pages.append(f"Your companion must also reach Lv {master.BOSS_LEVEL}.")
                pages.append("Tip: ATTACK questions now favour the skills you still need. Practise in tall grass or press B.")
                self.world.open_dialogue("THE SHADOW GATE", pages)

    def _wild(self):
        """A wild creature from the current area's habitat (meadow creatures outside tall-grass zones)."""
        return encounter_for(self.world.area_id if self.world else "meadow", self.rng)

    @staticmethod
    def _held_direction():
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        return int(dx), int(dy)

    def _start_battle(self, enemy=None):
        self.repository.save_player(self.player)
        self.battle = Battle(self.player, self.repository, self.orchestrator, self.llm, enemy, self.rng)
        self.state = "battle"

    def _update(self):
        if self.state == "battle" and self.battle:
            self.battle.update()
            if self.battle.closed:
                outcome = self.battle.outcome
                self.battle = None
                self.state = "overworld"
                self.saved_record = self.repository.load_player()
                self.world.resume()
                self.world.refresh_flags()
                self._refresh_boss_gate()
                if outcome == "befriended":
                    self.world.set_message("Captured! It joined your team. Press M to see your MathDex.", 300)
                elif outcome == "won":
                    self.world.set_message("Victory! Your creature grows stronger. The forest path is still open.")
                elif outcome == "defeated":
                    self.world.set_message("The ranger helps your creature recover. Keep exploring at your own pace.")
                else:
                    self.world.set_message("Back on the Number Forest trail.")
        if self.state == "overworld" and self.world:
            event = self.world.update(*self._held_direction())
            self.save_timer = getattr(self, "save_timer", 0) + 1
            if self.world.dirty and self.save_timer >= 180:
                self.repository.save_player(self.player)
                self.world.dirty, self.save_timer = False, 0
            if event == "encounter":
                # A roamer you touched brings its own species; a surprise from the grass picks one.
                spec, self.world.encounter_spec = self.world.encounter_spec, None
                self._start_battle(spec or self._wild())
        if self.state != self._last_state:
            # Starting a battle and leaving the title get a short fade-in from black.
            self.fade = self.FADE_FRAMES if self._last_state is not None else 0
            self._last_state = self.state
        elif self.fade:
            self.fade -= 1

    def _toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode((VIRTUAL_WIDTH * WINDOW_SCALE, VIRTUAL_HEIGHT * WINDOW_SCALE),
                                                  pygame.RESIZABLE)

    def _draw(self):
        ui.begin_frame()
        if self.state == "menu":
            self._draw_menu()
        elif self.state == "confirm_new":
            self._draw_confirm_new()
        elif self.state == "name":
            self._draw_name()
        elif self.state == "avatar":
            self._draw_avatar()
        elif self.state == "starter":
            self._draw_starter()
        elif self.state == "overworld" and self.world:
            self.world.draw(self.canvas, self.frame)
        elif self.state == "dex" and self.dex:
            self.dex.draw(self.canvas, self.frame)
        elif self.state == "worldmap" and self.map_screen:
            self.map_screen.draw(self.canvas, self.frame)
        elif self.state == "battle" and self.battle:
            self.battle.draw(self.canvas, self.frame)
        elif self.state == "profile":
            self._draw_profile()
        elif self.state == "settings":
            self._draw_settings()

    def _draw_menu(self):
        self.canvas.fill(PALETTE["ink"])
        # A quiet star field, tiny pixel motes, and a layered moonlit forest.
        for i in range(28):
            x = (i * 47 + 13) % VIRTUAL_WIDTH
            y = (i * 29 + 17) % 105
            pygame.draw.rect(self.canvas, PALETTE["muted"] if i % 3 else PALETTE["gold"], (x, y, 1 + (i % 2), 1 + (i % 2)))
        pygame.draw.circle(self.canvas, (229, 198, 132), (271, 34), 16)
        pygame.draw.circle(self.canvas, PALETTE["ink"], (278, 29), 15)
        for i in range(8):
            x = i * 44 - 12
            pygame.draw.polygon(self.canvas, (30 + i % 2 * 7, 61 + i % 3 * 6, 68),
                                [(x, 139), (x + 24, 78 + (i % 3) * 9), (x + 49, 139)])
            pygame.draw.rect(self.canvas, (35, 80, 60), (x + 18, 118, 10, 35))
        # Logo uses a shadow offset to suggest the old arcade title cards.
        float_y = 1 if self.frame % 90 < 45 else 0
        text(self.canvas, "MATHMON", (160, 56 + float_y), 48, PALETTE["coral"], center=True)
        text(self.canvas, "MATHMON", (158, 54 + float_y), 48, PALETTE["gold"], center=True)
        text(self.canvas, "TRAIN YOUR MIND. EVOLVE YOUR POWER.", (160, 81), 11, PALETTE["cream"], center=True)
        choices = list(self.MENU_CHOICES)
        disabled = ()
        if self.saved_record:
            choices[1] = f"CONTINUE  ({self.saved_record.name[:8]}, Lv {self.saved_record.level})"
        else:
            disabled = (1, 2)
        menu(self.canvas, (29, 113, 136, 96), choices, self.menu_selected, 10, self.frame, disabled)
        sprite_names = tuple(STARTERS)
        for i, name in enumerate(sprite_names):
            spec = STARTERS[name]
            pose = ("idle", "idle2", "idle3", "idle2")[(self.frame // 18 + i) % 4]
            draw_creature(self.canvas, spec, (204 + i * 44, 170 + (i % 2) * 6), 40, pose)
        panel(self.canvas, (170, 181, 143, 31), PALETTE["night"], PALETTE["leaf"])
        wrapped(self.canvas, self.menu_hint, (177, 187, 129, 20), 10, PALETTE["white"], 11, 2)
        text(self.canvas, "A SMALL WORLD OF BIG IDEAS", (160, 226), 10, PALETTE["muted"], center=True)

    def _draw_name(self):
        self.canvas.fill(PALETTE["ink"])
        text(self.canvas, "A NEW TRAIL BEGINS", (160, 52), 25, PALETTE["gold"], center=True)
        panel(self.canvas, (44, 99, 232, 62), PALETTE["night"])
        text(self.canvas, "What should the ranger call you?", (58, 111), 13, PALETTE["white"])
        caret = "_" if self.frame % 50 < 28 else " "
        if self.player_name:
            text(self.canvas, self.player_name + caret, (58, 135), 18, PALETTE["cream"])
        else:
            text(self.canvas, "Rookie" + caret, (58, 135), 18, PALETTE["muted"])
        text(self.canvas, "TYPE A NAME     ENTER: CONTINUE", (160, 184), 11, PALETTE["muted"], center=True)
        text(self.canvas, "ESC: BACK", (160, 215), 10, PALETTE["muted"], center=True)

    def _draw_avatar(self):
        from game import monster_sprites
        self.canvas.fill((37, 71, 77))
        text(self.canvas, "WHO ARE YOU?", (160, 24), 20, PALETTE["cream"], center=True)
        for i, name in enumerate(Overworld.AVATARS):
            chosen = i == self.avatar_selected
            x = 52 + i * 124
            lift = -4 if chosen else 0
            panel(self.canvas, (x, 52 + lift, 92, 136), PALETTE["night"] if chosen else PALETTE["ink"],
                  PALETTE["gold"] if chosen else PALETTE["leaf"])
            sheet = f"characters/{name}"
            if monster_sprites.available(sheet):
                pose = (1, 0, 2, 0)[self.frame // 10 % 4] if chosen else 0
                if chosen and self.frame // 60 % 4 == 3:
                    pose = 5  # cheer
                monster_sprites.draw(self.canvas, sheet, (x + 46, 160 + lift), 92, pose)
            text(self.canvas, name.title(), (x + 46, 172 + lift), 14, PALETTE["gold"], center=True)
        text(self.canvas, "LEFT/RIGHT: CHOOSE     ENTER: CONTINUE     ESC: BACK", (160, 214), 9, PALETTE["cream"], center=True)

    def _draw_starter(self):
        self.canvas.fill((37, 71, 77))
        text(self.canvas, "CHOOSE YOUR FIRST COMPANION", (160, 26), 20, PALETTE["cream"], center=True)
        keys = tuple(STARTERS)
        for i, name in enumerate(keys):
            x = 9 + i * 104
            spec = STARTERS[name]
            chosen = i == self.starter_selected
            border = PALETTE["gold"] if chosen else PALETTE["leaf"]
            lift = -4 if chosen else 0
            panel(self.canvas, (x, 68 + lift, 94, 124), PALETTE["night"] if chosen else PALETTE["ink"], border)
            hop = (self.frame % 24 // 12) * 2 if chosen else self.frame % 36 // 18
            pose = ("happy" if (self.frame // 50) % 4 == 3 else ("idle", "idle2", "idle3", "idle2")[self.frame // 16 % 4]) \
                if chosen else "idle"
            draw_creature(self.canvas, spec, (x + 47, 128 + lift - hop), 50, pose)
            text(self.canvas, name, (x + 47, 132), 14, PALETTE["gold"], center=True)
            text(self.canvas, spec.element + " TYPE", (x + 47, 148), 10, PALETTE["muted"], center=True)
            text(self.canvas, f"HP {spec.hp}   ATK {spec.attack}", (x + 47, 166), 10, PALETTE["white"], center=True)
        moods = ("Bold and bright, hits hardest.", "Calm and quick, well balanced.", "Steady and strong, most HP.")
        text(self.canvas, moods[self.starter_selected], (160, 206), 11, PALETTE["white"], center=True)
        text(self.canvas, "LEFT/RIGHT: CHOOSE     ENTER: BEGIN JOURNEY     ESC: BACK", (160, 226), 9, PALETTE["cream"], center=True)

    def _draw_confirm_new(self):
        self._draw_menu()
        overlay = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*PALETTE["ink"], 190))
        self.canvas.blit(overlay, (0, 0))
        ui.begin_frame()  # hide the menu's text beneath the dialog
        panel(self.canvas, (40, 78, 240, 86), PALETTE["night"], PALETTE["coral"])
        text(self.canvas, "START OVER?", (160, 92), 18, PALETTE["coral"], center=True)
        record = self.saved_record
        wrapped(self.canvas, f"This replaces {record.name}'s Lv {record.level} journey and learning journal.",
                (54, 106, 212, 30), 11, PALETTE["white"], 12, 2)
        text(self.canvas, "Y / ENTER: NEW GAME        N / ESC: KEEP SAVE", (160, 148), 10, PALETTE["gold"], center=True)

    def _draw_profile(self):
        self.canvas.fill(PALETTE["deep"])
        text(self.canvas, "RANGER'S LEARNING JOURNAL", (160, 13), 19, PALETTE["gold"], center=True)
        record = self.repository.load_player()
        if not record:
            wrapped(self.canvas, "Start a journey to build your learning journal.", (30, 54, 260, 50), 14, PALETTE["white"])
            text(self.canvas, "ENTER / ESC: BACK", (160, 213), 10, PALETTE["muted"], center=True)
            return
        if self.profile_summary is None:
            # The journal only changes between visits, so query it once rather than every frame.
            self.profile_summary = self.orchestrator.profile(record.player_id, record.level)
        summary = self.profile_summary
        topics = summary["topics"]
        panel(self.canvas, (10, 29, 300, 32), PALETTE["night"])
        accuracy = round(summary["summary"]["accuracy"] * 100)
        evolved_name = creature_spec(record.creature, record.level).name
        text(self.canvas, f"{record.name}   {evolved_name}   LV {record.level}", (18, 34), 12, PALETTE["white"])
        meter(self.canvas, 195, 48, 104, 7, summary["summary"]["correct"], max(1, summary["summary"]["attempted"]), PALETTE["mint"], f"ACCURACY {accuracy}%")
        labels = ("addition", "subtraction", "multiplication", "division")
        for i, topic in enumerate(labels):
            x = 10 + (i % 2) * 153
            y = 69 + (i // 2) * 43
            panel(self.canvas, (x, y, 145, 37), PALETTE["night"], PALETTE["leaf"])
            stats = topics.get(topic, {})
            pct = round(stats.get("accuracy", 0) * 100)
            text(self.canvas, topic.upper(), (x + 7, y + 5), 10, PALETTE["cream"])
            text(self.canvas, f"{pct}%   MASTERY {stats.get('mastery', 0)}", (x + 7, y + 19), 10, PALETTE["white"])
            if stats:
                meter(self.canvas, x + 90, y + 25, 47, 5, stats.get("mastery", 0), 100, PALETTE["sky"])
        if topics:
            strongest = max(topics, key=lambda key: topics[key].get("accuracy", 0))
            untried = [name for name in labels if name not in topics]
            weakest = untried[0] if untried else min(topics, key=lambda key: topics[key].get("mastery", 0))
            focus_line = f"STRONGEST: {strongest.upper()}   NEXT FOCUS: {weakest.upper()}"
        else:
            focus_line = "STRONGEST: —   NEXT FOCUS: YOUR FIRST PRACTICE"
        text(self.canvas, focus_line, (13, 153), 9, PALETTE["cream"])
        mistakes = summary["mistakes"]
        panel(self.canvas, (10, 166, 145, 45), PALETTE["night"])
        text(self.canvas, "RECENT MISTAKES", (17, 171), 10, PALETTE["gold"])
        if mistakes:
            recent = mistakes[0]
            wrapped(self.canvas, f"{recent['prompt'].replace('?', recent['expected'])}  (you said {recent['submitted']})",
                    (17, 184, 130, 23), 10, PALETTE["white"], 10, 2)
        else:
            text(self.canvas, "No mistakes on record yet.", (17, 184), 9, PALETTE["muted"])
        panel(self.canvas, (164, 166, 146, 45), PALETTE["night"])
        text(self.canvas, "AI LEARNING TIP", (171, 171), 10, PALETTE["gold"])
        recommendation = summary["recommendations"][0] if summary["recommendations"] else summary["next_step"]
        wrapped(self.canvas, recommendation, (171, 184, 131, 23), 9, PALETTE["white"], 10, 2)
        text(self.canvas, "ESC / ENTER: BACK", (160, 226), 10, PALETTE["muted"], center=True)

    def _draw_settings(self):
        self.canvas.fill(PALETTE["ink"])
        text(self.canvas, "FIELD SETTINGS", (160, 53), 24, PALETTE["gold"], center=True)
        options = ["SCANLINE EFFECT: " + ("ON" if self.scanlines else "OFF"), "BACK TO TITLE"]
        menu(self.canvas, (77, 103, 166, 46), options, self.settings_selected, 12, self.frame)
        text(self.canvas, "UP/DOWN: CHOOSE     ENTER: CHANGE     ESC: BACK", (160, 180), 10, PALETTE["muted"], center=True)
        text(self.canvas, "F11 or ALT+ENTER toggles fullscreen", (160, 196), 10, PALETTE["muted"], center=True)

    def _present(self):
        win_w, win_h = self.window.get_size()
        scale = min(win_w / VIRTUAL_WIDTH, win_h / VIRTUAL_HEIGHT)
        if scale >= 1:
            scale = int(scale)  # whole-number scaling keeps every pixel the same size
        scale = max(scale, 0.25)
        size = (int(VIRTUAL_WIDTH * scale), int(VIRTUAL_HEIGHT * scale))
        offset = ((win_w - size[0]) // 2, (win_h - size[1]) // 2)
        if offset != (0, 0):
            self.window.fill((0, 0, 0))
        self.window.blit(pygame.transform.scale(self.canvas, size), offset)
        ui.flush_text(self.window, scale, offset)
        if self.scanlines:
            self._draw_scanlines(size, offset)
        if self.fade:
            shade = pygame.Surface(size)
            shade.set_alpha(int(255 * self.fade / self.FADE_FRAMES))
            self.window.blit(shade, offset)
        pygame.display.flip()

    def _draw_scanlines(self, size, offset):
        cached = getattr(self, "_scanline_surface", None)
        if cached is None or cached.get_size() != size:
            cached = pygame.Surface(size, pygame.SRCALPHA)
            for y in range(0, size[1], 3):
                pygame.draw.line(cached, (0, 0, 0, 70), (0, y), (size[0], y))
            self._scanline_surface = cached
        self.window.blit(cached, offset)

    def _shutdown(self):
        if self.player:
            self.repository.save_player(self.player)
        self.llm.close()
        pygame.quit()
        sys.exit(0)

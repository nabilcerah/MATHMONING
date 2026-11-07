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
from game.creatures import ENEMIES, STARTERS, creature_spec, pixel_monster
from game.overworld import Overworld
from game.player import Player
from game.ui import menu, meter, panel, text, wrapped


class GameManager:
    MENU_CHOICES = ("NEW GAME", "CONTINUE", "PLAYER PROFILE", "SETTINGS", "EXIT")

    def __init__(self, database_path=None):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.window = pygame.display.set_mode((VIRTUAL_WIDTH * WINDOW_SCALE, VIRTUAL_HEIGHT * WINDOW_SCALE))
        self.canvas = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT))
        self.clock = pygame.time.Clock()
        self.database = Database(database_path)
        self.repository = PlayerRepository(self.database)
        self.orchestrator = AgentOrchestrator(self.repository)
        self.llm = LLMProvider()
        self.saved_record = self.repository.load_player()
        self.player = None
        self.world = None
        self.battle = None
        self.state = "menu"
        self.menu_selected = 0
        self.starter_selected = 0
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
        if self.state == "battle" and self.battle:
            self.battle.handle_event(event)
            return
        if event.type != pygame.KEYDOWN:
            return
        if self.state == "menu":
            self._menu_key(event)
        elif self.state == "name":
            if event.key == pygame.K_RETURN:
                self.state = "starter"
            elif event.key == pygame.K_ESCAPE:
                self.state = "menu"
            elif event.key == pygame.K_BACKSPACE:
                self.player_name = self.player_name[:-1]
            elif event.unicode and event.unicode.isprintable() and event.unicode not in "\r\n" and len(self.player_name) < 18:
                self.player_name += event.unicode
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

    def _menu_key(self, event):
        if event.key in (pygame.K_UP, pygame.K_w):
            self.menu_selected = (self.menu_selected - 1) % len(self.MENU_CHOICES)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.menu_selected = (self.menu_selected + 1) % len(self.MENU_CHOICES)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            choice = self.MENU_CHOICES[self.menu_selected]
            if choice == "NEW GAME":
                self.player_name, self.state = "", "name"
            elif choice == "CONTINUE":
                self._continue_game()
            elif choice == "PLAYER PROFILE":
                if self.saved_record:
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
        self.repository.create_player(self.player_name or "Rookie", creature, spec.hp)
        record = self.repository.load_player()
        self.player = self._to_player(record)
        self.saved_record = record
        self.world = Overworld(self.player, self.rng)
        self.world.set_message(f"{creature} joins your journey! Talk to Rowan for a friendly first battle.")
        self.state = "overworld"

    def _continue_game(self):
        record = self.repository.load_player()
        if record:
            self.player = self._to_player(record)
            self.world = Overworld(self.player, self.rng)
            self.state = "overworld"
            self.world.set_message(f"Welcome back, {self.player.name}. Your trail is waiting.")
        else:
            self.player_name, self.state = "", "name"

    @staticmethod
    def _to_player(record):
        return Player(record.name, record.creature, record.level, record.hp, record.max_hp,
                      record.exp, record.x, record.y, record.player_id)

    def _overworld_key(self, event):
        directions = {
            pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
            pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
            pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
            pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
        }
        if event.key in directions:
            result = self.world.move(*directions[event.key])
            if result != "blocked":
                self.repository.save_player(self.player)
            if result == "encounter":
                self._start_battle()
        elif event.key == pygame.K_e:
            action = self.world.interact()
            if action == "guide":
                if self.world.awaiting_duel:
                    self._start_battle()
                else:
                    self.world.awaiting_duel = True
                    self.world.set_message("ROWAN: Ready for a friendly practice battle? Press E again!")
            elif action == "sign":
                self.world.set_message("TRAIL SIGN: Explore the tall grass, then follow the stone path to the old arch.")
            elif action == "arch":
                profile = self.repository.get_learning_profile(self.player.player_id)
                if GameMasterAgent().boss_ready(profile, self.player.level):
                    self._start_battle(ENEMIES[3])
                else:
                    self.world.set_message("The arch glows faintly. Build practice in three number skills and return when ready.")
            else:
                self.world.set_message("No one is nearby. Try the ranger hut or the old stone arch.")
        elif event.key == pygame.K_b:
            self._start_battle()
        elif event.key == pygame.K_ESCAPE:
            self.repository.save_player(self.player)
            self.saved_record = self.repository.load_player()
            self.state, self.battle = "menu", None

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
                if outcome == "won":
                    self.world.set_message("Victory! Your creature grows stronger. The forest path is still open.")
                elif outcome == "defeated":
                    self.world.set_message("The ranger helps your creature recover. Keep exploring at your own pace.")
                else:
                    self.world.set_message("Back on the Number Forest trail.")
        if self.state == "overworld" and self.world:
            self.world.tick()

    def _draw(self):
        if self.state == "menu":
            self._draw_menu()
        elif self.state == "name":
            self._draw_name()
        elif self.state == "starter":
            self._draw_starter()
        elif self.state == "overworld" and self.world:
            self.world.draw(self.canvas, self.frame)
        elif self.state == "battle" and self.battle:
            self.battle.draw(self.canvas, self.frame)
        elif self.state == "profile":
            self._draw_profile()
        elif self.state == "settings":
            self._draw_settings()
        if self.scanlines:
            for y in range(1, VIRTUAL_HEIGHT, 3):
                pygame.draw.line(self.canvas, (0, 0, 0), (0, y), (VIRTUAL_WIDTH, y), 1)

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
        font = pygame.font.Font(None, 48)
        logo = font.render("MATHMON", False, PALETTE["gold"])
        shadow = font.render("MATHMON", False, PALETTE["coral"])
        self.canvas.blit(shadow, shadow.get_rect(center=(162, 58)))
        self.canvas.blit(logo, logo.get_rect(center=(158, 54)))
        text(self.canvas, "TRAIN YOUR MIND. EVOLVE YOUR POWER.", (160, 79), 11, PALETTE["cream"], center=True)
        panel(self.canvas, (29, 107, 127, 112), PALETTE["night"])
        if not hasattr(self, "menu_hint"):
            self.menu_hint = "A little practice can unlock a mighty adventure."
        choices = list(self.MENU_CHOICES)
        if not self.saved_record:
            choices[1] = "CONTINUE  ·  NO SAVE"
        menu(self.canvas, (39, 113, 111, 96), choices, self.menu_selected, 10)
        sprite_names = tuple(STARTERS)
        for i, name in enumerate(sprite_names):
            spec = STARTERS[name]
            pixel_monster(self.canvas, 190 + i * 36, 130 + (i % 2) * 13 + (self.frame % 36 // 18), spec, 2)
        panel(self.canvas, (170, 181, 143, 31), PALETTE["night"], PALETTE["leaf"])
        wrapped(self.canvas, self.menu_hint, (177, 187, 129, 20), 10, PALETTE["white"], 11, 2)
        text(self.canvas, "A SMALL WORLD OF BIG IDEAS", (160, 226), 10, PALETTE["muted"], center=True)

    def _draw_name(self):
        self.canvas.fill(PALETTE["ink"])
        text(self.canvas, "A NEW TRAIL BEGINS", (160, 52), 25, PALETTE["gold"], center=True)
        panel(self.canvas, (44, 99, 232, 62), PALETTE["night"])
        text(self.canvas, "What should the ranger call you?", (58, 111), 13, PALETTE["white"])
        text(self.canvas, (self.player_name or "ROOKIE") + "_", (58, 135), 18, PALETTE["cream"])
        text(self.canvas, "TYPE A NAME     ENTER: CONTINUE", (160, 184), 11, PALETTE["muted"], center=True)
        text(self.canvas, "ESC: BACK", (160, 215), 10, PALETTE["muted"], center=True)

    def _draw_starter(self):
        self.canvas.fill((37, 71, 77))
        text(self.canvas, "CHOOSE YOUR FIRST COMPANION", (160, 26), 20, PALETTE["cream"], center=True)
        keys = tuple(STARTERS)
        for i, name in enumerate(keys):
            x = 9 + i * 104
            spec = STARTERS[name]
            border = PALETTE["gold"] if i == self.starter_selected else PALETTE["leaf"]
            panel(self.canvas, (x, 68, 94, 124), PALETTE["night"], border)
            pixel_monster(self.canvas, x + 28, 78 + (self.frame % 36 // 18), spec, 3)
            text(self.canvas, name, (x + 47, 132), 14, PALETTE["gold"], center=True)
            text(self.canvas, spec.element + " TYPE", (x + 47, 148), 10, PALETTE["muted"], center=True)
            text(self.canvas, f"HP {spec.hp}   ATK {spec.attack}", (x + 47, 166), 10, PALETTE["white"], center=True)
        text(self.canvas, "← → TO CHOOSE     ENTER: BEGIN JOURNEY", (160, 207), 11, PALETTE["cream"], center=True)
        text(self.canvas, "PYROX: bold and bright   AQUABIT: calm and quick   TERRABIT: steady and strong", (160, 228), 9, PALETTE["muted"], center=True)

    def _draw_profile(self):
        self.canvas.fill(PALETTE["deep"])
        text(self.canvas, "RANGER'S LEARNING JOURNAL", (160, 13), 19, PALETTE["gold"], center=True)
        record = self.repository.load_player()
        if not record:
            wrapped(self.canvas, "Start a journey to build your learning journal.", (30, 54, 260, 50), 14, PALETTE["white"])
            text(self.canvas, "ENTER / ESC: BACK", (160, 213), 10, PALETTE["muted"], center=True)
            return
        summary = self.orchestrator.profile(record.player_id, record.level)
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
            weakest = min(topics, key=lambda key: topics[key].get("mastery", 0))
            focus_line = f"STRONGEST: {strongest.upper()}   NEXT FOCUS: {weakest.upper()}"
        else:
            focus_line = "STRONGEST: —   NEXT FOCUS: YOUR FIRST PRACTICE"
        text(self.canvas, focus_line, (13, 153), 9, PALETTE["cream"])
        mistakes = summary["mistakes"]
        panel(self.canvas, (10, 166, 145, 45), PALETTE["night"])
        text(self.canvas, "RECENT MISTAKES", (17, 171), 10, PALETTE["gold"])
        if mistakes:
            recent = mistakes[0]
            wrapped(self.canvas, f"{recent['topic']}: {recent['prompt']} → {recent['submitted']}",
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
        menu(self.canvas, (77, 103, 166, 62), options, self.settings_selected, 12)
        text(self.canvas, "↑ ↓ CHOOSE     ENTER: CHANGE", (160, 193), 10, PALETTE["muted"], center=True)

    def _present(self):
        scaled = pygame.transform.scale(self.canvas, self.window.get_size())
        self.window.blit(scaled, (0, 0))
        pygame.display.flip()

    def _shutdown(self):
        if self.player:
            self.repository.save_player(self.player)
        self.llm.close()
        pygame.quit()
        sys.exit(0)

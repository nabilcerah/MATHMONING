"""The one main loop (GDD 22) and the top-level flow between states.

Events, updates, rendering and frame timing all happen in ``run_async``. Which screen receives
them is decided by the StateManager: a named full-screen state (menu, overworld, battle, ...)
plus a stack of overlay screens (trainer menu, party, sanctuary, bag, shop, quests, profile,
evolution, puzzle challenges, pause).
"""
import asyncio
import random
import sys

import pygame

from ai.llm_provider import LLMProvider
from ai.orchestrator import AgentOrchestrator
from combat import reward_manager
from config import DATABASE_PATH, FPS, PALETTE, TITLE, VIRTUAL_HEIGHT, VIRTUAL_WIDTH, WEB, WINDOW_SCALE
from database.database import Database
from database.player_repository import PlayerRepository
from game import audio, ui, web_storage
from game.arena import ArenaScreen
from game.battle import BattleScreen, RepositoryBag
from game.creatures import STARTERS, draw_creature
from game.monster_battle import MonsterBattleScreen
from game.overworld import Overworld
from game.player import Player
from game.puzzle_screen import PuzzleScreen
from game.state_manager import StateManager
from game.team import Team
from game.touch_controls import TouchControls
from game.trials_screen import TrialsScreen
from game.ui import menu, meter, panel, text, wrapped
from game.worldmap_screen import WorldMapScreen
from mathematics import curriculum
from monsters import elemental_system, monster_factory
from monsters.monster_data import canonical_species, encounters, rules
from states.challenge_state import ChallengeScreen
from states.dex_state import DexScreen
from states.evolution_state import EvolutionScreen
from states.inventory_state import InventoryScreen
from states.party_state import PartyScreen
from states.pause_state import PauseScreen
from states.player_profile_state import ProfileScreen
from states.quest_state import QuestScreen
from states.sanctuary_state import SanctuaryScreen
from states.shop_state import ShopScreen
from states.trainer_menu import TrainerMenu
from world.quest_manager import QuestManager

SEALS = ("challenge:seal_add", "challenge:seal_mul", "challenge:seal_frac")


class GameManager:
    MAPS = ("number_forest", "crystal_realm", "village_shop", "village_sanctuary",
            "algebra_cavern", "geometry_kingdom", "chronos_dimension", "village_recovery")
    BOSS_FLAG = "boss:numerex"
    MENU_CHOICES = ("NEW GAME", "CONTINUE", "SETTINGS", "EXIT")
    FADE_FRAMES = 14
    REGION_MIN_DIFFICULTY = {"crystal_realm": "intermediate", "geometry_kingdom": "intermediate",
                             "chronos_dimension": "intermediate"}

    def __init__(self, database_path=None):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.fullscreen = False
        if WEB:
            self.window = pygame.display.set_mode(self._browser_size() or (1280, 720))
        else:
            self.window = pygame.display.set_mode((VIRTUAL_WIDTH * WINDOW_SCALE, VIRTUAL_HEIGHT * WINDOW_SCALE),
                                                  pygame.RESIZABLE)
        self.touch = TouchControls()
        self.canvas = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT))
        ui.set_text_layer(self.canvas)
        self.menu_hint = "A little practice can unlock a mighty adventure."
        self.fade = 0
        self._last_state = None
        self.clock = pygame.time.Clock()
        if WEB and database_path is None:
            web_storage.restore(DATABASE_PATH)
        self.database = Database(database_path)
        self.persister = web_storage.Persister(self.database.path)
        self.repository = PlayerRepository(self.database)
        self.rng = random.Random()
        self.llm = LLMProvider()
        self.orchestrator = AgentOrchestrator(self.repository, rng=self.rng, llm=self.llm)
        self.saved_record = self.repository.load_player()
        self.states = StateManager("menu")
        self.player = None
        self.party = None
        self.quests = None
        self.world = None
        self.battle = None
        self.map_screen = None
        self.puzzle = None
        self.puzzle_id = None
        self.arena = None
        self.trials = None
        self.monster_battle = None
        self.recovery_text = ""
        self.menu_selected = 0
        self.starter_selected = 0
        self.avatar_selected = 0
        self.settings_selected = 0
        self.scanlines = False
        self.sound = True
        self.player_name = ""
        self.frame = 0
        self.running = True
        self.save_timer = 0
        pygame.key.set_repeat(220, 105)

    # ================================================================== state
    @property
    def state(self):
        return self.states.state

    @state.setter
    def state(self, value):
        self.states.change(value)

    def run(self):
        asyncio.run(self.run_async())

    async def run_async(self):
        """The game loop. It yields to the event loop every frame so it can run in a browser (pygbag)."""
        while self.running:
            self.frame += 1
            for event in pygame.event.get():
                if self.touch.handle(event, self.window.get_size()):
                    continue
                self._handle_event(event)
            self.touch.update()
            if WEB and self.frame % 15 == 0:
                self._fit_browser_window()
            self._update()
            self._draw()
            self._present()
            if WEB and self.frame % 300 == 0:
                self.persister.sync()
            self.clock.tick(FPS)
            await asyncio.sleep(0)
        self._shutdown()

    # ================================================================== input
    def _handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.KEYDOWN and (event.key == pygame.K_F11 or
                                             (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT)):
            self._toggle_fullscreen()
            return
        if self.states.handle_event(event):
            return
        if self.state == "battle" and self.battle:
            self.battle.handle_event(event)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.state in ("menu", "starter", "avatar"):
            self._menu_click(ui.to_virtual(event.pos))
            return
        if event.type != pygame.KEYDOWN:
            return
        handler = {"menu": self._menu_key, "name": self._name_key, "confirm_new": self._confirm_key,
                   "avatar": self._avatar_key, "starter": self._starter_key, "settings": self._settings_key,
                   "overworld": self._overworld_key, "recovery": self._recovery_key}.get(self.state)
        if handler:
            handler(event)
        elif self.state == "arena" and self.arena:
            self.arena.handle_key(event.key, event.unicode)
            if self.arena.closed:
                summary, self.arena = self.arena.summary, None
                self._back_to_world(summary or "Come back to the Arena any time!")
        elif self.state == "trials" and self.trials:
            self.trials.handle_key(event.key)
            if self.trials.closed:
                challenge, self.trials = self.trials.challenge, None
                if challenge:
                    self.save_all()
                    self.monster_battle = MonsterBattleScreen(self.repository, self.player, challenge[0], challenge[1],
                                                              self.rng, self._team())
                    self.state = "mbattle"
                else:
                    self._back_to_world("The Trials hall is open whenever you press T.")
        elif self.state == "mbattle" and self.monster_battle:
            self.monster_battle.handle_key(event.key, event.unicode)
            if self.monster_battle.closed:
                self.monster_battle = None
                self._reload_party()
                self.trials = TrialsScreen(self.repository, self.player, self._team())
                self.state = "trials"
        elif self.state == "puzzle" and self.puzzle:
            self.puzzle.handle_key(event.key, event.unicode)
            if self.puzzle.closed:
                self._close_puzzle()
        elif self.state == "worldmap" and self.map_screen:
            self.map_screen.handle_key(event.key)
            if self.map_screen.closed:
                if self.map_screen.travel_to:
                    cell, name = self.map_screen.travel_to
                    self.world.teleport(cell)
                    self.save_all()
                    self.world.set_message(f"You travel to {name}.", 150)
                self.map_screen = None
                self.state = "overworld"

    def _menu_click(self, pos):
        if self.state == "menu":
            index = ui.menu_index((29, 113, 136, 70), len(self.MENU_CHOICES), pos, 15)
            if index is not None:
                self.menu_selected = index
                self._menu_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r"))
        elif self.state == "starter":
            for i in range(len(STARTERS)):
                if 6 + i * 78 <= pos[0] < 6 + i * 78 + 74 and 30 <= pos[1] < 140:
                    if i == self.starter_selected:
                        self._create_new_player()
                    self.starter_selected = i
        elif self.state == "avatar":
            self.avatar_selected = 0 if pos[0] < 160 else 1

    def _menu_key(self, event):
        if event.key in (pygame.K_UP, pygame.K_w):
            self.menu_selected = (self.menu_selected - 1) % len(self.MENU_CHOICES)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.menu_selected = (self.menu_selected + 1) % len(self.MENU_CHOICES)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            choice = self.MENU_CHOICES[self.menu_selected]
            if choice == "NEW GAME":
                self.state = "confirm_new" if self.saved_record else "name"
                self.player_name = ""
            elif choice == "CONTINUE":
                if self.saved_record:
                    self._continue_game()
                else:
                    self.menu_hint = "No saved journey yet. Choose NEW GAME to begin."
            elif choice == "SETTINGS":
                self.state = "settings"
            elif choice == "EXIT":
                self.running = False

    def _name_key(self, event):
        if event.key == pygame.K_RETURN:
            self.state = "avatar"
        elif event.key == pygame.K_ESCAPE:
            self.state = "menu"
        elif event.key == pygame.K_BACKSPACE:
            self.player_name = self.player_name[:-1]
        elif event.unicode and event.unicode.isprintable() and event.unicode not in "\r\n" and len(self.player_name) < 18:
            self.player_name += event.unicode

    def _confirm_key(self, event):
        if event.key in (pygame.K_y, pygame.K_RETURN):
            self.player_name, self.state = "", "name"
        elif event.key in (pygame.K_n, pygame.K_ESCAPE):
            self.state = "menu"

    def _avatar_key(self, event):
        if event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            self.avatar_selected = 1 - self.avatar_selected
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.state = "starter"
        elif event.key == pygame.K_ESCAPE:
            self.state = "name"

    def _starter_key(self, event):
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self.starter_selected = (self.starter_selected - 1) % len(STARTERS)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.starter_selected = (self.starter_selected + 1) % len(STARTERS)
        elif pygame.K_1 <= event.key <= pygame.K_4:
            self.starter_selected = event.key - pygame.K_1
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._create_new_player()
        elif event.key == pygame.K_ESCAPE:
            self.state = "avatar"

    def _settings_key(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "menu"
        elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
            step = -1 if event.key in (pygame.K_UP, pygame.K_w) else 1
            self.settings_selected = (self.settings_selected + step) % 3
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.settings_selected == 0:
                self.scanlines = not self.scanlines
            elif self.settings_selected == 1:
                self.sound = not self.sound
                audio.set_enabled(self.sound)
            else:
                self.state = "menu"

    def _recovery_key(self, event):
        if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_e):
            self.state = "overworld"
            self.world.set_message("Your party is fully healed. Keep exploring at your own pace.", 200)

    # ================================================================== new game / continue
    def _create_new_player(self):
        species_id = tuple(STARTERS)[self.starter_selected]
        player_id = self.repository.create_player(self.player_name or "Rookie", species_id)
        self.repository.set_world_flag(player_id, f"avatar:{Overworld.AVATARS[self.avatar_selected]}")
        record = self.repository.load_player()
        self._load(record)
        messages = self.quests.start_auto_quests()
        self._enter_world()
        self.world.set_message(f"{STARTERS[species_id].name} joins your journey! Talk to Professor Numeris in the "
                               "village square.", 300)
        del messages

    def _continue_game(self):
        record = self.repository.load_player()
        if not record:
            self.player_name, self.state = "", "name"
            return
        self._load(record)
        self.quests.start_auto_quests()
        self._enter_world()
        self.world.set_message(f"Welcome back, {self.player.name}. Your trail is waiting.")

    def _load(self, record):
        world = record.world if record.world in self.MAPS else "number_forest"
        self.player = Player(record.name, canonical_species(record.creature), record.level, record.hp, record.max_hp,
                             record.exp, record.x, record.y, record.player_id, world)
        self.party = self.repository.load_party(record.player_id)
        self.saved_record = record
        self.quests = QuestManager(self.repository, record.player_id,
                                   flags=lambda: self.world.flags if self.world else
                                   self.repository.world_flags(record.player_id))
        self.orchestrator.quest_manager = self.quests
        self.orchestrator.region = world if world in curriculum.REGION_TOPICS else "number_forest"

    def _play_music(self, boss=False):
        if boss:
            audio.music("boss")
        elif self.state in ("battle", "mbattle"):
            audio.music("battle")
        elif self.state in ("menu", "name", "avatar", "starter", "settings", "confirm_new"):
            audio.music("menu")
        elif self.player:
            audio.music(self.player.world)      # each world has its own theme

    def _enter_world(self):
        self.world = Overworld(self.player, self.rng, self.repository, self.player.world, self.party, self.quests,
                               self.on_world_event)
        self._refresh_boss_gate()
        self.save_timer = 0
        self.states.clear()
        self.state = "overworld"
        self._play_music()

    # ================================================================== saving

    def _sync_player(self):
        lead = self.party.lead if self.party and self.party.party else None
        if lead:
            self.player.creature, self.player.level = lead.species_id, lead.level
            self.player.hp, self.player.max_hp, self.player.exp = lead.hp, lead.max_hp, lead.exp

    def save_party(self):
        if self.party and self.player:
            self.repository.save_party(self.player.player_id, self.party)

    def save_all(self):
        if not self.player:
            return
        self.save_party()
        self._sync_player()
        self.repository.save_player(self.player)
        self.saved_record = self.repository.load_player()
        if WEB:
            self.persister.sync()

    def _reload_party(self):
        self.party = self.repository.load_party(self.player.player_id)
        if self.world:
            self.world.party = self.party
            self.world.refresh_flags()

    def _team(self):
        return Team(self.repository, self.player, party=self.party)

    # ================================================================== helpers used by screens
    def party_level(self):
        return max((m.level for m in self.party.party), default=1) if self.party else 1

    def boss_gate(self):
        """The current map's boss gate entry (seals, boss, level, texts), or None."""
        if not self.world:
            return None
        return next((e for e in self.world.objects.values() if e.get("kind") == "boss_gate"), None)

    def gate_seals(self, gate=None):
        gate = gate or self.boss_gate()
        return tuple(gate.get("seals", SEALS)) if gate else SEALS

    def seals_done(self, gate=None):
        flags = self.world.flags if self.world else set()
        return all(flag in flags for flag in self.gate_seals(gate))

    def on_shop_change(self):
        pass

    def after_evolution(self, monster):
        self.save_all()
        self.repository.add_recommendation(self.player.player_id,
                                           f"{monster.name} evolved! Keep practising {curriculum.label(monster.mastery_topic).lower()}.")

    def open_screen(self, name):
        screens = {"party": PartyScreen, "bag": InventoryScreen, "quests": QuestScreen, "mathdex": DexScreen,
                   "profile": ProfileScreen, "shop": ShopScreen, "sanctuary": SanctuaryScreen,
                   "evolution": EvolutionScreen}
        screen = screens[name](self)
        self.states.push(screen, self._screen_closed)
        return screen

    def _screen_closed(self, screen):
        if self.world:
            self.world.refresh_flags()
        self._refresh_boss_gate()

    def _pause_closed(self, screen):
        if screen.result == "main_menu":
            self.states.clear()
            self.state, self.battle = "menu", None
            self.saved_record = self.repository.load_player()

    def open_clinic(self):
        from states.clinic_state import ClinicScreen
        screen = ClinicScreen(self)
        self.states.push(screen, self._screen_closed)
        return screen

    def open_challenge(self, challenge_id):
        screen = ChallengeScreen(self, challenge_id)
        self.states.push(screen, self._challenge_closed)
        return screen

    def _challenge_closed(self, screen):
        if screen.result:
            self.world.set_flag(f"challenge:{screen.challenge_id}")
            messages, done = self.quests.notify("challenge", id=screen.challenge_id)
            self._quest_feedback(messages, done, f"{screen.spec['title']}: solved!")
            seals = self.gate_seals()
            if f"challenge:{screen.challenge_id}" in seals:
                count = sum(1 for flag in seals if self.world.has_flag(flag))
                gate = self.boss_gate() or {}
                self.world.set_message(f"{screen.spec['title'].title()} glows again! ({count}/{len(seals)} restored)" +
                                       (f"  {gate.get('title', 'The gate').title()} is open!" if count == len(seals)
                                        else ""), 260)
        self.save_all()
        self._refresh_boss_gate()

    # ================================================================== quests & world events
    def on_world_event(self, kind, **data):
        if not self.quests:
            return
        if kind == "visit" and data.get("first") and data.get("area") in encounters()["areas"]:
            exp = rules()["exp"]["discovery"]
            lead = self.party.lead
            lead.add_exp(exp)
            self.save_party()
            self.world.set_message(f"Discovered {data.get('name', 'a new place')}! {lead.name} +{exp} EXP.", 200)
        if kind == "healed":
            self.save_party()
            return
        messages, done = self.quests.notify(kind, **data)
        self._quest_feedback(messages, done)

    def _quest_feedback(self, messages, completed, prefix=""):
        for quest_id in completed:
            exp = self.quests.definition(quest_id).get("rewards", {}).get("exp", 0)
            if exp:
                reward_manager.distribute_exp(self.party.party, self.party.lead, exp)
        if completed:
            self.save_all()
            if self.world:
                self.world.refresh_flags()
        text_ = " ".join(([prefix] if prefix else []) + messages)
        if text_ and self.world:
            self.world.set_message(text_, 300)

    def _refresh_boss_gate(self):
        if self.world:
            self.world.boss_ready = self.seals_done()

    # ================================================================== overworld
    def _overworld_key(self, event):
        world = self.world
        if world.dialogue:
            action = world.handle_key(event.key)
            self._world_action(action)
            return
        if event.key == pygame.K_ESCAPE:
            self.save_all()
            self.states.push(PauseScreen(self), self._pause_closed)
            return
        if event.key == pygame.K_TAB:
            self.states.push(TrainerMenu(self), self._screen_closed)
            return
        if event.key == pygame.K_m:
            self.open_screen("mathdex")
            return
        if event.key == pygame.K_t:
            self.save_all()
            self.trials = TrialsScreen(self.repository, self.player, self._team())
            self.state = "trials"
            return
        if event.key == pygame.K_n and not world.world.interior:
            self.map_screen = WorldMapScreen(world)
            self.state = "worldmap"
            return
        self._world_action(world.handle_key(event.key))

    def _world_action(self, action):
        if not action:
            return
        if action == "arena":
            self.arena = ArenaScreen(self.repository, self.orchestrator, self.player, self.party.lead.spec,
                                     self.world.avatar.sheet, self.rng)
            self.state = "arena"
        elif isinstance(action, tuple) and action[0] == "travel_map":
            self._travel_to_map(action[1], action[2])
        elif isinstance(action, tuple) and action[0] == "puzzle":
            self._open_puzzle(action[1])
        elif isinstance(action, tuple) and action[0] == "challenge":
            self.open_challenge(action[1])
        elif action in ("shop", "sanctuary", "evolution"):
            if action == "evolution" and not self.repository.item_count(self.player.player_id, "Evolution Crystal"):
                self.world.open_dialogue("EVOLUTION SHRINE", [
                    "The shrine's crystal is dark. It needs an EVOLUTION CRYSTAL to awaken.",
                    "Legend says the Crystal Seal on Waterfall Plateau holds one."])
                return
            if action == "sanctuary":
                self.party.heal_all(1.0)
                self.save_party()
            self.open_screen(action)
        elif action == "clinic":
            self.open_clinic()
        elif action == "heal":
            healed = self.party.heal_all(1.0)
            self.save_party()
            self.world.open_dialogue("SAGE ILO", [f"There we go - your party is fully healed (+{healed} HP)."
                                                  if healed else "Your party is already in perfect health!"])
        elif action == "battle":
            duel = self.world.duel_spec or {"species": "DIVOWL", "level": 2}
            self.world.duel_spec = None
            enemy = monster_factory.create(duel["species"], duel["level"])
            self._start_battle(enemy, "trainer", self.world.duel_name)
        elif action == "boss":
            self._boss_gate()
        elif action == "boss_fight":
            self._start_boss()

    def _boss_gate(self):
        """Every world's boss gate works the same way; its seals, boss and texts are map data."""
        gate = self.boss_gate() or {}
        title = gate.get("title", "THE GATE")
        if self.world.has_flag(gate.get("flag", self.BOSS_FLAG)):
            self.world.open_dialogue(title, [gate.get("quiet", "All is quiet here now.")])
            return
        seals = self.gate_seals(gate)
        if not self.seals_done(gate):
            count = sum(1 for flag in seals if self.world.has_flag(flag))
            self.world.open_dialogue(title, [f"{gate.get('sealed', 'Seals bind the gate.')} {count}/{len(seals)} "
                                             "have been restored.", gate.get("where", "")])
            return
        advice = self.orchestrator.recommendations(self.player.player_id, self.party_level(), True)
        self.world.open_dialogue(title, [gate.get("open", "The gate opens..."),
                                         "AI Game Master: " + advice.extra.get("boss_advice", "")],
                                 choices=[(gate.get("fight", "Fight!"), "boss_fight"), ("Prepare first", "close")])

    def _start_boss(self):
        gate = self.boss_gate() or {}
        cfg = encounters()["boss"]
        enemy = monster_factory.create(gate.get("boss", cfg["species"]), gate.get("level", cfg["level"]))
        self.boss_in_progress = gate
        self._start_battle(enemy, "boss")

    def _travel_to_map(self, map_id, cell):
        self.player.world = map_id
        self.player.x, self.player.y = cell
        self.orchestrator.region = map_id if map_id in curriculum.REGION_TOPICS else self.orchestrator.region
        self.save_all()
        self._enter_world()
        if not self.world.world.interior:
            self.world.set_message(f"You arrive in {self.world.world.name}.", 160)

    # ------------------------------------------------------------------ puzzle shrines (bonus)
    PUZZLE_REWARDS = {"sequence": (12, "Math Potion"), "balance": (15, "Energy Potion"),
                      "target": (20, "Basic Mathball"), "magic": (25, "Greater Potion"), "starchart": (30, None)}

    def _open_puzzle(self, shrine_id):
        entry = self.world.objects[shrine_id]
        level = self.party_level()
        tier = 0 if level < 4 else 1 if level < 8 else 2
        tier = max(tier, int(entry.get("min_tier", 0)))
        rng = random.Random(f"{shrine_id}:{self.world.today}:{self.player.player_id}")
        self.puzzle = PuzzleScreen(entry["puzzle"], tier, rng, entry.get("title"))
        self.puzzle_id = shrine_id
        self.state = "puzzle"

    def _close_puzzle(self):
        puzzle, shrine_id = self.puzzle, self.puzzle_id
        self.puzzle = self.puzzle_id = None
        self.state = "overworld"
        if not puzzle.solved:
            self.world.set_message("The shrine waits patiently. Come back any time today.", 150)
            return
        exp, item = self.PUZZLE_REWARDS.get(puzzle.kind, (10, None))
        exp += puzzle.tier * 5
        if puzzle.revealed:
            exp, item = exp // 2, None
        lead = self.party.lead
        leveled = lead.add_exp(exp)
        self.save_party()
        if item:
            self.repository.add_item(self.player.player_id, item, 1)
        self.world.set_flag(f"shrine:{shrine_id}:{self.world.today}")
        if puzzle.kind == "starchart":
            self.world.set_flag("secret:starchart")
        reward = f"+{exp} EXP" + (f" and a {item}" if item else "") + ("  LEVEL UP!" if leveled else "")
        self.world.set_message(f"Puzzle solved! {reward}", 240)

    # ================================================================== battles
    def _start_battle(self, enemy, kind="wild", trainer_name=""):
        if self.party.all_fainted:
            self.party.heal_all(0.5)
        self.save_all()
        if kind == "wild":
            self.repository.record_seen(self.player.player_id, enemy.species_id)
        bag = RepositoryBag(self.repository.inventory(self.player.player_id))
        self.battle = BattleScreen(self.orchestrator, self.player.player_id, self.party, enemy, kind, bag, self.rng,
                                   self.llm, trainer_name, self.REGION_MIN_DIFFICULTY.get(self.player.world),
                                   scene=self.player.world)
        self.state = "battle"

    def _wild_encounter(self):
        species_id, level = self.world.encounter_spec, self.world.encounter_level
        self.world.encounter_spec = self.world.encounter_level = None
        if not species_id:
            species_id, level = self.world.encounters.pick(self.world.area_id)
        self._start_battle(monster_factory.create(species_id, level), "wild")

    def _end_battle(self):
        battle = self.battle
        self.battle = None
        outcome = battle.outcome
        pid = self.player.player_id
        if battle.bag.used:
            self.repository.set_inventory(pid, battle.bag.counts)
        coins = battle.battle.rewards["coins"]
        if coins:
            self.repository.add_coins(pid, coins)
        if outcome == "captured":
            self.repository.record_capture(pid, self.party, battle.enemy.species_id)
        if outcome == "defeated":
            self._recover()
            return
        self.save_all()
        self.state = "overworld"
        self.world.resume()
        self.world.refresh_flags()
        messages, done = [], []
        if outcome == "won":
            more, done = self.quests.notify("battle_won")
            messages += more
            if battle.battle.kind == "boss":
                gate = getattr(self, "boss_in_progress", None) or self.boss_gate() or {}
                flag = gate.get("flag", self.BOSS_FLAG)
                self.world.set_flag(flag)
                more, finished = self.quests.notify("flag", flag=flag)
                messages += more
                done += finished
        elif outcome == "captured":
            more, done = self.quests.notify("capture")
            messages += more
        lead = {"won": "Victory! Your team grows stronger.", "captured": "Captured! Press TAB > PARTY to see your team.",
                "fled": "You got away safely."}.get(outcome, "")
        if battle.battle.kind == "boss" and outcome == "won":
            gate = getattr(self, "boss_in_progress", None) or self.boss_gate() or {}
            lead = gate.get("victory", "The boss is defeated!")
            self.boss_in_progress = None
        self._quest_feedback(messages, done, lead)

    def _recover(self):
        """GDD 4.1 / 22: Game Over -> Recovery. Nothing is ever deleted; you wake at the nearest safe spot."""
        self.party.heal_all(rules()["defeat"]["recover_fraction"])
        if self.player.world in ("number_forest", "village_shop", "village_sanctuary", "village_recovery"):
            self.player.world, (self.player.x, self.player.y) = "village_recovery", (14, 10)
        else:
            self.player.x, self.player.y = self.world.world.safe_spot
        self.save_all()
        self._enter_world()
        if self.player.world == "village_recovery":
            self.recovery_text = ("Your team fainted, but Nurse Hana brought everyone to the Mathmon Recovery Center. "
                                  "Every monster is healed and nothing you caught or learned was lost.")
        else:
            self.recovery_text = (f"Your team fainted, but you woke safely at the {self.world.world.name} camp. Every "
                                  "monster is healed and nothing you caught or learned was lost.")
        self.state = "recovery"

    # ================================================================== update
    def _update(self):
        if self.states.update():
            pass
        elif self.state == "battle" and self.battle:
            self.battle.update()
            if self.battle.closed:
                self._end_battle()
        elif self.state == "puzzle" and self.puzzle:
            self.puzzle.update()
        elif self.state == "arena" and self.arena:
            self.arena.update()
        elif self.state == "trials" and self.trials:
            self.trials.update()
        elif self.state == "mbattle" and self.monster_battle:
            self.monster_battle.update()
        elif self.state == "overworld" and self.world:
            event = self.world.update(*self._held_direction())
            self.save_timer += 1
            if self.world.dirty and self.save_timer >= 180:
                self.save_all()
                self.world.dirty, self.save_timer = False, 0
            if event == "encounter":
                self._wild_encounter()
        if self.state != self._last_state and WEB:
            self.persister.sync()
        if self.state != self._last_state:
            boss = self.state == "battle" and self.battle is not None and self.battle.battle.kind == "boss"
            self._play_music(boss)
            self.fade = self.FADE_FRAMES if self._last_state is not None else 0
            self._last_state = self.state
        elif self.fade:
            self.fade -= 1

    def _back_to_world(self, message):
        self._reload_party()
        self.state = "overworld"
        self.world.set_message(message, 220)

    # ================================================================== drawing
    def _draw(self):
        ui.begin_frame()
        if not self.states.covers_base():
            draw = {"menu": self._draw_menu, "confirm_new": self._draw_confirm_new, "name": self._draw_name,
                    "avatar": self._draw_avatar, "starter": self._draw_starter, "settings": self._draw_settings,
                    "recovery": self._draw_recovery}.get(self.state)
            if draw:
                draw()
            elif self.state == "overworld" and self.world:
                self.world.draw(self.canvas, self.frame)
            elif self.state == "worldmap" and self.map_screen:
                self.map_screen.draw(self.canvas, self.frame)
            elif self.state == "puzzle" and self.puzzle:
                self.puzzle.draw(self.canvas, self.frame)
            elif self.state == "arena" and self.arena:
                self.arena.draw(self.canvas, self.frame)
            elif self.state == "trials" and self.trials:
                self.trials.draw(self.canvas, self.frame)
            elif self.state == "mbattle" and self.monster_battle:
                self.monster_battle.draw(self.canvas, self.frame)
            elif self.state == "battle" and self.battle:
                self.battle.draw(self.canvas, self.frame)
        self.states.draw(self.canvas, self.frame)

    def _draw_menu(self):
        self.canvas.fill(PALETTE["ink"])
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
        float_y = 1 if self.frame % 90 < 45 else 0
        text(self.canvas, "MATHMON", (160, 56 + float_y), 48, PALETTE["coral"], center=True)
        text(self.canvas, "MATHMON", (158, 54 + float_y), 48, PALETTE["gold"], center=True)
        text(self.canvas, "TRAIN YOUR MIND. EVOLVE YOUR POWER.", (160, 81), 11, PALETTE["cream"], center=True)
        choices = list(self.MENU_CHOICES)
        disabled = ()
        if self.saved_record:
            choices[1] = f"CONTINUE  ({self.saved_record.name[:8]}, Lv {self.saved_record.level})"
        else:
            disabled = (1,)
        menu(self.canvas, (29, 113, 136, 70), choices, self.menu_selected, 10, self.frame, disabled)
        for i, spec in enumerate(STARTERS.values()):
            pose = ("idle", "idle2", "idle3", "idle2")[(self.frame // 18 + i) % 4]
            draw_creature(self.canvas, spec, (196 + i * 34, 170 + (i % 2) * 6), 34, pose)
        panel(self.canvas, (170, 181, 143, 31), PALETTE["night"], PALETTE["leaf"])
        wrapped(self.canvas, self.menu_hint, (177, 187, 129, 20), 10, PALETTE["white"], 11, 2)
        text(self.canvas, f"{self.llm.label}  •  A SMALL WORLD OF BIG IDEAS", (160, 226), 9, PALETTE["muted"], center=True)

    def _draw_name(self):
        self.canvas.fill(PALETTE["ink"])
        text(self.canvas, "A NEW TRAINER", (160, 52), 25, PALETTE["gold"], center=True)
        panel(self.canvas, (44, 99, 232, 62), PALETTE["night"])
        text(self.canvas, "What is your name, Numera Trainer?", (58, 111), 13, PALETTE["white"])
        caret = "_" if self.frame % 50 < 28 else " "
        text(self.canvas, (self.player_name or "Rookie") + caret, (58, 135), 18,
             PALETTE["cream"] if self.player_name else PALETTE["muted"])
        text(self.canvas, "TYPE A NAME     ENTER: CONTINUE", (160, 184), 11, PALETTE["muted"], center=True)
        text(self.canvas, "ESC: BACK", (160, 215), 10, PALETTE["muted"], center=True)

    def _draw_avatar(self):
        from game import monster_sprites
        self.canvas.fill((37, 71, 77))
        text(self.canvas, "CHOOSE YOUR LOOK", (160, 24), 20, PALETTE["cream"], center=True)
        for i, name in enumerate(Overworld.AVATARS):
            chosen = i == self.avatar_selected
            x = 52 + i * 124
            lift = -4 if chosen else 0
            panel(self.canvas, (x, 52 + lift, 92, 136), PALETTE["night"] if chosen else PALETTE["ink"],
                  PALETTE["gold"] if chosen else PALETTE["leaf"])
            sheet = f"characters/{name}"
            if monster_sprites.available(sheet):
                pose = (1, 0, 2, 0)[self.frame // 10 % 4] if chosen else 0
                monster_sprites.draw(self.canvas, sheet, (x + 46, 160 + lift), 92, pose)
            text(self.canvas, name.title(), (x + 46, 172 + lift), 14, PALETTE["gold"], center=True)
        text(self.canvas, "LEFT/RIGHT: CHOOSE     ENTER: CONTINUE     ESC: BACK", (160, 214), 9, PALETTE["cream"], center=True)

    def _draw_starter(self):
        """GDD 4.2: sprite, element, description, role, maths affinity and basic stats."""
        self.canvas.fill((37, 71, 77))
        text(self.canvas, "CHOOSE YOUR FIRST MONSTER", (160, 14), 16, PALETTE["cream"], center=True)
        keys = tuple(STARTERS)
        for i, sid in enumerate(keys):
            spec = STARTERS[sid]
            chosen = i == self.starter_selected
            x = 6 + i * 78
            lift = -3 if chosen else 0
            panel(self.canvas, (x, 30 + lift, 74, 108), PALETTE["night"] if chosen else PALETTE["ink"],
                  PALETTE["gold"] if chosen else elemental_system.color(spec.element))
            hop = (self.frame % 24 // 12) * 2 if chosen else 0
            pose = ("idle", "idle2", "idle3", "idle2")[self.frame // 16 % 4] if chosen else "idle"
            draw_creature(self.canvas, spec, (x + 37, 96 + lift - hop), 50, pose)
            text(self.canvas, spec.name, (x + 37, 102 + lift), 11, PALETTE["gold"] if chosen else PALETTE["white"], center=True)
            badge = pygame.Rect(x + 17, 112 + lift, 40, 9)
            pygame.draw.rect(self.canvas, elemental_system.color(spec.element), badge)
            text(self.canvas, spec.element.upper(), badge.center, 8, PALETTE["ink"], center=True)
            text(self.canvas, curriculum.label(spec.mastery_topic), (x + 37, 128 + lift), 8, PALETTE["sky"], center=True)
        spec = STARTERS[keys[self.starter_selected]]
        panel(self.canvas, (6, 144, 308, 72), PALETTE["night"])
        stats = spec.stats
        text(self.canvas, f"{spec.name}  -  {spec.role}", (12, 148), 10, PALETTE["gold"])
        text(self.canvas, f"HP {stats['hp']}  ATK {stats['attack']}  DEF {stats['defence']}  SPD {stats['speed']}",
             (308, 148), 9, PALETTE["white"], align="right")
        wrapped(self.canvas, spec.description, (12, 160, 296, 12), 9, PALETTE["white"], 10, 1)
        affinity = ", ".join(curriculum.label(t) for t in spec.topics)
        beats = elemental_system.strong_against(spec.element)
        text(self.canvas, f"Maths affinity: {affinity}    {spec.element} beats {beats}", (12, 172), 9, PALETTE["sky"])
        moves = ", ".join(m.name for m in spec.move_list())
        text(self.canvas, f"Moves: {moves}", (12, 183), 9, PALETTE["cream"])
        wrapped(self.canvas, f"{spec.passive.get('name', '')}: {spec.passive.get('text', '')}", (12, 194, 296, 20), 8,
                PALETTE["muted"], 9, 2)
        text(self.canvas, "LEFT/RIGHT or 1-4: CHOOSE    ENTER: BEGIN    ESC: BACK", (160, 228), 9, PALETTE["cream"], center=True)

    def _draw_confirm_new(self):
        self._draw_menu()
        overlay = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*PALETTE["ink"], 190))
        self.canvas.blit(overlay, (0, 0))
        ui.begin_frame()
        panel(self.canvas, (40, 78, 240, 86), PALETTE["night"], PALETTE["coral"])
        text(self.canvas, "START OVER?", (160, 92), 18, PALETTE["coral"], center=True)
        record = self.saved_record
        wrapped(self.canvas, f"This replaces {record.name}'s Lv {record.level} journey and learning journal.",
                (54, 106, 212, 30), 11, PALETTE["white"], 12, 2)
        text(self.canvas, "Y / ENTER: NEW GAME        N / ESC: KEEP SAVE", (160, 148), 10, PALETTE["gold"], center=True)

    def _draw_settings(self):
        self.canvas.fill(PALETTE["ink"])
        text(self.canvas, "SETTINGS", (160, 53), 24, PALETTE["gold"], center=True)
        options = ["SCANLINE EFFECT: " + ("ON" if self.scanlines else "OFF"),
                   "SOUND: " + ("ON" if self.sound else "OFF"), "BACK TO TITLE"]
        menu(self.canvas, (77, 100, 166, 60), options, self.settings_selected, 12, self.frame)
        text(self.canvas, f"AI MODE: {self.llm.label}  (set MATHMON_AI_MODE / ANTHROPIC_API_KEY in .env)",
             (160, 166), 8, PALETTE["sky"], center=True)
        text(self.canvas, "F11 or ALT+ENTER toggles fullscreen", (160, 182), 10, PALETTE["muted"], center=True)
        text(self.canvas, "UP/DOWN: CHOOSE     ENTER: CHANGE     ESC: BACK", (160, 200), 10, PALETTE["muted"], center=True)

    def _draw_recovery(self):
        self.canvas.fill(PALETTE["ink"])
        text(self.canvas, "RECOVERY", (160, 60), 22, PALETTE["mint"], center=True)
        panel(self.canvas, (30, 90, 260, 80), PALETTE["night"], PALETTE["mint"])
        wrapped(self.canvas, self.recovery_text, (40, 100, 240, 60), 11, PALETTE["white"], 12, 5)
        text(self.canvas, "ENTER: CONTINUE", (160, 190), 10, PALETTE["cream"], center=True)

    # ================================================================== window
    @staticmethod
    def _browser_size():
        try:
            import platform
            win = platform.window
            css_w, css_h = int(win.innerWidth), int(win.innerHeight)
            ratio = min(2.0, float(win.devicePixelRatio or 1))
        except Exception:
            return None
        if css_w <= 0 or css_h <= 0:
            return None
        ratio = min(ratio, 1920 / max(css_w, css_h))
        return max(1, int(css_w * ratio)), max(1, int(css_h * ratio))

    def _fit_browser_window(self):
        size = self._browser_size()
        if size and size != self.window.get_size():
            self.window = pygame.display.set_mode(size)

    def _held_direction(self):
        if self.states.overlay is not None:
            return 0, 0
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        touch = self.touch.held_direction() if hasattr(self, "touch") else (0, 0)
        return max(-1, min(1, int(dx) + touch[0])), max(-1, min(1, int(dy) + touch[1]))

    def _toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode((VIRTUAL_WIDTH * WINDOW_SCALE, VIRTUAL_HEIGHT * WINDOW_SCALE),
                                                  pygame.RESIZABLE)

    def _present(self):
        win_w, win_h = self.window.get_size()
        scale = min(win_w / VIRTUAL_WIDTH, win_h / VIRTUAL_HEIGHT)
        if scale >= 1:
            scale = int(scale)
        scale = max(scale, 0.25)
        size = (int(VIRTUAL_WIDTH * scale), int(VIRTUAL_HEIGHT * scale))
        offset = ((win_w - size[0]) // 2, (win_h - size[1]) // 2)
        if self.touch.enabled and win_h > win_w:
            offset = (offset[0], min(offset[1], self.touch.top_reserved(win_w, win_h)))
        ui.set_view(scale, offset)
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
        self.touch.draw(self.window, self.state)
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
        try:
            self.save_all()
        except Exception:
            pass   # never lose the window close over a save hiccup
        self.llm.close()
        if WEB:
            self.persister.sync()
            return
        pygame.quit()
        sys.exit(0)

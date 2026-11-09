"""The one main loop (GDD 22) and the top-level flow between states.

Events, updates, rendering and frame timing all happen in ``run_async``. Which screen receives
them is decided by the StateManager: a named full-screen state (menu, overworld, battle, ...)
plus a stack of overlay screens (trainer menu, party, sanctuary, bag, shop, quests, profile,
evolution, puzzle challenges, pause).
"""
import asyncio
from pathlib import Path
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
from game.touch_controls import TouchControls, game_scale
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
from world.story_manager import StoryManager, chapters as story_chapters

SEALS = ("challenge:seal_add", "challenge:seal_mul", "challenge:seal_frac")


class GameManager:
    MAPS = ("number_forest", "crystal_realm", "village_shop", "village_sanctuary", "village_lab",
            "algebra_cavern", "geometry_kingdom", "chronos_dimension", "village_recovery")
    BOSS_FLAG = "boss:numerex"
    MENU_CHOICES = ("NEW GAME", "CONTINUE", "SETTINGS", "EXIT")
    FADE_FRAMES = 14
    REGION_MIN_DIFFICULTY = {"crystal_realm": "intermediate", "geometry_kingdom": "intermediate",
                             "chronos_dimension": "intermediate"}

    def __init__(self, database_path=None):
        if WEB:
            # The browser runs audio on the same single thread as the game: a big buffer (~90 ms)
            # keeps the music smooth when a frame takes a little longer (no crackles).
            pygame.mixer.pre_init(44100, -16, 2, audio.WEB_BUFFER)
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
        self.orchestrator.level_provider = self.party_level      # harder maths as the team levels up
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
        self.story = None
        self.story_queue = []            # scenes and chapter cards waiting to be shown, in order
        self.story_busy = False
        self.opening_flags = set()       # the opening plays before the save exists
        self.menu_selected = 0
        self.starter_selected = 0
        self.avatar_selected = 0
        self.settings_selected = 0
        self.scanlines = False
        self.sound = True
        self.settings_screen = None
        from game import settings as player_settings
        self.settings_folder = Path(database_path).parent if database_path else None   # next to the save
        player_settings.apply(self, player_settings.load(self.settings_folder))   # sound, volumes, scanlines
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
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.state == "worldmap" and self.map_screen:
            self.map_screen.handle_click(event.pos)
            if self.map_screen.closed:
                self._finish_map()
            return
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.state == "overworld" and self.world
                and not self.world.dialogue):
            from game.quest_tracker import TAB
            if TAB.collidepoint(ui.to_virtual(event.pos)):
                self.world.tracker.toggle()
                return
        if event.type == pygame.MOUSEBUTTONDOWN and self.state == "settings":
            screen = self._settings()
            screen.handle_event(event)
            if screen.closed:
                self.settings_screen = None
                self.state = "menu"
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
                self.trials = None
                self._back_to_world("Trial monsters roam the world - find one to challenge it!")
        elif self.state == "mbattle" and self.monster_battle:
            self.monster_battle.handle_key(event.key, event.unicode)
            if self.monster_battle.closed:
                battle, self.monster_battle = self.monster_battle, None
                self._reload_party()
                self._trial_over(battle)
        elif self.state == "puzzle" and self.puzzle:
            self.puzzle.handle_key(event.key, event.unicode)
            if self.puzzle.closed:
                self._close_puzzle()
        elif self.state == "worldmap" and self.map_screen:
            self.map_screen.handle_key(event.key)
            if self.map_screen.closed:
                self._finish_map()

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
                # A new save PROFILE: older journeys are kept (3:07 report).
                from states.profile_select_state import MAX_PROFILES
                if len(self.repository.list_profiles()) >= MAX_PROFILES:
                    self.menu_hint = f"{MAX_PROFILES} profiles already. Open CONTINUE and delete one (X)."
                else:
                    self.state, self.player_name = "name", ""
            elif choice == "CONTINUE":
                if self.saved_record:
                    self.open_profiles()
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
            if "scene:opening" not in self.opening_flags:
                preview = StoryManager(self.opening_flags.__contains__, self.opening_flags.add)
                self._push_scene(preview, preview.scene("opening"))
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

    def _settings(self):
        from states.settings_state import SettingsScreen
        if self.settings_screen is None or self.settings_screen.closed:
            self.settings_screen = SettingsScreen(self)
        return self.settings_screen

    def _settings_key(self, event):
        screen = self._settings()
        screen.handle_key(event.key, getattr(event, "unicode", ""))
        if screen.closed:
            self.settings_screen = None
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
        for flag in self.opening_flags | {"game:started"}:
            self.repository.set_world_flag(player_id, flag)
        self.opening_flags = set()
        self.repository.touch_player(player_id)
        record = self.repository.load_player(player_id)     # this new profile (older ones are kept)
        self._load(record)
        self.quests.start_auto_quests()
        self._enter_world()
        self.world.set_message(f"{STARTERS[species_id].name} joins your journey!", 200)

    def _finish_map(self):
        """The world map closed: fast-travel to a spawn point, or open a quest it pointed at."""
        screen, self.map_screen = self.map_screen, None
        self.state = "overworld"
        if screen.travel_to:
            cell, name = screen.travel_to
            self.world.teleport(cell)
            self.save_all()
            self.world.set_message(f"You travel to {name}.", 150)
        if screen.open_quest:
            self.show_quest(screen.open_quest)

    def show_quest(self, quest_id):
        """Open the Quest Log on one quest (from the world map's quest pins and locked places)."""
        screen = self.open_screen("quests")
        if screen is not None and quest_id in getattr(screen, "entries", []):
            screen.selected = screen.entries.index(quest_id)
        return screen

    def open_profiles(self):
        """CONTINUE: choose which save profile to play (or start / delete one)."""
        from states.profile_select_state import ProfileScreen
        self.states.push(ProfileScreen(self), self._profile_chosen)

    def _profile_chosen(self, screen):
        self.saved_record = self.repository.load_player()
        choice = screen.result
        if not choice:
            return
        action, player_id = choice
        if action == "new":
            self.state, self.player_name = "name", ""
        else:
            self._continue_game(player_id)

    def _continue_game(self, player_id=None):
        record = self.repository.load_player(player_id)
        if not record:
            self.player_name, self.state = "", "name"
            return
        self.repository.touch_player(record.player_id)      # it is now the most recently played profile
        self._load(record)
        self.quests.start_auto_quests()
        self.quests.notify("refresh")       # re-check every step (a save stuck before a rule fix moves on)
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
        self.story = StoryManager(self._has_flag, self._set_flag)
        self.story_queue, self.story_busy = [], False
        self._migrate_story()

    # ================================================================== story
    def _flags(self):
        return self.world.flags if self.world else self.repository.world_flags(self.player.player_id)

    def _has_flag(self, flag):
        return flag in self._flags()

    def _set_flag(self, flag):
        if self.world:
            self.world.set_flag(flag)
        else:
            self.repository.set_world_flag(self.player.player_id, flag)

    def _migrate_story(self):
        """Saves from before the story existed start in the right chapter without replaying the prologue."""
        if self._has_flag("game:started"):
            return
        story = self.story
        story.set_flag("game:started")
        flags = self._flags()
        if "met:rowan" in flags or any(f.startswith("boss:") for f in flags):
            for flag in ("chapter:prologue_done", "scene:opening", "scene:prologue_village", "numlink"):
                story.set_flag(flag)
            current = story.chapter()["id"]
            for chapter in story_chapters():
                if chapter["id"] != current and self._has_flag(chapter["starts"]):
                    story.mark_card_shown(chapter["id"])

    def story_event(self, event, then=None, **info):
        """Report a game event to the story; queue the matching scene (if any). Returns True if one was queued."""
        if not self.story:
            return False
        scene_id = self.story.scene_for(event, **info)
        if scene_id:
            self.play_scene(scene_id, then)
            return True
        if then:
            then()
        return False

    def play_scene(self, scene_id, then=None, npc=None):
        self.story_queue.append(("scene", scene_id, then, npc))
        self._run_story_queue()

    def _queue_chapter_card(self):
        chapter = self.story.pending_chapter_card() if self.story else None
        if chapter and not any(item[0] == "card" and item[1]["id"] == chapter["id"] for item in self.story_queue):
            self.story_queue.append(("card", chapter, None, None))

    def _run_story_queue(self):
        if self.story_busy or not self.story_queue:
            return
        kind, payload, then, npc = self.story_queue.pop(0)
        self.story_busy = True
        if kind == "card":
            from states.codex_state import ChapterCard
            self.story.mark_card_shown(payload["id"])
            self.states.push(ChapterCard(self, payload), lambda screen: self._story_closed(None, then))
            return
        scene = self.story.scene(payload)
        self._push_scene(self.story, scene, then, npc)

    def _push_scene(self, story, scene, then=None, npc=None):
        from states.scene_state import SceneScreen
        avatar = self.world.avatar.sheet if self.world else f"characters/{Overworld.AVATARS[self.avatar_selected]}"
        screen = SceneScreen(self, story, scene, avatar)
        screen.npc_id = npc
        if story is self.story:
            self.states.push(screen, lambda s: self._story_closed(s, then))
        else:
            self.states.push(screen)       # the opening: no save yet, nothing else to do

    def _story_closed(self, screen, then):
        self.story_busy = False
        if screen is not None:
            result = screen.result or {}
            if self.world and getattr(self.world, "talking_to", None):
                self.world.talking_to.end_talk()
                self.world.talking_to = None
            for quest_id in result.get("quests", []):
                self._quest_feedback(self.quests.start(quest_id), [])
            for action in result.get("actions", []):
                self._story_action(action, screen)
            new_flags = result.get("flags", [])
            if new_flags:
                messages, done = self.quests.notify("flag", flag=new_flags[-1])
                self._quest_feedback(messages, done)
                for flag in new_flags:
                    scene_id = self.story.scene_for("flag", flag=flag)
                    if scene_id:
                        self.story_queue.append(("scene", scene_id, None, None))
                if self.world:
                    self.world.refresh_flags()
                self._refresh_boss_gate()
            self.save_all()
        self._queue_chapter_card()
        if then:
            then()
        self._run_story_queue()

    def _story_action(self, action, screen):
        if action == "battle":
            npc_id = getattr(screen, "npc_id", None)
            spec = next((n.spec for n in self.world.npcs if n.id == npc_id), {}) if self.world else {}
            duel = spec.get("battle_with") or {"species": "DIVOWL", "level": 2}
            enemy = monster_factory.create(duel["species"], duel["level"])
            self._start_battle(enemy, "trainer", spec.get("name", ""))
        elif action.startswith("challenge:"):
            self.open_challenge(action.split(":", 1)[1])
        elif action.startswith("ending:"):
            scene_id = self.story.scene_for("ending", id=action.split(":", 1)[1])
            if scene_id:
                self.story_queue.append(("scene", scene_id, None, None))

    def _play_music(self, boss=False):
        if boss:
            audio.music("boss")
        elif self.state == "battle" and self.battle is not None and self.battle.battle.kind == "wild":
            audio.music("wild_battle")
        elif self.state == "arena":
            audio.music("arena")
        elif self.state in ("battle", "mbattle"):
            audio.music("battle")
        elif self.state in ("menu", "name", "avatar", "starter", "settings", "confirm_new"):
            audio.music("menu")
        elif self.player:
            audio.music(self.player.world)      # each world has its own theme

    def _enter_world(self):
        # Events the new map fires while it loads (e.g. "visit" for the area you arrive in) are held
        # until the map is ready - otherwise the reset below would throw their story scenes away.
        self._world_loading, self._held_world_events = True, []
        self.world = Overworld(self.player, self.rng, self.repository, self.player.world, self.party, self.quests,
                               self.on_world_event)
        self._world_loading = False
        self._refresh_boss_gate()
        self.save_timer = 0
        self.states.clear()
        self.story_queue, self.story_busy = [], False
        self.state = "overworld"
        self._play_music()
        self.world.scene_for = self.story.scene_for if self.story else None
        self._queue_chapter_card()
        self.story_event("enter_world")
        held, self._held_world_events = self._held_world_events, []
        for kind, data in held:
            self.on_world_event(kind, **data)
        self._run_story_queue()

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

    def open_catalog(self, tab="MATHDEX"):
        """The Catalog: MathDex and Trials (bosses) side by side, switched with Q / E."""
        from states.catalog_state import CatalogScreen
        screen = CatalogScreen(self, tab)
        self.states.push(screen, self._screen_closed)
        return screen

    def open_screen(self, name):
        if name == "catalog":
            return self.open_catalog()
        from states.codex_state import CodexScreen
        screens = {"codex": CodexScreen, "party": PartyScreen, "bag": InventoryScreen, "quests": QuestScreen, "mathdex": DexScreen,
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
        if screen.result:
            self.story_event("challenge", id=screen.challenge_id)

    # ================================================================== quests & world events
    def on_world_event(self, kind, **data):
        if getattr(self, "_world_loading", False):
            self._held_world_events.append((kind, data))
            return
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
        if kind == "visit":
            self.story_event("visit", area=data.get("area"))

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
            self.open_catalog("MATHDEX")
            return
        if event.key == pygame.K_j and self.world:
            self.world.tracker.toggle()          # quest tracker in the top-right corner
            return
        if event.key == pygame.K_t:
            self.save_all()
            self.open_catalog("TRIALS")          # the Trials catalogue is a tab of the Catalog now
            return
        if event.key == pygame.K_n and not world.world.interior:
            self.map_screen = WorldMapScreen(world)
            self.state = "worldmap"
            return
        self._world_action(world.handle_key(event.key))

    def _world_action(self, action):
        if not action:
            return
        if isinstance(action, tuple) and action[0] == "scene":
            self.play_scene(action[1], npc=action[2])
            return
        if isinstance(action, tuple) and action[0] == "record":
            self.read_record(action[1])
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

    def read_record(self, record_id):
        """Historical records: read the text, add it to the Codex, then let the story react."""
        def after():
            messages, done = self.quests.notify("flag", flag=f"record:{record_id}")
            self._quest_feedback(messages, done)
            self.story_event("record", id=record_id)
        self.play_scene(f"record:{record_id}", after)

    def _start_boss(self):
        gate = self.boss_gate() or {}
        if gate.get("trial"):
            # This gate's boss is a Monster Trials creature (the stone arch: ARITHMORD, the Arithmetic Beast).
            self.boss_in_progress = gate
            self.story_event("boss_before", then=lambda: self._start_trial(gate["trial"], gate.get("trial_rank"), gate),
                             flag=gate.get("flag", self.BOSS_FLAG))
            return
        cfg = encounters()["boss"]
        enemy = monster_factory.create(gate.get("boss", cfg["species"]), gate.get("level", cfg["level"]))
        self.boss_in_progress = gate
        self.story_event("boss_before", then=lambda: self._start_battle(enemy, "boss"),
                         flag=gate.get("flag", self.BOSS_FLAG))

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
                      "target": (20, "Numeris Core"), "magic": (25, "Greater Potion"), "starchart": (30, None)}

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

    def _start_trial(self, monster_id, rank=None, gate=None):
        """Battle a Trial monster: a roaming one (next mastery tier you can reach) or a gate boss."""
        from battle_engine.monster_data import load_all
        from battle_engine.progression import available_ranks, new_record
        defn = load_all().get(monster_id)
        if defn is None:
            return
        record = self.repository.monster_records(self.player.player_id).get(monster_id) or new_record(monster_id)
        rank = rank or available_ranks(defn, record)[-1]
        self.trial_gate = gate
        self.world.set_flag(f"trial_seen:{monster_id}")      # the Trials catalogue now shows it
        self.save_all()
        self.monster_battle = MonsterBattleScreen(self.repository, self.player, monster_id, rank, self.rng,
                                                  self._team())
        self.state = "mbattle"

    TRAINER_XP = {"wild": 12, "trainer": 20, "boss": 50}     # per win; a catch counts like a wild win

    def _grant_trainer_xp(self, kind, outcome):
        """Every battle you win (or catch) earns Trainer XP - Trainer levels unlock battle SKILLS."""
        if outcome not in ("won", "captured"):
            return ""
        from battle_engine.progression import ProgressStore
        from battle_engine.skills import newly_unlocked
        store = ProgressStore(self.repository, self.player.player_id)
        trainer = store.trainer()
        before = trainer.level
        gained = trainer.add_xp(self.TRAINER_XP.get(kind, 12))
        store.save_trainer(trainer)
        if not gained:
            return ""
        skills = newly_unlocked(before, trainer.level)
        extra = f" New skill: {skills[0].name}!" if skills else ""
        return f"TRAINER Lv {trainer.level}!{extra}"

    def _trial_over(self, battle):
        """After a Trial battle: gate bosses finish their story; a first win unlocks the Professor's tale."""
        won = battle.engine.outcome == "won"
        name, monster_id = battle.engine.name, battle.engine.defn.id
        gate, self.trial_gate = getattr(self, "trial_gate", None), None
        if gate:
            self.state = "overworld"
            self.world.resume()
            if won:
                self._boss_victory(gate)
            else:
                self.boss_in_progress = None
                self.world.set_message(f"{name} drives you back! Heal up and face it again.", 220)
        else:
            self._back_to_world(f"You defeated {name}! It will be back, stronger, when you return here."
                                if won else f"{name} retreats into the wild. Find it again to retry!")
        if won and not gate:
            messages, done = self.quests.notify("trial_won", id=monster_id)   # counts for "win N battles"
            self._quest_feedback(messages, done)
        if won and not self.world.has_flag(f"trial_story:{monster_id}"):
            self.story_event("trial_won", id=monster_id)        # the Professor tells its story

    def _boss_victory(self, gate):
        flag = gate.get("flag", self.BOSS_FLAG)
        self.world.set_flag(flag)
        messages, done = self.quests.notify("battle_won")
        more, finished = self.quests.notify("flag", flag=flag)
        self.boss_in_progress = None
        self._refresh_boss_gate()
        self.save_all()
        self._quest_feedback(messages + more, done + finished, gate.get("victory", "The boss is defeated!"))
        self.story_event("boss_after", flag=flag)

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
        new_species = battle.enemy.species_id if battle.battle.kind == "wild" and self.story and \
            not self._has_flag(f"discovered:{battle.enemy.species_id}") else None
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
            more, done = self.quests.notify("capture", species=battle.enemy.species_id)
            messages += more
        lead = {"won": "Victory! Your team grows stronger.", "captured": "Captured! Press TAB > PARTY to see your team.",
                "fled": "You got away safely."}.get(outcome, "")
        trainer_note = self._grant_trainer_xp(battle.battle.kind, outcome)
        if trainer_note:
            lead = f"{lead} {trainer_note}".strip()
        if battle.battle.kind == "boss" and outcome == "won":
            gate = getattr(self, "boss_in_progress", None) or self.boss_gate() or {}
            lead = gate.get("victory", "The boss is defeated!")
            self.boss_in_progress = None
            self._quest_feedback(messages, done, lead)
            self.story_event("boss_after", flag=gate.get("flag", self.BOSS_FLAG))
            return
        self._quest_feedback(messages, done, lead)
        if new_species:
            self.play_scene(f"discover:{new_species}")

    def _recover(self):
        """GDD 4.1 / 22: Game Over -> Recovery. Nothing is ever deleted; you wake at the nearest safe spot."""
        self.party.heal_all(rules()["defeat"]["recover_fraction"])
        if self.player.world in ("number_forest", "village_shop", "village_sanctuary", "village_recovery", "village_lab"):
            self.player.world, (self.player.x, self.player.y) = "village_recovery", (7, 5)
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
            elif event == "trial":
                if self.states.stack or self.story_busy or self.story_queue:
                    # A story scene comes first; the Trial monster waits where it is.
                    self.world.trial_roamers.append(self.world.encounter_trial_roamer)
                    self.world.encounter_grace = 60
                else:
                    self._start_trial(self.world.encounter_trial)
        if self.state != self._last_state and WEB:
            self.persister.sync()
        if self.state != self._last_state:
            boss = (self.state == "battle" and self.battle is not None and self.battle.battle.kind == "boss") or                 (self.state == "mbattle" and getattr(self, "trial_gate", None) is not None)
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
            choices[1] = f"CONTINUE  ({self.saved_record.name[:8]}...)"
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
        self._settings().draw(self.canvas, self.frame)

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
        scale = game_scale((win_w, win_h), whole_steps=not self.touch.enabled)
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

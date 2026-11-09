"""The items from 'Mathmon bug report.pdf':
1 visual hints, 2 music and sound effects, 3 choosing a companion in the MathDex, 4 map crossings,
5 a Mathmon Recovery Center that heals by solving maths, 6 a Mathmart with the requested items."""
from tests.story_helpers import finish_story
import os
import random
import tempfile
import unittest
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from ai.schemas import reveals
from config import ROOT
from game.visual_hint import draw_visual, hint_visual
from game.world_map import load_map
from mathematics import curriculum
from mathematics.question_generator import TemplateQuestionGenerator
from monsters.monster_factory import create

pygame.init()
E = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, unicode="", mod=0)


class GameCase(unittest.TestCase):
    def setUp(self):
        from game.game_manager import GameManager
        self.folder = tempfile.TemporaryDirectory()
        self.game = GameManager(database_path=self.folder.name + "/bugs.sqlite3")
        self.game._create_new_player()
        finish_story(self.game)

    def tearDown(self):
        self.game.llm.close()
        self.folder.cleanup()


class VisualHintTests(unittest.TestCase):
    def test_every_question_type_has_an_animated_picture(self):
        generator = TemplateQuestionGenerator(random.Random(4))
        surface = pygame.Surface((160, 90))
        for topic in curriculum.MASTERY_TOPICS:
            for difficulty in curriculum.DIFFICULTIES:
                for _ in range(25):
                    question = generator.generate(topic, difficulty)
                    spec = hint_visual(question)
                    self.assertIsNotNone(spec, question.prompt)
                    for age in (0, 30, 90, 400):
                        draw_visual(surface, spec, (2, 2, 150, 80), age)

    def test_pictures_only_use_numbers_from_the_question(self):
        """A picture is built from the question's own numbers, never from a computed result."""
        import re
        generator = TemplateQuestionGenerator(random.Random(8))
        for topic in curriculum.MASTERY_TOPICS:
            for difficulty in curriculum.DIFFICULTIES:
                for _ in range(25):
                    question = generator.generate(topic, difficulty)
                    spec = hint_visual(question)
                    if spec[0] in ("steps", "decimal_cols"):
                        continue      # these restate the question's numbers as text (checked by eye)
                    given = {abs(int(n)) for n in re.findall(r"\d+", question.prompt)}
                    used = set()
                    for part in spec[1:]:
                        for value in (part if isinstance(part, tuple) else (part,)):
                            if isinstance(value, int):
                                used.add(abs(value))
                    self.assertTrue(used - {0, 1} <= given, (question.prompt, spec))   # 1 = the "x" in "x + 4"

    def test_the_question_panel_shows_the_picture_when_a_hint_is_asked_for(self):
        from game.question_panel import QuestionPanel
        from ai.orchestrator import AgentOrchestrator
        from database.database import Database
        from database.player_repository import PlayerRepository
        with tempfile.TemporaryDirectory() as folder:
            repo = PlayerRepository(Database(folder + "/h.sqlite3"))
            pid = repo.create_player("Ada", "FRACTELLA")
            question = TemplateQuestionGenerator(random.Random(1)).generate("fractions", "intermediate")
            panel = QuestionPanel(AgentOrchestrator(repo), pid, question)
            self.assertIsNone(panel.visual)
            panel.request_hint()
            self.assertEqual(panel.visual[0], "bars")
            surface = pygame.Surface((320, 240))
            for frame in range(5):
                panel.update()
                panel.draw(surface, (7, 120, 306, 94), frame)


class AudioTests(unittest.TestCase):
    def test_music_and_effects_exist_and_never_crash(self):
        from game import audio
        for name in ("menu", "forest", "cavern", "kingdom", "chronos", "battle", "boss"):
            self.assertTrue((ROOT / "assets" / "sounds" / f"{name}.wav").exists(), name)
        for name in audio.BLIPS:
            self.assertTrue((ROOT / "assets" / "sounds" / f"{name}.wav").exists(), name)
            audio.play(name)
        for track in ("menu", "number_forest", "algebra_cavern", "boss", "no_such_track"):
            audio.music(track)
        audio.set_enabled(False)
        audio.play("hit")
        audio.set_enabled(True)


class CompanionTests(GameCase):
    def test_a_caught_monster_can_be_chosen_as_companion_from_the_mathdex(self):
        game = self.game
        game.party.add(create("VOLTIX", 5))
        for _ in range(3):
            game.party.add(create("PYRON", 3))           # the last one goes to the Sanctuary
        stored = create("DIVOWL", 4)
        game.party.storage.append(stored)
        game.save_party()
        dex = game.open_screen("mathdex")
        dex.activate(dex.ids.index("VOLTIX"))
        self.assertEqual(game.party.lead.species_id, "VOLTIX")
        self.assertIn("companion", dex.notice)
        dex.activate(dex.ids.index("DIVOWL"))            # stored: comes into the party and leads
        self.assertEqual(game.party.lead.species_id, "DIVOWL")
        self.assertEqual(len(game.party.party), 3)
        self.assertEqual(game.repository.load_party(game.player.player_id).party[0].species_id, "DIVOWL")
        self.assertEqual(game.world.companion_spec().name, "DIVOWL")
        dex.activate(dex.ids.index("GRAPHION"))
        self.assertIn("Catch one first", dex.notice)


class MapCrossingTests(GameCase):
    def test_people_never_block_the_path(self):
        world = self.game.world
        bram_cell = (90, 33)
        world.teleport((88, 33))
        bram = next(n for n in world.npcs if n.id == "bram")
        bram.x, bram.y = world.world.cell_to_feet(bram_cell)
        bram.state, bram.wait, bram.path = "working", 10 ** 6, []
        start = world.avatar.x
        for _ in range(60):
            world.update(1, 0)
        self.assertGreater(world.avatar.x, start + 40)          # walked straight past Bram

    def test_bumping_the_broken_bridge_says_how_to_fix_it(self):
        world = self.game.world
        world.teleport((91, 33))
        world.message_frames = 0
        for _ in range(40):
            world.update(1, 0)
        self.assertIn("Bram", world.message)

    def test_every_map_is_fully_connected(self):
        for map_id in ("number_forest", "village_shop", "village_sanctuary", "village_recovery", "crystal_realm",
                       "algebra_cavern", "geometry_kingdom", "chronos_dimension"):
            world = load_map(map_id)
            world.apply_flags({"bridge:repaired"})
            start = world.nearest_walkable(world.spawn)
            seen, queue = {start}, deque([start])
            while queue:
                x, y = queue.popleft()
                for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if nxt not in seen and world.is_walkable(nxt):
                        seen.add(nxt)
                        queue.append(nxt)
            for entry in world.data.get("interactables", []):
                x, y = entry["pos"]
                self.assertTrue(any(c in seen for c in ((x, y + 1), (x, y - 1), (x + 1, y), (x - 1, y))),
                                (map_id, entry["id"]))


class RecoveryCenterTests(GameCase):
    def enter_center(self):
        game = self.game
        game._travel_to_map("village_recovery", (7, 7))
        world = game.world
        world.avatar.x, world.avatar.y = world.world.cell_to_feet((7, 4))
        world.avatar.facing = (0, -1)
        world.update()
        self.assertEqual(world.target_id(), "nurse_desk")
        game._overworld_key(E)
        return game.states.overlay

    def test_the_village_has_a_recovery_center_and_healing_needs_maths(self):
        forest = load_map("number_forest")
        door = next(e for e in forest.data["interactables"] if e["id"] == "door_recovery")
        self.assertEqual(door["destination"], "village_recovery")
        sanctuary = load_map("village_sanctuary")
        self.assertFalse([e for e in sanctuary.data["interactables"] if e["kind"] == "spring"])

    def test_one_mathmon_goes_in_the_capsule_and_right_answers_heal_it(self):
        game = self.game
        lead = game.party.lead
        lead.hp = 0
        game.party.add(create("GEOMAX", 5))
        geomax = game.party.party[1]
        geomax.hp = 10
        game.save_party()
        clinic = self.enter_center()
        self.assertEqual(type(clinic).__name__, "ClinicScreen")
        self.assertEqual(clinic.state, "choose")             # the player picks who goes in the capsule
        clinic.handle_key(pygame.K_RETURN)                    # the fainted lead is pre-selected
        self.assertIs(clinic.patient, lead)
        stages = []
        for _ in range(3):
            self.assertEqual(clinic.state, "question")
            clinic.answer(clinic.panel.question.answer)
            clinic.handle_key(pygame.K_RETURN)
            stages.append(clinic.stage)
            if clinic.state != "done":
                clinic.handle_key(pygame.K_RETURN)
        self.assertEqual(clinic.state, "done")
        self.assertEqual(stages[-1], 8)
        self.assertEqual(lead.hp, lead.max_hp)
        self.assertEqual(geomax.hp, 10)                       # only the patient is healed
        self.assertEqual(game.repository.load_party(game.player.player_id).party[0].hp, lead.max_hp)
        surface = pygame.Surface((320, 240))
        clinic.draw(surface, 1)
        clinic.handle_key(pygame.K_RETURN)                    # discharge -> choose the next one
        self.assertEqual(clinic.state, "choose")
        self.assertEqual(clinic.selected, 1)
        clinic.draw(surface, 2)
        clinic.handle_key(pygame.K_RETURN)
        self.assertIs(clinic.patient, geomax)
        self.assertGreaterEqual(game.repository.history_summary(game.player.player_id)["attempted"], 3)

    def test_healthy_mathmon_cannot_go_in_the_capsule(self):
        game = self.game
        game.party.add(create("GEOMAX", 5))
        game.party.party[1].hp = 3
        clinic = self.enter_center()
        clinic.selected = 0                                   # the lead is healthy
        clinic.handle_key(pygame.K_RETURN)
        self.assertEqual(clinic.state, "choose")
        self.assertIn("already healthy", clinic.message)

    def test_wrong_answers_still_help_a_little_and_never_punish(self):
        game = self.game
        lead = game.party.lead
        lead.hp = 1
        clinic = self.enter_center()
        clinic.handle_key(pygame.K_RETURN)
        clinic.answer("99999")
        clinic.answer("99998")
        clinic.handle_key(pygame.K_RETURN)
        self.assertGreater(lead.hp, 1)
        self.assertLess(lead.hp, lead.max_hp)
        self.assertEqual(clinic.state, "result")

    def test_a_healthy_team_needs_no_check_up(self):
        clinic = self.enter_center()
        self.assertEqual(clinic.state, "all_done")

    def test_world_camps_have_recovery_stations(self):
        for map_id in ("algebra_cavern", "geometry_kingdom", "chronos_dimension"):
            kinds = [e["kind"] for e in load_map(map_id).data["interactables"]]
            self.assertIn("clinic", kinds, map_id)


class MathmartTests(GameCase):
    def test_the_mathmart_uses_its_art_and_sells_everything_on_the_list(self):
        mart = load_map("village_shop")
        self.assertEqual(mart.name, "Mathmart")
        self.assertEqual(mart.background, "village_shop_interior.png")
        game = self.game
        shop = game.open_screen("shop")
        names = [name for name, _ in shop.items()]
        self.assertEqual(names, ["Math Potion", "Energy Potion", "Full Restore", "Basic Mathball", "Advanced Mathball",
                                 "Attack Boost", "Defence Boost", "Revive Crystal", "Knowledge Tome", "EXP Star"])
        coins = game.repository.coins(game.player.player_id)
        shop.activate(names.index("EXP Star"))
        self.assertEqual(game.repository.coins(game.player.player_id), coins - 300)

    def test_exp_star_and_knowledge_tome_from_the_bag(self):
        game = self.game
        pid = game.player.player_id
        game.repository.add_item(pid, "EXP Star", 1)
        game.repository.add_item(pid, "Knowledge Tome", 1)
        bag = game.open_screen("bag")
        lead = game.party.lead
        bag.activate(bag.items().index("EXP Star"))
        bag.activate(0)
        self.assertEqual(lead.level, 2)
        bag.activate(bag.items().index("Knowledge Tome"))
        bag.activate(0)
        self.assertEqual(lead.exp, 40)                         # no Proficient topics yet: the base 40 EXP
        self.assertNotIn("Knowledge Tome", game.repository.inventory(pid))


if __name__ == "__main__":
    unittest.main()


class CaptureMenuTests(GameCase):
    """Bug report: players did not know they could catch a wild MathMon (the Mathballs hid in the bag)."""

    def battle_with(self, hp_fraction, kind="wild", species="VOLTIX"):
        game = self.game
        enemy = create(species, 2)
        enemy.hp = max(1, int(enemy.max_hp * hp_fraction))
        game._start_battle(enemy, kind)
        battle = game.battle
        for _ in range(50):
            if battle.state == "menu":
                break
            battle.handle_key(pygame.K_RETURN)
        self.assertEqual(battle.state, "menu")
        return battle

    def test_capture_appears_in_the_menu_when_the_wild_mathmon_is_weak(self):
        battle = self.battle_with(1.0)
        self.assertNotIn("CAPTURE", battle.actions())
        battle.enemy.hp = int(battle.enemy.max_hp * 0.3)
        battle._after_events()
        self.assertIn("CAPTURE", battle.actions())
        self.assertIn("CAPTURE", battle.message)             # it tells the player
        self.assertEqual(battle.actions()[battle.selected], "CAPTURE")
        battle.draw(pygame.Surface((320, 240)), 1)
        battle.handle_key(pygame.K_RETURN)
        self.assertEqual(battle.state, "question")            # straight into the binding challenge
        self.assertEqual(battle.panel_kind, "capture")

    def test_no_capture_for_trainers_and_without_mathballs(self):
        battle = self.battle_with(0.2, kind="trainer")
        self.assertNotIn("CAPTURE", battle.actions())
        battle = self.battle_with(0.2)
        for name in list(battle.battle_items()):
            while battle.bag.count(name):
                battle.bag.take(name)
        battle.choose_action("CAPTURE")
        self.assertEqual(battle.state, "menu")
        self.assertIn("Mathball", battle.message)


class Bug9NovTests(GameCase):
    """Bug report 9 Nov: three companions, a livelier Recovery Center, Bram's sprite, battle music."""

    def test_up_to_three_companions_follow_and_the_party_screen_picks_them(self):
        game = self.game
        game.party.add(create("GEOMAX", 5))
        game.party.add(create("DIVOWL", 4))
        game.save_party()
        world = game.world
        self.assertEqual([m.name for m in world.followers()], [m.name for m in game.party.party])
        for _ in range(80):
            world.update(1, 0)
        spots = [world.avatar.follower_spot(14 * (i + 1)) for i in range(3)]
        self.assertGreater(world.avatar.x - spots[2][0], world.avatar.x - spots[0][0])   # in a line behind
        party = game.open_screen("party")
        party.selected = 1
        party.handle_key(pygame.K_f)                          # GEOMAX rests in its Mathball
        self.assertEqual([m.name for m in world.followers()], [game.party.party[0].name, "DIVOWL"])
        self.assertIn("rests", party.notice)
        party.draw(pygame.Surface((320, 240)), 1)
        party.handle_key(pygame.K_f)
        self.assertEqual(len(world.followers()), 3)
        game.world.draw(pygame.Surface((320, 240)), 1)

    def test_the_recovery_center_has_people_who_move_and_talk(self):
        game = self.game
        game._travel_to_map("village_recovery", (7, 7))
        world = game.world
        self.assertEqual(world.world.background, "village_recovery_interior_v2.png")   # people painted out
        self.assertTrue((ROOT / "assets" / "backgrounds" / "village_recovery_interior.png").exists())  # kept
        hana = next(n for n in world.npcs if n.id == "nurse_hana")
        desk = next(n for n in world.npcs if n.id == "mcr_farah")
        self.assertEqual(desk.cell(), (7, 2))                  # behind the counter
        visited, said = set(), set()
        surface = pygame.Surface((320, 240))
        for frame in range(3600):
            world.update()
            visited.add(hana.cell())
            said |= {n.bubble[0] for n in world.npcs if n.bubble}
            if frame % 300 == 0:
                world.draw(surface, frame)
        self.assertTrue({(12, 3), (13, 3), (14, 3)} & visited)   # she checks the capsules
        self.assertGreater(len(visited), 5)                       # and really walks around
        self.assertTrue(said)
        # Talking to Nurse Hana offers the Recovery Capsule.
        hana.state = "talking"
        world._talk(hana)
        self.assertIn("clinic", [action for _, action in world.dialogue.choices])

    def test_bram_has_his_own_sprite_and_battles_have_their_music(self):
        forest = load_map("number_forest")
        bram = next(n for n in forest.data["npcs"] if n["id"] == "bram")
        self.assertEqual(bram["sheet"], "characters/BRAM")
        self.assertTrue((ROOT / "assets" / "sprites" / "characters" / "BRAM" / "manifest.json").exists())
        for track in ("wild_battle", "arena"):
            self.assertTrue((ROOT / "assets" / "sounds" / f"{track}.ogg").exists(), track)
        from game import audio
        game = self.game
        played = []
        original = audio.music
        audio.music = played.append
        try:
            game._start_battle(create("VOLTIX", 2), "wild")
            game._play_music()
            game.battle.battle.kind = "trainer"
            game._play_music()
        finally:
            audio.music = original
        self.assertEqual(played, ["wild_battle", "battle"])


class TrialsInTheWorldTests(GameCase):
    """1:16PM report: Trial monsters are fought only by finding them on the map."""

    def test_a_trial_monster_roams_its_area_and_touching_it_starts_the_battle(self):
        game = self.game
        world = game.world
        ids = {t.id for t in world.trial_roamers}
        self.assertEqual(ids, {"voltbyte", "mycomorph", "nullshade"})   # Number Forest's three
        trial = next(t for t in world.trial_roamers if t.id == "voltbyte")
        world.encounter_grace = 0
        world.avatar.x, world.avatar.y = trial.x, trial.y
        game.world.draw(pygame.Surface((320, 240)), 1)
        event = world.update()
        self.assertEqual(event, "trial")
        game.states.clear()                                   # (the meadow's arrival scene, if it queued)
        game.story_busy, game.story_queue = False, []
        game._start_trial(world.encounter_trial)
        self.assertEqual(game.state, "mbattle")
        self.assertTrue(world.has_flag("trial_seen:voltbyte"))
        self.assertNotIn("voltbyte", {t.id for t in world.trial_roamers})   # gone until you come back
        game.monster_battle.closed = True
        game.monster_battle.handle_key = lambda *a: None
        game._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0))
        self.assertEqual(game.state, "overworld")

    def test_story_trials_wait_at_their_gates_and_the_rest_hide_far_away(self):
        from game.trial_roamers import spawn_for, walking_distances
        chronos = load_map("chronos_dimension")
        beaten = {m: {"wins": 1} for m in ("voltbyte", "mycomorph", "nullshade", "crystalgon", "equinox", "sphynox")}
        ids = {t.id for t in spawn_for(chronos, beaten, random.Random(1))}
        self.assertNotIn("infinity_zero", ids)                   # fought at the Time Spire gate instead
        self.assertEqual(ids, {"chronowl", "hexabyte"})
        gate = next(e for e in chronos.data["interactables"] if e.get("kind") == "boss_gate")
        self.assertEqual(gate["trial"], "infinity_zero")
        forest = load_map("number_forest")
        distances = walking_distances(forest)
        for trial in spawn_for(forest, {}, random.Random(2)):
            same_area = [d for c, d in distances.items() if forest.area_at(c)[0] == forest.area_at(trial.home)[0]]
            # Hidden in the far end of its area: further than 80% of that area's cells.
            self.assertGreaterEqual(distances[trial.home], sorted(same_area)[int(len(same_area) * 0.8)], trial.id)


class QuestTrackerTests(GameCase):
    """1:16PM report: quests in the top-right corner, with a show/hide button and the distance."""

    def test_tracker_shows_the_quest_and_how_far_the_objective_is(self):
        game = self.game
        world = game.world
        entries = world.tracker.entries()
        self.assertTrue(entries)
        title, step, distance = entries[0]
        self.assertTrue(title and step)
        self.assertRegex(distance, r"^(\d+ m (N|NE|E|SE|S|SW|W|NW)|You're here!|In .+)$")
        world.draw(pygame.Surface((320, 240)), 1)

    def test_the_tab_button_and_j_hide_and_show_it(self):
        from game.quest_tracker import TAB
        game = self.game
        tracker = game.world.tracker
        self.assertTrue(tracker.visible)
        game._overworld_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j, unicode="j", mod=0))
        self.assertFalse(tracker.visible)
        self.assertIn("ui:quest_tracker_hidden", game.repository.world_flags(game.player.player_id))  # remembered
        from game import ui
        ui.set_view(1, (0, 0))
        game._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=TAB.center))
        self.assertTrue(tracker.visible)

    def test_objectives_point_at_people_places_and_objects(self):
        from game.quest_tracker import direction
        world = self.game.world
        tracker = world.tracker
        self.assertIsInstance(tracker.target({"type": "talk", "npc": "bram"}), tuple)
        self.assertIsInstance(tracker.target({"type": "challenge", "id": "stone_1"}), tuple)
        self.assertIsInstance(tracker.target({"type": "visit", "area": "ridge"}), tuple)
        self.assertEqual(tracker.target({"type": "talk", "npc": "vexa"}), "Algebra Cavern")
        self.assertIsInstance(tracker.target({"type": "win_battles", "count": 1}), tuple)
        self.assertEqual(direction(10, -10), "NE")
        self.assertEqual(direction(0, 5), "S")


class SoundSettingsTests(GameCase):
    """1:47 report: a Settings screen that controls the sound."""

    def test_volumes_mute_and_scanlines_are_saved(self):
        from game import audio, settings
        from states.settings_state import ROWS, SettingsScreen
        game = self.game
        screen = SettingsScreen(game)
        screen.selected = ROWS.index("music")
        before = screen.values["music"]
        screen.handle_key(pygame.K_LEFT)
        self.assertEqual(screen.values["music"], max(0, before - 1))
        self.assertAlmostEqual(audio._state["music_volume"], screen.values["music"] / 10)
        screen.selected = ROWS.index("sfx")
        screen.handle_key(pygame.K_RIGHT)
        screen.selected = ROWS.index("sound")
        screen.handle_key(pygame.K_RETURN)
        self.assertFalse(game.sound)
        self.assertFalse(audio._state["enabled"])
        screen.draw(pygame.Surface((320, 240)), 1)
        self.assertEqual(settings.load(game.settings_folder)["sound"], False)   # remembered for next time
        self.assertTrue(str(game.settings_folder).startswith(self.folder.name))  # tests never touch real saves
        screen.handle_key(pygame.K_RETURN)
        self.assertTrue(audio._state["enabled"])
        screen.handle_key(pygame.K_ESCAPE)
        self.assertTrue(screen.closed)

    def test_settings_open_from_the_title_and_the_pause_menu(self):
        from states.pause_state import PauseScreen
        from states.settings_state import SettingsScreen
        game = self.game
        pause = game.states.push(PauseScreen(game))
        pause.activate(2)
        self.assertIsInstance(game.states.overlay, SettingsScreen)
        game.states.clear()
        game.state = "settings"
        game._draw_settings()
        game._settings_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="", mod=0))
        self.assertEqual(game.state, "menu")


class SaveProfileTests(unittest.TestCase):
    """3:07 report: one player can keep several save profiles; a new one never deletes the old ones."""

    def setUp(self):
        from game.game_manager import GameManager
        self.folder = tempfile.TemporaryDirectory()
        self.path = self.folder.name + "/profiles.sqlite3"
        self.game = GameManager(database_path=self.path)

    def tearDown(self):
        self.game.llm.close()
        self.folder.cleanup()

    def new_profile(self, name, starter=0):
        game = self.game
        game.player_name, game.starter_selected = name, starter
        game._create_new_player()
        finish_story(game)
        return game.player.player_id

    def test_new_profiles_keep_the_old_ones_and_continue_lets_you_choose(self):
        from states.profile_select_state import ProfileScreen
        game = self.game
        first = self.new_profile("Ana", 0)
        game.repository.add_coins(first, 123)
        game.save_all()
        second = self.new_profile("Ben", 2)
        names = [p["name"] for p in game.repository.list_profiles()]
        self.assertEqual(set(names), {"Ana", "Ben"})             # Ana's journey was not deleted
        self.assertEqual(game.repository.coins(first), game.repository.coins(second) + 123)
        # Back on the title screen: CONTINUE opens the profile list.
        game.state = "menu"
        game.menu_selected = game.MENU_CHOICES.index("CONTINUE")
        game._menu_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r", mod=0))
        screen = game.states.overlay
        self.assertIsInstance(screen, ProfileScreen)
        screen.draw(pygame.Surface((320, 240)), 1)
        screen.selected = next(i for i, p in enumerate(screen.profiles) if p["name"] == "Ana")
        screen.handle_key(pygame.K_RETURN)
        game.states._pop_closed()
        self.assertEqual(game.player.player_id, first)
        self.assertEqual(game.player.name, "Ana")
        self.assertEqual(game.repository.load_player().name, "Ana")   # now the most recently played

    def test_deleting_a_profile_needs_two_presses_and_removes_only_that_one(self):
        from states.profile_select_state import ProfileScreen
        game = self.game
        keep = self.new_profile("Keep")
        gone = self.new_profile("Gone")
        screen = ProfileScreen(game)
        screen.selected = next(i for i, p in enumerate(screen.profiles) if p["player_id"] == gone)
        screen.handle_key(pygame.K_x)
        self.assertEqual(len(game.repository.list_profiles()), 2)    # first press only asks
        self.assertIn("again", screen.notice)
        screen.handle_key(pygame.K_x)
        self.assertEqual([p["player_id"] for p in game.repository.list_profiles()], [keep])
        self.assertEqual(game.repository.load_party(gone).party, [])
        self.assertTrue(game.repository.load_party(keep).party)

    def test_there_is_a_limit_of_six_profiles(self):
        from states.profile_select_state import MAX_PROFILES, ProfileScreen
        game = self.game
        for i in range(MAX_PROFILES):
            self.new_profile(f"P{i}")
        game.state = "menu"
        game.menu_selected = game.MENU_CHOICES.index("NEW GAME")
        game._menu_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r", mod=0))
        self.assertEqual(game.state, "menu")
        self.assertIn("delete", game.menu_hint)
        screen = ProfileScreen(game)
        screen.handle_key(pygame.K_n)
        self.assertFalse(screen.closed)


class NextDestinationTests(GameCase):
    """3:42 report: after a chapter's quests are done, the game points the player to the next world."""

    def test_after_the_guardian_the_tracker_points_to_the_lab_gateway(self):
        game = self.game
        for flag in ("boss:numerex", "region:number_forest_complete", "boss:guardian",
                     "region:algebra_cavern_complete"):
            game.world.set_flag(flag)
        for quest_id in list(game.quests.active()):
            if game.quests.definition(quest_id).get("category") == "main":
                game.quests._save(quest_id, "completed", {})
        game._travel_to_map("algebra_cavern", (10, 24))
        from tests.test_cutscene import run_scene
        run_scene(game)
        game.quests._save("unknown_guardian", "completed", {})
        title, text_, distance = game.world.tracker.entries()[0]
        self.assertEqual(title, "NEXT DESTINATION")
        self.assertIn("Geometry Kingdom", text_)
        self.assertIn("Lab Gateway", text_)
        self.assertRegex(distance, r"^\d+ m [NESW]{1,2}$")
        game.world.tracker.toggle()
        self.assertIn("NEXT: Travel to the Geometry Kingdom", game.world.quest_hint())

    def test_from_another_map_it_names_where_the_portal_is(self):
        game = self.game
        for flag in ("boss:numerex", "region:number_forest_complete"):
            game.world.set_flag(flag)
        game.quests._save("fading_numera", "completed", {})
        upcoming = game.world.tracker.next_destination()
        self.assertEqual(upcoming[0], "NEXT DESTINATION")
        self.assertIn("Algebra Cavern", upcoming[1])              # the cave in the ruins
        self.assertRegex(upcoming[2], r"^\d+ m ")                 # that entrance is on this map

    def test_no_next_destination_while_a_main_quest_is_running(self):
        self.assertIsNone(self.game.world.tracker.next_destination())


class WorldMapPinTests(GameCase):
    """Report: pick SPAWN POINTS on the map, see quest locations, and open quests from it."""

    def open_map(self):
        from game.worldmap_screen import WorldMapScreen
        game = self.game
        game._overworld_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n, unicode="n", mod=0))
        self.assertIsInstance(game.map_screen, WorldMapScreen)
        return game.map_screen

    def test_spawn_points_and_quest_pins_are_on_the_map(self):
        screen = self.open_map()
        kinds = {p["kind"] for p in screen.pins}
        self.assertEqual(kinds, {"spawn", "quest"})
        quest_pins = [p for p in screen.pins if p["kind"] == "quest"]
        self.assertIn("fading_numera", {p["quest"] for p in quest_pins})
        self.assertEqual(screen.pins[screen.selected]["kind"], "quest")    # starts on your quest
        surface = pygame.Surface((320, 240))
        for key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_LEFT, pygame.K_UP, pygame.K_TAB):
            screen.handle_key(key)
            screen.draw(surface, 1)

    def test_a_quest_pin_opens_the_quest_log_on_that_quest(self):
        from states.quest_state import QuestScreen
        game = self.game
        screen = self.open_map()
        screen.selected = next(i for i, p in enumerate(screen.pins) if p.get("quest") == "fading_numera")
        game._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r", mod=0))
        self.assertEqual(game.state, "overworld")
        log = game.states.overlay
        self.assertIsInstance(log, QuestScreen)
        self.assertEqual(log.entries[log.selected], "fading_numera")

    def test_a_locked_place_your_quest_leads_to_shows_the_quest(self):
        from states.quest_state import QuestScreen
        game = self.game
        screen = self.open_map()
        target = next(p for p in screen.pins if p["kind"] == "quest" and p["quest"] == "fading_numera")
        cell = (int(target["x"] // 16), int(target["y"] // 16))
        area = game.world.world.area_at(cell)[0]
        spawn = next((i for i, p in enumerate(screen.pins) if p["kind"] == "spawn" and p["area"] == area), None)
        if spawn is None or screen.pins[spawn]["unlocked"]:
            self.skipTest("the first quest's objective is in an area you have already visited")
        screen.selected = spawn
        screen.activate()
        self.assertEqual(screen.open_quest, "fading_numera")
        game._finish_map()
        self.assertIsInstance(game.states.overlay, QuestScreen)

    def test_click_a_pin_to_select_then_again_to_go(self):
        from game import ui
        game = self.game
        screen = self.open_map()
        ui.set_view(1, (0, 0))
        index = next(i for i, p in enumerate(screen.pins) if p["kind"] == "spawn" and p["unlocked"]
                     and p["area"] != game.world.area_id) if any(
            p["kind"] == "spawn" and p["unlocked"] and p["area"] != game.world.area_id for p in screen.pins) else None
        if index is None:
            game.world.set_flag("visited:meadow")
            screen = self.open_map()
            index = next(i for i, p in enumerate(screen.pins) if p["kind"] == "spawn" and p["area"] == "meadow")
        pin = screen.pins[index]
        pos = tuple(int(v) for v in screen.to_map(pin["x"], pin["y"]))
        game._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        self.assertEqual(game.map_screen.selected, index)
        game._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        self.assertEqual(game.state, "overworld")
        self.assertEqual(game.world.area_id, pin["area"])

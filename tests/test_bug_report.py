"""The items from 'Mathmon bug report.pdf':
1 visual hints, 2 music and sound effects, 3 choosing a companion in the MathDex, 4 map crossings,
5 a Mathmon Recovery Center that heals by solving maths, 6 a Mathmart with the requested items."""
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
        game._travel_to_map("village_recovery", (14, 16))
        world = game.world
        world.avatar.x, world.avatar.y = world.world.cell_to_feet((14, 8))
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

    def test_right_answers_heal_and_advance_the_chamber(self):
        game = self.game
        lead = game.party.lead
        lead.hp = 0
        game.party.add(create("GEOMAX", 5))
        game.party.party[1].hp = 10
        game.save_party()
        clinic = self.enter_center()
        self.assertEqual(type(clinic).__name__, "ClinicScreen")
        clinic.handle_key(pygame.K_RETURN)
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
        self.assertTrue(all(m.hp == m.max_hp for m in game.party.party))
        self.assertEqual(game.repository.load_party(game.player.player_id).party[0].hp, lead.max_hp)
        self.assertGreaterEqual(game.repository.history_summary(game.player.player_id)["attempted"], 3)
        surface = pygame.Surface((320, 240))
        clinic.draw(surface, 1)

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
        self.assertEqual(clinic.state, "done")

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

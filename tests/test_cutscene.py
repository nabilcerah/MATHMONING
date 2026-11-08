"""Cutscenes: characters walk to the player, the camera pans, guides introduce themselves (so the
'Meet ...' quest steps complete on their own), skipping works, and missing characters never block."""
import tempfile
import unittest

from tests.story_helpers import finish_story  # sets the SDL dummy drivers first

import pygame

from game.game_manager import GameManager
from states.cutscene import Cutscene
from states.scene_state import SceneScreen


def run_scene(game, limit=3000):
    """Play the story overlays frame by frame, like a player who presses ENTER after each line."""
    seen = []
    for _ in range(limit):
        game._update()
        screen = game.states.overlay
        if screen is None:
            return seen
        if isinstance(screen, SceneScreen):
            if screen.scene["id"] not in seen:
                seen.append(screen.scene["id"])
            if screen.cutscene is None:
                if screen.in_choice:
                    screen.choose(len(screen.options()) - 1)
                elif screen.revealed:
                    screen.handle_key(pygame.K_RETURN)
        else:
            screen.close()
        game.states._pop_closed()
    raise AssertionError("story never finished")


class CutsceneTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.game = GameManager(database_path=self.folder.name + "/c.sqlite3")
        game = self.game
        game.player_name = "Sam"
        game.state = "avatar"
        game._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0))
        finish_story(game)                 # the opening plays before the world exists
        game._create_new_player()
        self.close_cards()

    def close_cards(self):
        from states.codex_state import ChapterCard
        while isinstance(self.game.states.overlay, ChapterCard):
            self.game.states.overlay.close()
            self.game.states._pop_closed()

    def tearDown(self):
        self.game.llm.close()
        self.folder.cleanup()

    def rowan(self):
        return next(n for n in self.game.world.npcs if n.id == "rowan")

    def test_professor_walks_to_the_player_and_the_meet_step_completes(self):
        screen = self.game.states.overlay
        self.assertIsInstance(screen, SceneScreen)
        self.assertIsNotNone(screen.cutscene)               # it starts with a cutscene, not a text box
        self.assertTrue(self.game.world.cinematic)          # HUD hidden, letterbox bars
        start = self.rowan().cell()
        self.assertIn("prologue_village", run_scene(self.game))
        rowan, avatar = self.rowan().cell(), self.game.world.avatar.cell()
        self.assertNotEqual(start, rowan)                   # he really walked
        self.assertEqual(abs(rowan[0] - avatar[0]) + abs(rowan[1] - avatar[1]), 1)
        self.assertFalse(self.game.world.cinematic)
        self.assertIsNone(self.game.world.camera_focus)
        self.assertIn("Win a battle", self.game.world.quest_hint())

    def test_enter_skips_a_cutscene_and_everyone_ends_up_in_place(self):
        screen = self.game.states.overlay
        screen.handle_key(pygame.K_RETURN)                  # skip the walk...
        self.assertIsNotNone(screen.cutscene)               # ...the first line has its own camera pan
        screen.handle_key(pygame.K_RETURN)                  # skip that too
        self.assertIsNone(screen.cutscene)
        self.assertIsNotNone(screen.line)
        rowan, avatar = self.rowan().cell(), self.game.world.avatar.cell()
        self.assertEqual(abs(rowan[0] - avatar[0]) + abs(rowan[1] - avatar[1]), 1)

    def test_steps_for_absent_characters_are_skipped(self):
        run_scene(self.game)
        cut = Cutscene(self.game.world, [{"do": "walk", "who": "nobody", "to": "player"},
                                          {"do": "emote", "who": "ghost", "emote": "!"}])
        self.assertTrue(cut.finished)
        cut.release()
        surface = pygame.Surface((320, 240))
        cut = Cutscene(self.game.world, [{"do": "shake", "t": 0.2}, {"do": "flash"}, {"do": "fade", "to": "black"},
                                          {"do": "fade", "to": "clear"}, {"do": "emote", "who": "player", "emote": "?"}])
        for frame in range(200):
            cut.update()
            cut.draw(surface, frame)
            if cut.finished:
                break
        self.assertTrue(cut.finished)
        cut.release()

    def test_guide_walks_over_on_arrival_and_gives_the_quest(self):
        game = self.game
        run_scene(game)
        game.world.set_flag("boss:numerex")
        game._travel_to_map("algebra_cavern", (10, 24))
        for _ in range(30):
            game._update()
        seen = run_scene(game)
        self.assertIn("cavern_arrival", seen)
        vexa = next(n for n in game.world.npcs if n.id == "vexa")
        avatar = game.world.avatar.cell()
        self.assertEqual(abs(vexa.cell()[0] - avatar[0]) + abs(vexa.cell()[1] - avatar[1]), 1)
        self.assertTrue(game.world.has_flag("met:vexa"))
        self.assertEqual(game.quests.status("unknown_guardian"), "active")
        self.assertGreater(game.quests.step_index("unknown_guardian"), 0)   # 'Meet Dr. Vexa' already done


if __name__ == "__main__":
    unittest.main()

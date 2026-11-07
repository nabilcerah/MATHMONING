import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from game.creatures import ENEMIES
from game.game_manager import GameManager


class GameSmokeTests(unittest.TestCase):
    def test_scenes_draw_and_battle_records_a_correct_answer(self):
        with tempfile.TemporaryDirectory() as folder:
            game = GameManager(database_path=folder + "/smoke.sqlite3")
            try:
                for state in ("menu", "name", "starter", "settings"):
                    game.state = state
                    game._draw()
                game._create_new_player()
                self.assertEqual(game.state, "overworld")
                self.assertEqual(game.world.move(1, 0), "moved")
                game.player.x, game.player.y = 7, 6
                self.assertEqual(game.world.interact(), "guide")
                game._draw()
                game._start_battle(ENEMIES[0])
                game._draw()
                game.battle._start_question("addition")
                game.battle.draw(game.canvas, 0)
                game.battle.answer = game.battle.question.answer
                game.battle._submit()
                game.battle.draw(game.canvas, 1)
                profile = game.repository.get_learning_profile(game.player.player_id)
                self.assertEqual(profile["addition"]["correct"], 1)
                game._start_battle(ENEMIES[3])
                game.battle._start_question()
                self.assertEqual(game.battle.question.topic, "addition")
                game.battle.answer = game.battle.question.answer
                game.battle._submit()
                game.battle._start_question()
                self.assertEqual(game.battle.question.topic, "subtraction")
                game.state = "profile"
                game._draw()
                original_event_get = pygame.event.get
                pygame.event.get = lambda: [pygame.event.Event(pygame.QUIT)]
                try:
                    with self.assertRaises(SystemExit) as exit_result:
                        game.run()
                    self.assertEqual(exit_result.exception.code, 0)
                finally:
                    pygame.event.get = original_event_get
            finally:
                game.llm.close()
                pygame.quit()


if __name__ == "__main__":
    unittest.main()

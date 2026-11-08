import os
import random
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from game.puzzle_screen import PuzzleScreen
from mathematics import puzzles as P

pygame.init()


def key(code, ch=""):
    return code, ch


class PuzzleLogicTests(unittest.TestCase):
    def test_every_generated_puzzle_is_solvable(self):
        rng = random.Random(9)
        for tier in (0, 1, 2):
            for _ in range(150):
                for kind in ("sequence", "balance", "target", "magic"):
                    puzzle = P.GENERATORS[kind](rng, tier)
                    answer = puzzle.answer
                    if kind == "target":
                        answer = puzzle.solution.split(": ", 1)[1].split(" = ")[0]
                    self.assertTrue(P.check(puzzle, answer), puzzle.prompt)
                for round_index in range(3):
                    star = P.starchart(rng, tier, round_index)
                    x, y = star.answer
                    self.assertTrue(0 <= x < star.data["size"] and 0 <= y < star.data["size"])
                    if star.data["line"]:
                        m, c = star.data["line"]
                        self.assertEqual(y, m * x + c)

    def test_target_expressions_are_safe_and_must_use_the_given_numbers(self):
        self.assertEqual(P.evaluate_expression("3x5+8", [3, 5, 8]), 23)
        self.assertEqual(P.evaluate_expression("(8-3)×5", [3, 5, 8]), 25)
        self.assertIsNone(P.evaluate_expression("3*5+8+1", [3, 5, 8]))  # extra number
        self.assertIsNone(P.evaluate_expression("3*5", [3, 5, 8]))      # missing number
        self.assertIsNone(P.evaluate_expression("__import__('os')", [1]))
        self.assertIsNone(P.evaluate_expression("2**9", [2, 9]))        # only + - x allowed

    def test_magic_square_rules(self):
        self.assertTrue(P.magic_ok([list(row) for row in P.LO_SHU]))
        self.assertFalse(P.magic_ok([[1, 2, 3], [4, 5, 6], [7, 8, 9]]))


class PuzzleScreenTests(unittest.TestCase):
    def setUp(self):
        self.surface = pygame.Surface((320, 240))

    def type(self, screen, chars):
        for ch in chars:
            screen.handle_key(0, ch)
        screen.handle_key(pygame.K_RETURN)

    def test_typed_puzzles_solve_with_keys(self):
        for kind in ("sequence", "balance", "target"):
            screen = PuzzleScreen(kind, 1, random.Random(4))
            screen.draw(self.surface, 0)
            answer = screen.puzzle.answer if kind != "target" else \
                screen.puzzle.solution.split(": ", 1)[1].split(" = ")[0].replace(" ", "").replace("×", "x").replace("−", "-")
            self.type(screen, str(answer))
            self.assertTrue(screen.solved, kind)
            screen.draw(self.surface, 1)

    def test_hint_then_reveal_after_misses(self):
        screen = PuzzleScreen("sequence", 0, random.Random(2))
        for _ in range(2):
            self.type(screen, "999999")
        self.assertTrue(screen.message.startswith("Hint"))
        for _ in range(2):
            self.type(screen, "999999")
        self.assertTrue(screen.revealed)
        self.assertIn(screen.puzzle.answer, screen.message)
        self.type(screen, screen.puzzle.answer)
        self.assertTrue(screen.solved)

    def test_magic_square_by_cursor(self):
        screen = PuzzleScreen("magic", 2, random.Random(5))
        solution = screen.puzzle.data["solution"]
        for r in range(3):
            for c in range(3):
                if (r, c) not in screen.locked:
                    screen.cell = (r, c)
                    screen.handle_key(0, str(solution[r][c]))
        screen.draw(self.surface, 0)
        screen.handle_key(pygame.K_RETURN)
        self.assertTrue(screen.solved)

    def test_star_chart_three_rounds(self):
        screen = PuzzleScreen("starchart", 0, random.Random(6))
        for round_index in range(3):
            self.assertEqual(screen.round, round_index)
            target_x, target_y = screen.puzzle.answer
            for _ in range(target_x):
                screen.handle_key(pygame.K_RIGHT)
            for _ in range(target_y):
                screen.handle_key(pygame.K_UP)
            screen.draw(self.surface, round_index)
            screen.handle_key(pygame.K_RETURN)
        self.assertTrue(screen.solved)


class ShrineTests(unittest.TestCase):
    def test_shrine_rewards_once_per_day(self):
        from game.game_manager import GameManager
        with tempfile.TemporaryDirectory() as folder:
            game = GameManager(database_path=folder + "/shrine.sqlite3")
            try:
                game.player_name = "Solver"
                game._create_new_player()
                world = game.world
                shrine = world.objects["shrine_sequence"]
                exp_before = game.party.lead.exp + game.party.lead.level * 1000
                potions = game.repository.inventory(game.player.player_id)["Health Potion"]
                x, y = shrine["pos"]
                world.avatar.x, world.avatar.y = world.world.cell_to_feet((x, y + 1))
                world.avatar.facing = (0, -1)
                world.update()
                self.assertIn("new puzzle", world.prompt())
                enter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, unicode="", mod=0)
                game._overworld_key(enter)          # open the shrine dialogue
                world.dialogue.age = 10 ** 6         # skip the typewriter
                game._overworld_key(enter)          # "Solve it!"
                self.assertEqual(game.state, "puzzle")
                puzzle = game.puzzle
                for ch in puzzle.puzzle.answer:
                    game._handle_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=ch, mod=0))
                game._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0))
                game._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0))
                self.assertEqual(game.state, "overworld")
                self.assertGreater(game.party.lead.exp + game.party.lead.level * 1000, exp_before)
                self.assertEqual(game.repository.inventory(game.player.player_id)["Health Potion"], potions + 1)
                self.assertTrue(world.shrine_done("shrine_sequence"))
                world.update()                       # the [E] prompt refreshes each frame
                self.assertIn("solved today", world.prompt())
                world.today = "2999-01-01"           # tomorrow brings a new puzzle
                self.assertFalse(world.shrine_done("shrine_sequence"))
            finally:
                game.llm.close()


if __name__ == "__main__":
    unittest.main()

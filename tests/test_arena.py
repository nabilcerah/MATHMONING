import os
import random
import statistics
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from ai.arena_agent import RIVALS, ArenaRivalAgent, elo_change, rank_for
from ai.orchestrator import AgentOrchestrator
from database.database import Database
from database.player_repository import PlayerRepository
from game.arena import COUNTDOWN, ArenaScreen
from game.creatures import creature_spec
from game.player import Player
from mathematics.question_generator import QuestionGenerator

pygame.init()


class RivalAgentTests(unittest.TestCase):
    def test_stronger_rivals_are_faster_and_more_accurate(self):
        generator = QuestionGenerator(random.Random(1))
        questions = [generator.generate("easy", "addition") for _ in range(300)]
        results = []
        for profile in (RIVALS[0], RIVALS[-1]):
            agent = ArenaRivalAgent(profile, rng=random.Random(2))
            plans = [agent.plan(q) for q in questions]
            results.append((statistics.mean(p.think_seconds for p in plans), sum(p.correct for p in plans)))
        (weak_time, weak_correct), (strong_time, strong_correct) = results
        self.assertLess(strong_time, weak_time)
        self.assertGreater(strong_correct, weak_correct)

    def test_wrong_answers_look_like_real_slips(self):
        agent = ArenaRivalAgent(RIVALS[0], rng=random.Random(3))
        for answer in ("42", "7", "3.25"):
            slip = agent._near_miss(answer)
            self.assertNotEqual(slip, answer)

    def test_ratings_and_ranks(self):
        self.assertGreater(elo_change(1000, 1200, True), elo_change(1000, 800, True))
        self.assertLess(elo_change(1000, 800, False), 0)
        self.assertEqual([rank_for(r) for r in (900, 1000, 1200, 1350, 1500)],
                         ["BRONZE", "SILVER", "GOLD", "PLATINUM", "CHAMPION"])


class ArenaMatchTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repository = PlayerRepository(Database(self.folder.name + "/arena.sqlite3"))
        player_id = self.repository.create_player("Racer", "AQUABIT", 38)
        self.player = Player("Racer", "AQUABIT", 3, 38, 38, 0, 16, 60, player_id)
        self.orchestrator = AgentOrchestrator(self.repository)
        self.arena = ArenaScreen(self.repository, self.orchestrator, self.player, creature_spec("AQUABIT", 3),
                                 "characters/ALEX", random.Random(4))
        self.surface = pygame.Surface((320, 240))

    def tearDown(self):
        self.folder.cleanup()

    def start(self, rival_index=0):
        self.arena.selected = rival_index
        self.arena.handle_key(pygame.K_RETURN)
        self.assertEqual(self.arena.state, "countdown")

    def skip_countdown(self):
        for _ in range(COUNTDOWN + 1):
            self.arena.update()
        self.assertEqual(self.arena.state, "round")

    def answer_correctly(self):
        question = self.arena.question
        answer = question.answer
        if question.format == "target":
            answer = question.explanation.split(": ", 1)[1].split(" = ")[0].replace(" ", "").replace("×", "x").replace("−", "-")
        for ch in answer:
            self.arena.handle_key(0, ch)
        self.arena.handle_key(pygame.K_RETURN)

    def finish_reveal(self):
        self.arena.handle_key(pygame.K_RETURN)
        self.arena.update()

    def test_a_quick_player_sweeps_and_climbs(self):
        self.assertEqual(self.arena.rivals[1].name, "Luna")  # Alex's friend-rival is Luna
        attempts_before = self.repository.overall_summary(self.player.player_id)["attempted"]
        self.start(0)
        for _ in range(3):
            self.skip_countdown()
            self.answer_correctly()
            self.assertEqual(self.arena.state, "reveal")
            self.arena.draw(self.surface, 1)
            self.finish_reveal()
        self.assertEqual(self.arena.state, "result")
        self.assertTrue(self.arena.result["won"])
        self.assertGreater(self.arena.stats["rating"], 1000)
        self.assertEqual(self.repository.arena_stats(self.player.player_id)["wins"], 1)
        self.assertIn("arena_beaten:byte", self.repository.world_flags(self.player.player_id))
        self.assertEqual(self.repository.inventory(self.player.player_id)["Math Capsule"], 6)
        self.assertEqual(self.repository.overall_summary(self.player.player_id)["attempted"], attempts_before + 3)
        self.arena.draw(self.surface, 2)
        self.arena.handle_key(pygame.K_RETURN)
        self.assertEqual(self.arena.state, "lobby")
        self.assertEqual(self.arena.selected, 1)  # next rung of the ladder

    def test_a_correct_rival_takes_rounds_you_dont_answer(self):
        self.start(2)
        for _ in range(3):
            self.skip_countdown()
            self.arena.plan.correct = True
            self.arena.plan.think_seconds = 1.5
            for _ in range(100):
                self.arena.update()
            self.assertEqual(self.arena.winner, "rival")
            self.finish_reveal()
        self.assertFalse(self.arena.result["won"])
        self.assertLess(self.arena.stats["rating"], 1000)
        self.assertEqual(self.arena.stats["streak"], 0)

    def test_a_wrong_rival_is_locked_out(self):
        self.start(1)
        self.skip_countdown()
        self.arena.plan.correct = False
        self.arena.plan.think_seconds = 1.5
        for _ in range(100):
            self.arena.update()
        self.assertTrue(self.arena.rival_locked)
        self.assertEqual(self.arena.state, "round")
        self.answer_correctly()
        self.assertEqual(self.arena.winner, "you")

    def test_forfeit_needs_two_presses(self):
        self.start(0)
        self.skip_countdown()
        self.arena.handle_key(pygame.K_ESCAPE)
        self.assertEqual(self.arena.state, "round")
        self.arena.handle_key(pygame.K_ESCAPE)
        self.assertEqual(self.arena.state, "result")
        self.assertTrue(self.arena.result["forfeit"])

    def test_lobby_updates_every_frame_before_any_match(self):
        # The game calls update() every frame, even while you browse the ladder.
        for frame in range(30):
            self.arena.update()
            self.arena.draw(self.surface, frame)
        self.assertEqual(self.arena.state, "lobby")

    def test_every_screen_draws(self):
        self.arena.draw(self.surface, 0)
        for index in range(len(self.arena.rivals)):
            self.arena.selected = index
            self.arena.draw(self.surface, index)
        self.start(5)
        for frame in range(COUNTDOWN + 30):
            self.arena.update()
            if frame % 25 == 0:
                self.arena.draw(self.surface, frame)


class ArenaOnTheMapTests(unittest.TestCase):
    def test_entering_the_arena_from_the_map(self):
        from game.game_manager import GameManager
        with tempfile.TemporaryDirectory() as folder:
            game = GameManager(database_path=folder + "/map.sqlite3")
            try:
                game.player_name = "Visitor"
                game._create_new_player()
                world = game.world
                x, y = world.objects["arena"]["pos"]
                world.avatar.x, world.avatar.y = world.world.cell_to_feet((x, y + 1))
                world.avatar.facing = (0, -1)
                world.update()
                self.assertIn("race AI rivals", world.prompt())
                game._overworld_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, unicode="", mod=0))
                self.assertEqual(game.state, "arena")
                game._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="", mod=0))
                self.assertEqual(game.state, "overworld")
            finally:
                game.llm.close()


if __name__ == "__main__":
    unittest.main()

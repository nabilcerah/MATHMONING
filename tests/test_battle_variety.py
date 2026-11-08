import os
import random
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from ai.orchestrator import AgentOrchestrator
from database.database import Database
from database.player_repository import PlayerRepository
from game.battle import Battle
from game.creatures import BOSS, WILD_BY_NAME
from game.player import Player

pygame.init()
ENTER = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0)


def typed(ch):
    return pygame.event.Event(pygame.KEYDOWN, key=0, unicode=ch, mod=0)


class PuzzleAttackTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repository = PlayerRepository(Database(self.folder.name + "/variety.sqlite3"))
        player_id = self.repository.create_player("Mixer", "PYRON", 34)
        self.player = Player("Mixer", "PYRON", 3, 34, 34, 0, 16, 60, player_id)
        self.orchestrator = AgentOrchestrator(self.repository)

    def tearDown(self):
        self.folder.cleanup()

    def battle(self, spec=None, seed=3):
        battle = Battle(self.player, self.repository, self.orchestrator, None, spec or WILD_BY_NAME["DIVOWL"],
                        random.Random(seed))
        battle.enemy_hp = battle.enemy_max_hp = 999
        return battle

    def force_puzzle(self, battle, wanted=None):
        battle.PUZZLE_CHANCE = 1.0
        for _ in range(200):
            battle._start_question()
            if battle.is_puzzle and (wanted is None or battle.question.format == wanted):
                return battle.question
        self.fail(f"no {wanted} puzzle served")

    def test_puzzles_keep_the_chosen_skill_and_never_repeat_a_format_twice(self):
        battle = self.battle()
        battle.PUZZLE_CHANCE = 1.0
        last = None
        for _ in range(60):
            battle._start_question()
            if battle.is_puzzle:
                self.assertIn(battle.question.topic, ("addition", "subtraction", "multiplication", "division"))
                if last is not None and battle.question.topic in ("addition", "multiplication"):
                    self.assertNotEqual(battle.question.format, last)
                last = battle.question.format

    def test_target_number_needs_the_given_numbers(self):
        battle = self.battle()
        question = self.force_puzzle(battle, "target")
        hp = battle.enemy_hp
        for ch in question.answer:          # just typing the target is not allowed
            battle.handle_event(typed(ch))
        battle.handle_event(ENTER)
        self.assertEqual(battle.wrong_count, 0)  # doesn't cost a try
        self.assertIn("once each", battle.feedback)
        solution = question.explanation.split(": ", 1)[1].split(" = ")[0]
        for ch in solution.replace(" ", "").replace("×", "x").replace("−", "-"):
            battle.handle_event(typed(ch))
        battle.handle_event(ENTER)
        self.assertLess(battle.enemy_hp, hp)
        self.assertIn("Correct", battle.feedback)

    def test_every_quick_format_can_be_answered_and_drawn(self):
        surface = pygame.Surface((320, 240))
        for fmt in ("sequence", "balance", "magic"):
            battle = self.battle(seed=11)
            question = self.force_puzzle(battle, fmt)
            battle.draw(surface, 1)
            hp = battle.enemy_hp
            for ch in question.answer:
                battle.handle_event(typed(ch))
            battle.handle_event(ENTER)
            self.assertLess(battle.enemy_hp, hp, fmt)

    def test_puzzles_hit_harder_and_get_a_longer_critical_window(self):
        battle = self.battle()
        question = self.force_puzzle(battle, "magic")
        plain_window = Battle.CRITICAL_SECONDS[question.difficulty] * 60
        self.assertEqual(battle.critical_window(), plain_window * 2)
        self.assertGreater(question.base_damage, {"easy": 6, "intermediate": 9, "advanced": 13}[question.difficulty])

    def test_out_of_tries_on_a_puzzle_still_walks_through_it(self):
        battle = self.battle()
        question = self.force_puzzle(battle, "balance")
        for _ in range(3):
            for ch in "9999":
                battle.handle_event(typed(ch))
            battle.handle_event(ENTER)
        self.assertEqual(battle.state, "walkthrough")
        self.assertIn(question.answer, battle.walkthrough["steps"][-1])

    def test_skills_and_the_boss_stay_plain_questions(self):
        battle = self.battle()
        battle.PUZZLE_CHANCE = 1.0
        for _ in range(20):
            battle._start_question("multiplication", 1.35)
            self.assertFalse(battle.is_puzzle)
        boss = self.battle(BOSS)
        boss.PUZZLE_CHANCE = 1.0
        for _ in range(8):
            boss._start_question()
            self.assertFalse(boss.is_puzzle)

    def test_new_topics_and_their_visuals_draw_in_battle(self):
        surface = pygame.Surface((320, 240))
        battle = self.battle()
        for topic in ("fractions", "place_value", "shapes", "time_money"):
            for _ in range(6):
                battle._start_question(topic)
                battle.draw(surface, 2)
            self.assertEqual(battle.question.topic, topic)


if __name__ == "__main__":
    unittest.main()

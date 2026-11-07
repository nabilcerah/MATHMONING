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
from game.creatures import ENEMIES, EVOLUTIONS, STARTERS
from game.game_manager import GameManager
from game.player import Player


def key(code, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=code, unicode=unicode, mod=0)


class BattlePolishTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repository = PlayerRepository(Database(self.folder.name + "/polish.sqlite3"))
        player_id = self.repository.create_player("Tester", "TERRABIT", 42)
        self.player = Player("Tester", "TERRABIT", 1, 42, 42, 0, 4, 6, player_id)
        self.orchestrator = AgentOrchestrator(self.repository)

    def tearDown(self):
        self.folder.cleanup()

    def battle(self):
        return Battle(self.player, self.repository, self.orchestrator, None, ENEMIES[0], random.Random(3))

    def test_every_skill_maps_to_a_topic(self):
        for spec in list(STARTERS.values()) + list(EVOLUTIONS.values()):
            for skill in spec.skills:
                self.assertIn(skill, Battle.TOPIC_FOR_SKILL, skill)
        self.assertEqual(Battle.TOPIC_FOR_SKILL["Multiplication Boulder"], "multiplication")

    def test_large_exp_gain_grants_every_level(self):
        self.assertTrue(self.player.add_exp(20 + 40 + 5))
        self.assertEqual(self.player.level, 3)
        self.assertEqual(self.player.exp, 5)

    def test_learning_crystal_is_kept_when_nothing_to_explain(self):
        battle = self.battle()
        battle._use_item("Learning Crystal")
        self.assertEqual(self.repository.inventory(self.player.player_id)["Learning Crystal"], 2)

    def test_enemy_counterattack_waits_and_can_be_skipped(self):
        battle = self.battle()
        battle._start_question("addition")
        battle.answer = battle.question.answer
        hp_before = self.player.hp
        battle._submit()
        self.assertEqual(battle.state, "resolving")
        self.assertEqual(self.player.hp, hp_before)
        battle.handle_event(key(pygame.K_RETURN))
        battle.update()
        self.assertEqual(battle.state, "menu")
        self.assertLess(self.player.hp, hp_before)

    def test_victory_reports_booster_exp(self):
        battle = self.battle()
        battle._use_item("EXP Booster")
        battle.enemy_hp = 1
        battle._start_question("addition")
        battle.answer = battle.question.answer
        battle._submit()
        self.assertEqual(battle.outcome, "won")
        self.assertIn("+18 EXP", battle.feedback)


class ComboTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repository = PlayerRepository(Database(self.folder.name + "/combo.sqlite3"))
        player_id = self.repository.create_player("Combo", "PYROX", 34)
        self.player = Player("Combo", "PYROX", 1, 34, 34, 0, 4, 6, player_id)
        self.battle = Battle(self.player, self.repository, AgentOrchestrator(self.repository), None,
                             ENEMIES[3], random.Random(2))  # the boss has enough HP for a long streak
        self.battle.enemy_hp = self.battle.enemy_max_hp = 999

    def tearDown(self):
        self.folder.cleanup()

    def answer(self, correct=True, frames=0):
        battle = self.battle
        battle._start_question("addition")
        battle.question_frames = frames
        battle.answer = battle.question.answer if correct else "-999"
        before = battle.enemy_hp
        battle._submit()
        battle.state = "menu"  # skip the enemy's turn
        return before - battle.enemy_hp

    def base_damage(self):
        question = self.battle.question
        return question.base_damage + self.player.level + self.battle.player_spec.attack // 2

    def test_streak_raises_damage_and_caps(self):
        first = self.answer()
        self.assertEqual(first, max(4, round(self.base_damage())))
        for _ in range(8):
            self.answer()
        self.assertEqual(self.battle.combo, 9)
        self.assertAlmostEqual(self.battle.combo_multiplier, 1.5)
        self.assertIn("Combo x1.5", self.battle.feedback)

    def test_a_miss_only_cools_the_combo_by_one(self):
        for _ in range(3):
            self.answer()
        self.answer(correct=False)
        self.assertEqual(self.battle.combo, 2)
        self.assertIn("cools", self.battle.feedback)
        self.assertEqual(self.battle.best_combo, 3)

    def test_quick_first_try_is_critical_but_slow_is_never_penalised(self):
        slow = self.answer(frames=60 * 60)
        self.assertEqual(slow, max(4, round(self.base_damage())))
        self.battle.combo = 0
        quick = self.answer(frames=30)
        self.assertEqual(quick, max(4, round(self.base_damage() * 1.5)))
        self.assertIn("CRITICAL", self.battle.feedback)
        # A retry after a mistake can still win the turn, just not as a critical.
        self.battle.combo = 0
        battle = self.battle
        battle._start_question("addition")
        battle.question_frames = 30
        battle.answer = "-999"
        battle._submit()
        battle.answer = battle.question.answer
        battle._submit()
        self.assertNotIn("CRITICAL", battle.feedback)

    def test_combo_draws(self):
        pygame.init()
        surface = pygame.Surface((320, 240))
        for _ in range(5):
            self.answer(frames=10)
        self.battle._start_question("addition")
        for frame in range(30):
            self.battle.update()
            self.battle.draw(surface, frame)


class BossGateTests(unittest.TestCase):
    def test_any_three_ready_skills_open_the_arch(self):
        from ai.game_master import GameMasterAgent
        ready = {"attempted": 8, "mastery": 88}
        profile = {"division": ready, "subtraction": ready, "addition": {"attempted": 3, "mastery": 38},
                   "multiplication": {"attempted": 3, "mastery": 25}}
        master = GameMasterAgent()
        self.assertFalse(master.boss_ready(profile, 6))
        self.assertIn("Addition: 3/4 questions tried", master.boss_progress(profile, 6))
        profile["addition"] = {"attempted": 4, "mastery": 50}
        self.assertTrue(master.boss_ready(profile, 6))
        self.assertFalse(master.boss_ready(profile, 2))

    def test_unpractised_topics_are_offered_more_often(self):
        from mathematics.question_generator import QuestionGenerator
        generator = QuestionGenerator(random.Random(5))
        profile = {"division": {"attempted": 16, "accuracy": 0.88}, "subtraction": {"attempted": 8, "accuracy": 0.88},
                   "addition": {"attempted": 3, "accuracy": 1.0}, "multiplication": {"attempted": 3, "accuracy": 0.67}}
        picks = [generator.choose_topic(profile) for _ in range(400)]
        needed = picks.count("addition") + picks.count("multiplication")
        self.assertGreater(needed, 300)


class MenuPolishTests(unittest.TestCase):
    def test_new_game_asks_before_replacing_a_save(self):
        with tempfile.TemporaryDirectory() as folder:
            game = GameManager(database_path=folder + "/menu.sqlite3")
            try:
                game.player_name = "First"
                game._create_new_player()
                game.state, game.saved_record, game.menu_selected = "menu", game.repository.load_player(), 0
                game._handle_event(key(pygame.K_RETURN))
                self.assertEqual(game.state, "confirm_new")
                game._handle_event(key(pygame.K_n))
                self.assertEqual(game.state, "menu")
                self.assertEqual(game.repository.load_player().name, "First")
                for state in ("menu", "confirm_new", "profile", "settings"):
                    game.state = state
                    game._draw()
                    game._present()
            finally:
                game.llm.close()
                pygame.quit()


if __name__ == "__main__":
    unittest.main()

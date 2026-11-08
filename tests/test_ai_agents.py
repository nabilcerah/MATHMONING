import random
import unittest

import pygame
from unittest.mock import patch
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from ai.difficulty_manager import DifficultyManager
from ai.llm_provider import LLMProvider
from ai.orchestrator import AgentOrchestrator
from ai.tutor_agent import TutorAgent
from database.database import Database
from database.player_repository import PlayerRepository
from game.battle import Battle
from game.creatures import ENEMIES
from game.player import Player
from mathematics.question_generator import QuestionGenerator


class AgentWorkflowTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.repository = PlayerRepository(Database(self.temp.name + "/test.sqlite3"))
        self.player_id = self.repository.create_player("Ada", "PYROX", 34)
        self.orchestrator = AgentOrchestrator(self.repository, QuestionGenerator(random.Random(3)))

    def tearDown(self):
        self.temp.cleanup()

    def test_repeated_algebra_mistakes_route_to_easier_practice(self):
        question = self.orchestrator.next_question(self.player_id, "algebra", "intermediate")["question"]
        self.assertEqual(question.topic, "algebra")
        for _ in range(3):
            decision = self.orchestrator.submit_answer(self.player_id, question, "999")
            self.assertFalse(decision.correct)
        profile = self.repository.get_learning_profile(self.player_id)
        self.assertEqual(profile["algebra"]["attempted"], 3)
        self.assertIn("isolating variables", profile["algebra"]["common_mistake"])
        follow_up = self.orchestrator.next_question(self.player_id, "algebra", "intermediate")["question"]
        self.assertEqual(follow_up.difficulty, "easy")
        recovery = self.orchestrator.submit_answer(self.player_id, follow_up, follow_up.answer)
        self.assertTrue(recovery.correct)
        self.assertGreater(recovery.exp_reward, 0)
        self.assertTrue(recovery.recommendation)

    def test_regular_adaptive_question_uses_topic_history(self):
        question = self.orchestrator.next_question(self.player_id, "addition", "intermediate")["question"]
        for _ in range(3):
            self.orchestrator.submit_answer(self.player_id, question, "999")
        follow_up = self.orchestrator.next_question(self.player_id, fallback="intermediate")["question"]
        self.assertEqual(follow_up.topic, "addition")
        self.assertEqual(follow_up.difficulty, "easy")

    def test_battle_solves_a_repeated_miss_together(self):
        seed_question = self.orchestrator.next_question(
            self.player_id, "algebra", "intermediate"
        )["question"]
        for _ in range(3):
            self.repository.record_attempt(self.player_id, seed_question, "999", False)
        player = Player("Ada", "PYROX", 1, 34, 34, 0, 4, 6, self.player_id)
        battle = Battle(player, self.repository, self.orchestrator, None, ENEMIES[0], random.Random(1))
        battle._start_question("algebra")
        first_prompt = battle.question.prompt
        self.assertEqual(battle.question.difficulty, "easy")
        for _ in range(3):
            battle.answer = "999"
            battle._submit()
        # Out of tries: the mentor walks through *this* question instead of swapping it away.
        self.assertEqual(battle.state, "walkthrough")
        walk = battle.walkthrough
        self.assertEqual(walk["question"].prompt, first_prompt)
        self.assertIn(walk["question"].answer, walk["steps"][-1])
        enter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0)
        while not walk["typing"]:
            battle.handle_event(enter)
        hp = battle.enemy_hp
        for ch in walk["question"].answer:
            battle.handle_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=ch, mod=0))
        battle.handle_event(enter)
        self.assertIsNone(battle.walkthrough)
        self.assertEqual(battle.wrong_count, 0)
        self.assertLess(battle.enemy_hp, hp)  # a gentle "teamwork" hit

    def test_single_correct_answer_does_not_raise_difficulty(self):
        choice = DifficultyManager().choose({
            "last_difficulty": "easy", "attempted": 1, "accuracy": 1,
            "recent_accuracy": 1, "mastery": 100,
        })
        self.assertEqual(choice.level, "easy")

    def test_tutor_mentor_gives_a_similar_example_before_the_answer(self):
        question = self.orchestrator.next_question(self.player_id, "algebra")["question"]
        response = TutorAgent().mentor(question)
        self.assertIn("similar example", response)
        self.assertIn("Undo operations", response)

    def test_optional_mentor_falls_back_without_an_api_key(self):
        question = self.orchestrator.next_question(self.player_id, "addition")["question"]
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            provider = LLMProvider()
            try:
                self.assertFalse(provider.available)
                future = provider.explain_async(question, "", "Offline hint is ready.")
                self.assertEqual(future.result(timeout=2), "Offline hint is ready.")
            finally:
                provider.close()

    def test_ai_walkthrough_steps_are_checked_against_the_verified_answer(self):
        from types import SimpleNamespace
        from mathematics.solution_steps import steps_for
        question = self.orchestrator.next_question(self.player_id, "addition")["question"]
        offline = steps_for(question)

        def fake_client(reply):
            message = SimpleNamespace(content=[SimpleNamespace(type="text", text=reply)])
            return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: message))

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            provider = LLMProvider()
        try:
            good = f"Split into tens and ones.\nAdd the parts.\nSo the answer is {question.answer}."
            with patch("anthropic.Anthropic", return_value=fake_client(good)):
                steps = provider.solve_async(question, offline).result(timeout=5)
            self.assertEqual(len(steps), 3)
            self.assertIn(question.answer, steps[-1])
            wrong = "Add them up.\nSo the answer is -12345."
            with patch("anthropic.Anthropic", return_value=fake_client(wrong)):
                self.assertEqual(provider.solve_async(question, offline).result(timeout=5), offline)
        finally:
            provider.close()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            offline_provider = LLMProvider()
        try:
            self.assertEqual(offline_provider.solve_async(question, offline).result(timeout=2), offline)
        finally:
            offline_provider.close()


if __name__ == "__main__":
    unittest.main()

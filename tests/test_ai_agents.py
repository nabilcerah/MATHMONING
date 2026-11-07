import random
import unittest
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

    def test_battle_replaces_repeated_miss_with_same_topic_question(self):
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
        self.assertEqual(battle.question.topic, "algebra")
        self.assertEqual(battle.question.difficulty, "easy")
        self.assertNotEqual(battle.question.prompt, first_prompt)
        self.assertEqual(battle.wrong_count, 0)

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


if __name__ == "__main__":
    unittest.main()

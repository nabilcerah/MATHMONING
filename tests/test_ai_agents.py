"""GDD 14-17 and 28 (AI): agent inputs/outputs, orchestrator routing, learning analysis, difficulty,
tutor behaviour and fallbacks, invalid-response handling, offline mode, and the required
'player struggles with algebra' workflow (GDD 30)."""
import random
import tempfile
import unittest
from unittest.mock import patch

from ai.difficulty_manager import DifficultyManager
from ai.game_master import GameMaster
from ai.llm_provider import LLMProvider
from ai.offline_provider import OfflineProvider
from ai.orchestrator import AgentOrchestrator
from ai.schemas import (AnalysisResult, QuestRecommendation, SchemaError, TutorResponse, validate_analysis,
                        validate_question, validate_recommendation, validate_tutor)
from database.database import Database
from database.player_repository import PlayerRepository
from mathematics.question_generator import TemplateQuestionGenerator
from monsters.monster_data import quests
from world.quest_manager import QuestManager


def analysis(topic="algebra", status="developing", evidence=8, mastery=50, recent=0.6, hints=0.0, weakness=""):
    return AnalysisResult(topic, status, evidence, mastery, recent, hints, weakness)


class Base(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repository = PlayerRepository(Database(self.folder.name + "/ai.sqlite3"))
        self.player_id = self.repository.create_player("Ada", "CHRONOX")
        self.orchestrator = AgentOrchestrator(self.repository, rng=random.Random(3))
        self.orchestrator.quest_manager = QuestManager(self.repository, self.player_id)

    def tearDown(self):
        self.folder.cleanup()

    def answer(self, question, outcome, attempts=None, used_hint=False):
        return self.orchestrator.handle({
            "type": "answer_resolved", "player_id": self.player_id, "question": question, "outcome": outcome,
            "attempts": attempts or [question.answer], "attempts_used": len(attempts or [1]),
            "used_hint": used_hint})


class AlgebraStruggleWorkflowTests(Base):
    """GDD 30: the required, demonstrable Agentic AI workflow."""

    def test_struggle_is_detected_remediated_and_followed_by_a_quest_recommendation(self):
        # 1. A player repeatedly struggles with algebra (the same misconception each time).
        for _ in range(6):
            question = self.orchestrator.request_question(self.player_id, "algebra").question
            wrong = next(iter(question.misconceptions), "0")
            self.answer(question, "failed", [wrong, wrong])
        # 2. The Learning Analyst identifies the problem, with evidence.
        analysis_ = self.orchestrator.analyst.analyse(self.player_id, "algebra")
        self.assertEqual(analysis_.status, "weakness")
        self.assertGreaterEqual(analysis_.evidence_count, 5)
        self.assertTrue(analysis_.identified_weakness)
        self.assertEqual(analysis_.recommendation, "guided_linear_equations")
        # 3-5. The Orchestrator calls the Difficulty Manager and the Question Generator; the Tutor
        #      prepares a contextual hint because the learner is struggling.
        decision = self.orchestrator.request_question(self.player_id, "algebra")
        self.assertEqual(decision.agents[:3], ["learning_analyst", "difficulty_manager", "question_generator"])
        self.assertIn("tutor", decision.agents)
        self.assertEqual(decision.difficulty.level, "foundation")
        self.assertEqual(decision.question.topic, "algebra")
        self.assertTrue(decision.tutor.text)
        self.assertFalse(decision.question.answer in decision.tutor.text.split())
        self.assertTrue(decision.trace[0].startswith("1. Received event"))
        self.assertTrue(any(step.startswith("9. Recorded decision") for step in decision.trace))
        # 6. The player improves.
        before = self.repository.learning_profile(self.player_id)["algebra"]["mastery"]
        for _ in range(10):
            question = self.orchestrator.request_question(self.player_id, "algebra").question
            result = self.answer(question, "first_try")
        # 7. The Learning Analyst updates the mastery profile.
        after = self.repository.learning_profile(self.player_id)["algebra"]
        self.assertGreater(after["mastery"], before)
        self.assertNotEqual(self.orchestrator.analyst.analyse(self.player_id, "algebra").status, "weakness")
        # 8. The Game Master recommends an appropriate next quest (an existing one, about algebra).
        recommendation = self.orchestrator.recommendations(self.player_id).recommendation
        self.assertIsNotNone(recommendation)
        self.assertIn(recommendation.quest_id, quests())
        self.assertIn("algebra", quests()[recommendation.quest_id]["topics"])
        # Every decision was recorded with its trace.
        logged = self.repository.recent_decisions(self.player_id, 50)
        self.assertTrue(any(row["event"] == "answer_resolved" for row in logged))
        self.assertTrue(self.repository.recommendations(self.player_id))
        del result

    def test_player_history_changes_later_questions(self):
        first = self.orchestrator.request_question(self.player_id, "fractions")
        for _ in range(12):
            question = self.orchestrator.request_question(self.player_id, "fractions").question
            self.answer(question, "first_try")
        later = self.orchestrator.request_question(self.player_id, "fractions")
        self.assertEqual(first.difficulty.level, "foundation")
        self.assertNotEqual(later.difficulty.level, "foundation")


class AnalystTests(Base):
    def test_insufficient_evidence_is_not_called_a_weakness(self):
        question = self.orchestrator.request_question(self.player_id, "geometry").question
        self.answer(question, "failed", ["1", "2"])
        result = self.orchestrator.analyst.analyse(self.player_id, "geometry")
        self.assertEqual(result.status, "insufficient_evidence")
        self.assertEqual(result.recommendation, "")

    def test_overview_lists_strongest_and_developing(self):
        for outcome, topic in (("first_try", "addition"), ("failed", "division")):
            for _ in range(6):
                question = self.orchestrator.request_question(self.player_id, topic).question
                self.answer(question, outcome, None if outcome == "first_try" else ["0", "0"])
        overview = self.orchestrator.analyst.overview(self.player_id)
        self.assertIn("addition", overview["strongest"])
        self.assertIn("division", overview["developing"])


class DifficultyTests(unittest.TestCase):
    def test_bands_follow_the_gdd_table(self):
        manager = DifficultyManager()
        for mastery, level in ((10, "foundation"), (45, "intermediate"), (75, "advanced"), (90, "mastery")):
            self.assertEqual(manager.recommend(analysis(status="strong", mastery=mastery, recent=0.9)).level, level)

    def test_safeguards(self):
        manager = DifficultyManager()
        self.assertEqual(manager.recommend(analysis(status="insufficient_evidence", evidence=2, mastery=95)).level,
                         "intermediate")
        self.assertEqual(manager.recommend(analysis(status="developing", mastery=75, recent=0.3)).level, "intermediate")
        self.assertEqual(manager.recommend(analysis(status="developing", mastery=75, recent=0.9, hints=0.9)).level,
                         "intermediate")
        jump = manager.recommend(analysis(status="mastered", mastery=95, recent=1.0, evidence=20), previous="foundation")
        self.assertEqual(jump.level, "intermediate")   # one band at a time


class TutorTests(Base):
    def test_hints_progress_without_revealing_the_answer(self):
        question = TemplateQuestionGenerator(random.Random(9)).generate("fractions", "intermediate")
        first = self.orchestrator.tutor.hint(question, 0)
        second = self.orchestrator.tutor.hint(question, 1)
        self.assertNotEqual(first.text, second.text)
        for response in (first, second):
            validate_tutor(response, question)

    def test_feedback_names_the_misconception(self):
        question = TemplateQuestionGenerator(random.Random(2)).generate("fractions", "intermediate")
        wrong, tag = next(iter(question.misconceptions.items()))
        self.assertEqual(tag, "added_denominators")
        feedback = self.orchestrator.handle({"type": "wrong_attempt", "player_id": self.player_id,
                                             "question": question, "submitted": wrong})
        self.assertIn("denominator", feedback.message)
        self.assertNotIn(question.answer, feedback.message.split())

    def test_worked_example_uses_different_numbers(self):
        question = TemplateQuestionGenerator(random.Random(4)).generate("algebra", "intermediate")
        decision = self.orchestrator.handle({"type": "worked_example", "player_id": self.player_id,
                                             "question": question})
        self.assertNotIn(question.prompt, decision.message)
        self.assertTrue(decision.message.startswith("Here's one like it"))


class ValidationTests(unittest.TestCase):
    def test_invalid_agent_responses_are_rejected(self):
        with self.assertRaises(SchemaError):
            validate_analysis(AnalysisResult("algebra", "confused", 1, 150, 0.5, 0.0))
        with self.assertRaises(SchemaError):
            validate_tutor(TutorResponse("hint", "You are stupid."))
        with self.assertRaises(SchemaError):
            validate_tutor(TutorResponse("hint", "x" * 1000))
        with self.assertRaises(SchemaError):
            validate_recommendation(QuestRecommendation("make_me_rich", "?", "Do it"), quests())
        question = TemplateQuestionGenerator(random.Random(1)).generate("addition", "foundation")
        with self.assertRaises(SchemaError):
            validate_tutor(TutorResponse("hint", f"The answer is {question.answer}."), question)

    def test_a_question_with_a_wrong_answer_never_validates(self):
        from dataclasses import replace
        question = TemplateQuestionGenerator(random.Random(1)).generate("multiplication", "intermediate")
        self.assertIs(validate_question(question), question)
        with self.assertRaises(SchemaError):
            validate_question(replace(question, answer=str(int(question.answer) + 1), misconceptions={}))


class OfflineAndProviderTests(Base):
    def test_offline_mode_without_credentials(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "MATHMON_AI_MODE": "hybrid"}):
            with patch("dotenv.load_dotenv"):
                provider = LLMProvider()
        self.assertFalse(provider.available)
        self.assertEqual(provider.label, "OFFLINE AI")
        question = TemplateQuestionGenerator(random.Random(1)).generate("addition", "foundation")
        self.assertEqual(provider.explain_async(question, "1", "fallback").result(), "fallback")
        self.assertEqual(OfflineProvider().explain_async(question, "1", "fallback").result(), "fallback")

    def test_api_failure_falls_back_to_offline_text(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-not-real", "MATHMON_AI_MODE": "live"}):
            with patch("dotenv.load_dotenv"):
                provider = LLMProvider()
        question = TemplateQuestionGenerator(random.Random(1)).generate("addition", "foundation")
        with patch.object(LLMProvider, "_client", side_effect=RuntimeError("network down")):
            self.assertEqual(provider._request(question, "1", "offline explanation"), "offline explanation")
            self.assertEqual(provider._solve(question, ["step"]), ["step"])
        provider.close()

    def test_unknown_events_are_refused(self):
        with self.assertRaises(ValueError):
            self.orchestrator.handle({"type": "award_exp", "player_id": self.player_id, "amount": 9999})

    def test_ai_never_touches_game_mechanics(self):
        party_before = [(m.hp, m.exp, m.level) for m in self.repository.load_party(self.player_id).party]
        bag_before = self.repository.inventory(self.player_id)
        coins_before = self.repository.coins(self.player_id)
        for _ in range(5):
            question = self.orchestrator.request_question(self.player_id, "addition").question
            self.answer(question, "first_try")
        self.orchestrator.recommendations(self.player_id)
        self.assertEqual([(m.hp, m.exp, m.level) for m in self.repository.load_party(self.player_id).party], party_before)
        self.assertEqual(self.repository.inventory(self.player_id), bag_before)
        self.assertEqual(self.repository.coins(self.player_id), coins_before)


class GameMasterTests(unittest.TestCase):
    def test_recommends_only_existing_quests_for_the_weak_topic(self):
        master = GameMaster()
        weak = [analysis("fractions", "weakness", 8, 30), analysis("addition", "strong", 10, 90)]
        recommendation = master.recommend_quest(weak, list(quests()), [])
        self.assertIn(recommendation.quest_id, ("crystal_seal", "fading_numera"))
        self.assertIn("fractions", quests()[recommendation.quest_id]["topics"])

    def test_boss_readiness_is_advice(self):
        master = GameMaster()
        self.assertFalse(master.boss_readiness([], 10, seals_done=False)[0])
        self.assertTrue(master.boss_readiness([analysis(status="strong", mastery=80)], 10, seals_done=True)[0])


if __name__ == "__main__":
    unittest.main()

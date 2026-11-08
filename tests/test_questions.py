"""GDD 18 / 28: question generation - every topic and band, verified answers, structure, no repeats."""
import random
import unittest

from mathematics import curriculum
from mathematics.question_generator import TemplateQuestionGenerator, VerificationError, verify_draft


class QuestionTests(unittest.TestCase):
    def test_every_topic_and_band_produces_verified_questions(self):
        generator = TemplateQuestionGenerator(random.Random(11))
        for topic in curriculum.MASTERY_TOPICS:
            for difficulty in curriculum.DIFFICULTIES:
                for _ in range(40):
                    q = generator.generate(topic, difficulty)
                    self.assertEqual((q.topic, q.difficulty), (topic, difficulty))
                    self.assertTrue(q.verified(), q.prompt)
                    self.assertTrue(q.check(q.answer).correct, q.prompt)
                    for wrong in q.misconceptions:
                        self.assertFalse(q.check(wrong).correct, (q.prompt, wrong))
                    self.assertEqual(len(q.hints), 3)
                    self.assertTrue(q.explanation)

    def test_structured_object_has_the_gdd_fields(self):
        q = TemplateQuestionGenerator(random.Random(2)).generate("algebra", "intermediate", affinity="CHRONOX")
        data = q.to_dict()
        for key in ("question_id", "topic", "subtopic", "difficulty", "question", "answer_type", "correct_answer",
                    "hint", "explanation", "affinity", "source"):
            self.assertIn(key, data)
        self.assertEqual(data["affinity"], "CHRONOX")
        self.assertEqual(data["source"], "template")

    def test_hints_never_contain_the_answer_alone(self):
        from ai.schemas import reveals
        generator = TemplateQuestionGenerator(random.Random(5))
        for topic in curriculum.MASTERY_TOPICS:
            for _ in range(30):
                q = generator.generate(topic, "intermediate")
                if not reveals(q.prompt, q.answer):
                    self.assertFalse(any(reveals(hint, q.answer) for hint in q.hints), (q.prompt, q.hints))

    def test_recent_prompts_are_not_repeated(self):
        generator = TemplateQuestionGenerator(random.Random(7))
        prompts = [generator.generate("multiplication", "advanced").prompt for _ in range(12)]
        self.assertEqual(len(set(prompts)), len(prompts))

    def test_unverifiable_drafts_are_rejected(self):
        self.assertFalse(verify_draft({"answer": "5", "expression": "2+2"}))
        self.assertFalse(verify_draft({"answer": "5"}))                         # no proof at all
        self.assertFalse(verify_draft({"answer": "4", "equation": ("2*x+1", "11")}))
        self.assertTrue(verify_draft({"answer": "5", "equation": ("2*x+1", "11")}))
        self.assertTrue(VerificationError)

    def test_quest_contexts(self):
        generator = TemplateQuestionGenerator(random.Random(1))
        self.assertIn("bridge", generator.generate("geometry", "foundation", "bridge_area").prompt)
        self.assertIn("planks", generator.generate("multiplication", "foundation", "bridge_bundles").prompt)

    def test_topic_mapping(self):
        self.assertEqual(curriculum.mastery_topic("equations"), "algebra")
        self.assertEqual(curriculum.mastery_topic("negative_numbers"), "integers")
        self.assertEqual(curriculum.mastery_topic("percentages"), "ratios")
        self.assertEqual(curriculum.normalise_difficulty("easy"), "foundation")


if __name__ == "__main__":
    unittest.main()

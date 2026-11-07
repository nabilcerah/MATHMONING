import random
import re
import unittest

from mathematics.answer_validator import AnswerValidator
from mathematics.question_generator import QuestionGenerator


class QuestionGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.generator = QuestionGenerator(random.Random(11))

    def test_generated_arithmetic_answer_is_correct(self):
        for topic in self.generator.TOPICS:
            question = self.generator.generate("intermediate", topic)
            self.assertEqual(question.topic, topic)
            numbers = [int(value) for value in re.findall(r"\d+", question.prompt)]
            if topic == "addition":
                expected = numbers[0] + numbers[1]
            elif topic == "subtraction":
                expected = numbers[0] - numbers[1]
            elif topic == "multiplication":
                expected = numbers[0] * numbers[1]
            else:
                expected = numbers[0] // numbers[1]
            self.assertTrue(AnswerValidator.check(str(expected), question.answer))
            self.assertTrue(question.explanation)
            self.assertTrue(question.hint)

    def test_algebra_extension_checks_isolating_variables(self):
        question = self.generator.generate("easy", "algebra")
        self.assertIn("Solve for x", question.prompt)
        self.assertEqual(question.concept, "isolating variables")
        coefficient, offset, total = [int(value) for value in re.findall(r"\d+", question.prompt)]
        self.assertTrue(AnswerValidator.check(str((total - offset) // coefficient), question.answer))

    def test_recent_prompts_do_not_repeat(self):
        questions = [self.generator.generate("easy") for _ in range(10)]
        self.assertEqual(len({question.prompt for question in questions}), len(questions))


if __name__ == "__main__":
    unittest.main()

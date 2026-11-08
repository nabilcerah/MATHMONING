import random
import re
import unittest

from mathematics.answer_validator import AnswerValidator
from mathematics.question_generator import QuestionGenerator


class QuestionGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.generator = QuestionGenerator(random.Random(11))

    def test_generated_arithmetic_answer_is_correct(self):
        for topic in self.generator.CORE_TOPICS:
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

    def test_new_topics_have_valid_answers_and_walkthroughs(self):
        from mathematics.solution_steps import steps_for
        for topic in ("fractions", "place_value", "shapes", "time_money"):
            for difficulty in ("easy", "intermediate", "advanced"):
                for _ in range(80):
                    question = self.generator.generate(difficulty, topic)
                    self.assertEqual(question.topic, topic)
                    self.assertTrue(AnswerValidator.check(question.answer, question.answer), question.prompt)
                    steps = steps_for(question)
                    self.assertGreaterEqual(len(steps), 2)
                    last = steps[-1].replace(",", "")
                    self.assertTrue(question.answer in last or question.answer.replace(".00", "") in last,
                                    (question.prompt, question.answer, last))

    def test_new_topic_answers_are_right(self):
        rng_questions = [self.generator.generate("easy", "shapes") for _ in range(30)]
        for question in rng_questions:
            w, h = (int(v) for v in re.findall(r"\d+", question.prompt)[:2])
            expected = w * h if "area" in question.prompt else 2 * (w + h)
            self.assertEqual(int(question.answer), expected)
        self.assertTrue(AnswerValidator.check("4/6", "2/3"))      # equivalent fractions are accepted
        self.assertTrue(AnswerValidator.check("3.25", "3.25"))    # money answers with cents
        for _ in range(30):
            question = self.generator.generate("advanced", "fractions")
            if question.prompt.startswith("Which is bigger"):
                a, b = re.findall(r"\d+/\d+", question.prompt)
                from fractions import Fraction
                self.assertEqual(Fraction(question.answer), max(Fraction(a), Fraction(b)))

    def test_recent_prompts_do_not_repeat(self):
        questions = [self.generator.generate("easy") for _ in range(10)]
        self.assertEqual(len({question.prompt for question in questions}), len(questions))


if __name__ == "__main__":
    unittest.main()

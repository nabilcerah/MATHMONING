"""The advanced question engine: every topic, every level, verified answers and plausible options."""
import random
import unittest
from fractions import Fraction

from mathematics.question_engine import GENERATORS, QuestionEngine, parse_number, topic_label, verify_draft
from mathematics.question_engine.safe_eval import left_to_right, safe_eval

REQUIRED_TOPICS = ("addition", "subtraction", "multiplication", "division", "negative_numbers", "fractions",
                   "percentages", "geometry", "algebra", "equations", "sequences", "exponents", "mixed_operations",
                   "logic")


class GeneratorTests(unittest.TestCase):
    def test_every_required_topic_exists(self):
        for topic in REQUIRED_TOPICS:
            self.assertIn(topic, GENERATORS)

    def test_every_draft_is_mathematically_verified(self):
        for topic, generate in GENERATORS.items():
            for level in range(1, 6):
                for seed in range(120):
                    draft = generate(random.Random(seed * 31 + level), level)
                    self.assertTrue(verify_draft(draft), (topic, level, draft.prompt, draft.answer))

    def test_questions_have_one_right_option_and_plausible_wrong_ones(self):
        engine = QuestionEngine(random.Random(5), "TEST")
        for topic in GENERATORS:
            for level in range(1, 6):
                for _ in range(8):
                    q = engine.generate(topic, level)
                    self.assertTrue(q.check(q.answer))
                    self.assertEqual(sum(1 for c in q.choices if q.check(c)), 1, (q.prompt, q.choices))
                    self.assertGreaterEqual(len(q.choices), 2 if q.kind == "choice" else 4)
                    self.assertTrue(q.question_id and q.explanation and q.prompt)
                    if q.kind == "number" and parse_number(q.answer).denominator == 1:
                        # whole-number answers never sit among fractional options (that would give it away)
                        self.assertTrue(all(parse_number(c).denominator == 1 for c in q.choices), q.choices)

    def test_no_repeats_inside_one_battle(self):
        engine = QuestionEngine(random.Random(2), "TEST")
        prompts = [engine.generate("multiplication", 3).prompt for _ in range(40)]
        self.assertEqual(len(prompts), len(set(prompts)))

    def test_difficulty_grows_with_level(self):
        engine = QuestionEngine(random.Random(8))
        easy = [abs(parse_number(engine.generate("addition", 1).answer)) for _ in range(20)]
        hard = [abs(parse_number(engine.generate("addition", 5).answer)) for _ in range(20)]
        self.assertGreater(min(hard), max(easy))

    def test_question_metadata(self):
        q = QuestionEngine(random.Random(1), "CRYSTALGON").generate("angles", 2, weakness=True)
        self.assertEqual(q.monster, "CRYSTALGON")
        self.assertTrue(q.weakness)
        self.assertEqual(q.topic, "angles")
        self.assertIn(q.difficulty, ("easy", "intermediate", "advanced"))  # works with the learning profile
        self.assertEqual(topic_label("mixed_operations"), "Order of Operations")


class CheckingTests(unittest.TestCase):
    def test_equivalent_forms_are_accepted_exactly(self):
        q = QuestionEngine(random.Random(3)).generate("fractions", 4)
        value = parse_number(q.answer)
        self.assertTrue(q.check(f"{value.numerator * 3}/{value.denominator * 3}"))
        self.assertTrue(q.check(str(float(value)) if len(str(float(value))) < 8 else q.answer))
        self.assertFalse(q.check(str(value + 1)))
        self.assertEqual(parse_number("1 1/2"), Fraction(3, 2))
        self.assertEqual(parse_number("-3/4"), Fraction(-3, 4))
        self.assertEqual(parse_number("1,200"), 1200)
        self.assertEqual(parse_number("30%"), 30)

    def test_player_input_is_never_evaluated(self):
        q = QuestionEngine(random.Random(3)).generate("addition", 1)
        for attack in ("__import__('os')", "2+2", "1e9", "", "nan"):
            self.assertFalse(q.check(attack) and attack != q.answer)
        self.assertIsNone(parse_number("__import__('os')"))

    def test_safe_eval_and_left_to_right(self):
        self.assertEqual(safe_eval("3+4*2"), 11)
        self.assertEqual(left_to_right("3+4*2"), 14)
        self.assertEqual(safe_eval("2**(-2)"), Fraction(1, 4))
        with self.assertRaises(ValueError):
            safe_eval("__import__('os')")


if __name__ == "__main__":
    unittest.main()

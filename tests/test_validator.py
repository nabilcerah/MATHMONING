"""GDD 19 / 28 MATHEMATICS: the answer validator (never eval)."""
import unittest
from unittest.mock import patch

from mathematics.answer_validator import ExpressionError, parse_expression, validate


def ok(submitted, expected, kind="number", **kwargs):
    return validate(submitted, expected, kind, **kwargs).correct


class ValidatorTests(unittest.TestCase):
    def test_integers(self):
        self.assertTrue(ok("12", "12", "integer"))
        self.assertTrue(ok("-7", "-7", "integer"))
        self.assertTrue(ok("−7", "-7", "integer"))           # typographic minus
        self.assertFalse(ok("13", "12", "integer"))
        result = validate("24/2", "12", "integer")
        self.assertFalse(result.correct)
        self.assertIn("whole number", result.reason)

    def test_decimals(self):
        self.assertTrue(ok("0.5", "0.5", "decimal"))
        self.assertTrue(ok(".5", "0.5", "decimal"))
        self.assertTrue(ok("1/2", "0.5", "decimal"))
        self.assertTrue(ok("3.14", "3.14159", "decimal", decimals=2))
        self.assertFalse(ok("3.1", "3.14159", "decimal", decimals=2))

    def test_fractions_and_equivalence(self):
        self.assertTrue(ok("5/6", "5/6", "fraction"))
        self.assertTrue(ok("10/12", "5/6", "fraction"))
        self.assertTrue(ok("0.5", "1/2", "fraction"))
        self.assertTrue(ok("1 1/2", "3/2", "fraction"))
        self.assertTrue(ok("3/2", "3/2", "simplified_fraction"))
        not_simplified = validate("10/12", "5/6", "simplified_fraction")
        self.assertFalse(not_simplified.correct)
        self.assertIn("simplest", not_simplified.reason)
        self.assertFalse(ok("0.5", "1/2", "simplified_fraction"))

    def test_algebra(self):
        self.assertTrue(ok("5", "5", "equation"))
        self.assertTrue(ok("x = 5", "5", "equation"))
        self.assertTrue(ok("2x+2", "2(x+1)", "expression"))
        self.assertTrue(ok("x^2 + 2x + 1", "(x+1)(x+1)", "expression"))
        self.assertFalse(ok("2x+1", "2(x+1)", "expression"))
        self.assertTrue(ok("5x+4", "5x+4", "simplified_expression"))
        self.assertFalse(ok("2x+3x+4", "5x+4", "simplified_expression"))

    def test_time(self):
        self.assertTrue(ok("12:20", "12:20", "time"))
        self.assertTrue(ok("12.20", "12:20", "time"))
        self.assertFalse(ok("12:30", "12:20", "time"))

    def test_invalid_input_is_unreadable_not_wrong(self):
        for junk in ("", "abc", "__import__('os')", "1/0", "x" * 100, "2**1000", "()"):
            result = validate(junk, "4", "integer")
            self.assertFalse(result.correct, junk)
        self.assertFalse(validate("hello", "4", "integer").readable)
        self.assertFalse(validate("", "4", "integer").readable)

    def test_player_input_never_reaches_eval(self):
        with patch("builtins.eval", side_effect=AssertionError("eval used")):
            self.assertTrue(ok("2(x+1)", "2x+2", "expression"))
            self.assertTrue(ok("3/4", "0.75", "decimal"))
            validate("__import__('os').system('x')", "1", "expression")

    def test_expression_parser_is_restricted(self):
        for bad in ("import os", "x.__class__", "lambda: 1", "x^99", "q[0]"):
            with self.assertRaises(ExpressionError, msg=bad):
                parse_expression(bad)


if __name__ == "__main__":
    unittest.main()

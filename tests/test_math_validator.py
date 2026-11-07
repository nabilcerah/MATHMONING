import unittest

from mathematics.answer_validator import AnswerValidator


class AnswerValidatorTests(unittest.TestCase):
    def test_exact_integer_and_decimal_answers(self):
        self.assertTrue(AnswerValidator.check(" 0.5 ", "1/2"))
        self.assertTrue(AnswerValidator.check("3 + 4", "7"))
        self.assertTrue(AnswerValidator.check("2**3", "8"))
        self.assertFalse(AnswerValidator.check("1/3", "0.33"))

    def test_untrusted_python_is_not_executed(self):
        self.assertFalse(AnswerValidator.check("__import__('os').system('echo unsafe')", "1"))
        self.assertFalse(AnswerValidator.check("x + 1", "2"))

    def test_division_by_zero_is_rejected(self):
        self.assertFalse(AnswerValidator.check("1/0", "0"))


if __name__ == "__main__":
    unittest.main()

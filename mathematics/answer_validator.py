"""Safe numeric answer checking; arbitrary Python expressions are never evaluated."""
import ast
from fractions import Fraction


class AnswerValidator:
    @staticmethod
    def _number(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return Fraction(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = AnswerValidator._number(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            left, right = AnswerValidator._number(node.left), AnswerValidator._number(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            if isinstance(node.op, ast.Div): return left / right
            if right.denominator != 1 or abs(right.numerator) > 8: raise ValueError("Unsupported exponent")
            return left ** right.numerator
        raise ValueError("Only numeric arithmetic is allowed")

    @classmethod
    def parse_numeric(cls, value):
        text = str(value).strip().replace(",", "")
        if not text or len(text) > 80:
            raise ValueError("Empty or long answer")
        tree = ast.parse(text, mode="eval")
        result = cls._number(tree.body)
        # SymPy is available in the full install and provides a second exact check.
        try:
            import sympy
            exact = sympy.Rational(result.numerator, result.denominator)
            return exact
        except ImportError:
            return result

    @classmethod
    def check(cls, submitted, expected):
        try:
            return cls.parse_numeric(submitted) == cls.parse_numeric(expected)
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
            return False

"""GDD 19: safe answer checking. Player input is NEVER passed to eval() or to sympy.parse_expr
(which uses eval internally). Numbers go through a regex parser; algebra goes through the small
recursive-descent parser below, which builds SymPy objects directly.

    validate("10/12", "5/6", "fraction")            -> correct (equivalent fraction)
    validate("10/12", "5/6", "simplified_fraction") -> not correct: "write it in simplest form"
    validate("2x+2", "2(x+1)", "expression")        -> correct
"""
import ast
import re
from dataclasses import dataclass
from fractions import Fraction

import sympy

ANSWER_TYPES = ("integer", "number", "fraction", "simplified_fraction", "decimal", "expression",
                "simplified_expression", "equation", "time", "choice")

_NUMBER = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)$")
_FRACTION = re.compile(r"^([+-]?\d+)\s*/\s*([+-]?\d+)$")
_MIXED = re.compile(r"^([+-]?\d+)\s+(\d+)\s*/\s*(\d+)$")
_TIME = re.compile(r"^(\d{1,2})\s*[:.h]\s*(\d{2})$")
MAX_LENGTH = 40


@dataclass(frozen=True)
class ValidationResult:
    correct: bool
    readable: bool          # False = we could not read the input (it should not cost an attempt)
    reason: str = ""


def clean(text):
    text = str(text if text is not None else "").strip()
    for bad, good in (("−", "-"), ("–", "-"), ("×", "*"), ("÷", "/"), (",", ""), ("²", "^2"), ("³", "^3")):
        text = text.replace(bad, good)
    return text


def parse_number(text):
    """'-3', '0.75', '3/4', '1 1/2' -> Fraction, or None. No expressions."""
    text = clean(text)
    if not text or len(text) > MAX_LENGTH:
        return None
    if _NUMBER.match(text):
        return Fraction(text)
    match = _FRACTION.match(text)
    if match:
        denominator = int(match.group(2))
        return Fraction(int(match.group(1)), denominator) if denominator else None
    match = _MIXED.match(text)
    if match:
        whole, numerator, denominator = (int(g) for g in match.groups())
        if not denominator:
            return None
        part = Fraction(numerator, denominator)
        return whole - part if text.startswith("-") else whole + part
    return None


def parse_time(text):
    """'12:20' / '12.20' / '12h20' -> minutes after midnight, or None."""
    match = _TIME.match(clean(text))
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return hours * 60 + minutes


# ---------------------------------------------------------------------------- algebra parser
class ExpressionError(ValueError):
    pass


_TOKEN = re.compile(r"\s*(?:(\d+\.\d+|\d+)|([a-z])|(\*\*|[-+*/^()]))", re.IGNORECASE)
ALLOWED_VARIABLES = frozenset("abcmnpqrstxyz")


def _tokens(text):
    tokens, pos = [], 0
    text = text.strip()
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if not match or match.end() == pos:
            raise ExpressionError(f"unexpected character {text[pos]!r}")
        number, name, op = match.groups()
        if number:
            tokens.append(("num", number))
        elif name:
            if name.lower() not in ALLOWED_VARIABLES:
                raise ExpressionError(f"unknown letter {name!r}")
            tokens.append(("var", name.lower()))
        else:
            tokens.append(("op", "^" if op == "**" else op))
        pos = match.end()
    # Implicit multiplication: 2x, 3(x+1), x(x+1), (x+1)(x-1), )2
    result = []
    for token in tokens:
        if result:
            prev = result[-1]
            ends_value = prev[0] in ("num", "var") or prev == ("op", ")")
            starts_value = token[0] in ("num", "var") or token == ("op", "(")
            if ends_value and starts_value and not (prev[0] == "num" and token[0] == "num"):
                result.append(("op", "*"))
        result.append(token)
    return result


class _Parser:
    def __init__(self, tokens):
        self.tokens, self.pos = tokens, 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def take(self, value=None):
        token = self.peek()
        if token[0] is None or (value is not None and token[1] != value):
            raise ExpressionError("incomplete expression")
        self.pos += 1
        return token

    def parse(self):
        value = self.expr()
        if self.pos != len(self.tokens):
            raise ExpressionError("unexpected input")
        return value

    def expr(self):
        value = self.term()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            right = self.term()
            value = value + right if op == "+" else value - right
        return value

    def term(self):
        value = self.unary()
        while self.peek()[1] in ("*", "/"):
            op = self.take()[1]
            right = self.unary()
            if op == "/" and right == 0:
                raise ExpressionError("division by zero")
            value = value * right if op == "*" else value / right
        return value

    def unary(self):
        if self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            value = self.unary()
            return -value if op == "-" else value
        return self.power()

    def power(self):
        base = self.atom()
        if self.peek()[1] == "^":
            self.take()
            exponent = self.unary()
            if not (exponent.is_Integer and abs(int(exponent)) <= 6):
                raise ExpressionError("only small whole-number powers are allowed")
            return base ** exponent
        return base

    def atom(self):
        kind, value = self.peek()
        if kind == "num":
            self.take()
            return sympy.Rational(value)
        if kind == "var":
            self.take()
            return sympy.Symbol(value)
        if value == "(":
            self.take("(")
            inner = self.expr()
            self.take(")")
            return inner
        raise ExpressionError("expected a number, a letter or a bracket")


def parse_expression(text):
    """Text -> SymPy expression, built without eval. Raises ExpressionError."""
    text = clean(text)
    if not text or len(text) > MAX_LENGTH:
        raise ExpressionError("empty or too long")
    return _Parser(_tokens(text)).parse()


def _equivalent(a, b):
    return sympy.simplify(sympy.expand(a - b)) == 0


# ---------------------------------------------------------------------------- validation
def validate(submitted, expected, answer_type="number", decimals=None):
    """Check ``submitted`` against the verified ``expected`` answer in the requested form."""
    text = clean(submitted)
    if not text:
        return ValidationResult(False, False, "Type an answer first.")
    if answer_type == "choice":
        same = re.sub(r"\s+", " ", text.lower()) == re.sub(r"\s+", " ", clean(expected).lower())
        return ValidationResult(same, True)
    if answer_type == "time":
        got, want = parse_time(text), parse_time(expected)
        if got is None:
            return ValidationResult(False, False, "Write the time like 12:20.")
        return ValidationResult(got == want, True)
    if answer_type in ("expression", "simplified_expression"):
        return _validate_expression(text, expected, answer_type)
    if answer_type == "equation":
        text = re.sub(r"^\s*[a-z]\s*=\s*", "", text, flags=re.IGNORECASE)  # "x = 5" -> "5"
    value = parse_number(text)
    if value is None:
        try:
            value = Fraction(str(sympy.nsimplify(parse_expression(text))))
            if not value.denominator:
                raise ValueError
        except (ExpressionError, ValueError, TypeError, ZeroDivisionError):
            return ValidationResult(False, False, "I couldn't read that. Try a number like 7, -3, 3/4 or 0.75.")
        computed = True
    else:
        computed = False
    target = parse_number(expected)
    if target is None:
        return ValidationResult(False, True, "")
    if answer_type == "decimal" and decimals is not None:
        same = round(float(value), decimals) == round(float(target), decimals)
        return ValidationResult(same, True, "" if same else f"Round to {decimals} decimal places.")
    if value != target:
        return ValidationResult(False, True)
    # Equal value: now check the requested representation.
    if answer_type == "integer" and (computed or not re.match(r"^[+-]?\d+$", text)):
        return ValidationResult(False, True, "Right value! Now write it as a whole number.")
    if answer_type == "simplified_fraction":
        match = _FRACTION.match(text)
        whole = bool(re.match(r"^[+-]?\d+$", text))
        if computed or not (match or whole):
            return ValidationResult(False, True, "Right value! Now write it as a fraction like 5/6.")
        if match and (_gcd(int(match.group(1)), int(match.group(2))) != 1 or abs(int(match.group(2))) == 1):
            return ValidationResult(False, True, "Right value! Now write it in simplest form.")
    if computed and answer_type != "number":
        return ValidationResult(False, True, "Right value! Now write just the final number.")
    return ValidationResult(True, True)


def _gcd(a, b):
    from math import gcd
    return gcd(abs(a), abs(b))


def _term_count(text):
    """Numbers and letters as typed ("2x+3x+4" has 5, "5x+4" has 3)."""
    return sum(1 for kind, _ in _tokens(clean(text)) if kind in ("num", "var"))


def _validate_expression(text, expected, answer_type):
    try:
        got = parse_expression(text)
    except ExpressionError:
        return ValidationResult(False, False, "I couldn't read that expression. Try something like 3x + 2.")
    want = parse_expression(expected)
    if not _equivalent(got, want):
        return ValidationResult(False, True)
    if answer_type == "simplified_expression" and _term_count(text) > _term_count(expected):
        # SymPy combines like terms by itself, so compare what the learner actually typed.
        return ValidationResult(False, True, "Right idea! Now collect like terms to simplify it.")
    return ValidationResult(True, True)


class AnswerValidator:
    """Backwards-compatible numeric checker used by the Arena, Trials and older screens."""

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
        tree = ast.parse(text, mode="eval")   # parsed to a syntax tree only; never evaluated
        result = cls._number(tree.body)
        return sympy.Rational(result.numerator, result.denominator)

    @classmethod
    def check(cls, submitted, expected):
        try:
            return cls.parse_numeric(submitted) == cls.parse_numeric(expected)
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
            return False

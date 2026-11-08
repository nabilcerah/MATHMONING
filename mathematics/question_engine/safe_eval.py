"""Exact evaluation of generated arithmetic (used to double-check every generated answer).

Only numbers, + - * / ** and brackets are accepted, computed with Fractions. This module checks the
*generator's own* expressions; player input is parsed separately by ``model.parse_number``.
"""
import ast
from fractions import Fraction


def safe_eval(expression):
    tree = ast.parse(str(expression).replace("×", "*").replace("÷", "/").replace("−", "-"), mode="eval")
    return _value(tree.body)


def _value(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _value(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left, right = _value(node.left), _value(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            if right.denominator != 1 or abs(right.numerator) > 12:
                raise ValueError("unsupported exponent")
            return left ** right.numerator
    raise ValueError(f"unsupported expression: {ast.dump(node)[:40]}")


def left_to_right(expression):
    """The classic order-of-operations mistake: work strictly left to right (used for distractors)."""
    expression = expression.replace(" ", "")
    if "**" in expression:
        return None  # powers have no single "left to right" reading
    tokens, number = [], ""
    for char in expression:
        if char.isdigit():
            number += char
        else:
            if number:
                tokens.append(Fraction(int(number)))
                number = ""
            if char in "+-*/":
                tokens.append(char)
            else:
                return None  # brackets or powers: no single "left to right" reading
    if number:
        tokens.append(Fraction(int(number)))
    if not tokens or not isinstance(tokens[0], Fraction):
        return None
    total = tokens[0]
    for op, value in zip(tokens[1::2], tokens[2::2]):
        if op == "+":
            total += value
        elif op == "-":
            total -= value
        elif op == "*":
            total *= value
        elif value:
            total /= value
        else:
            return None
    return total

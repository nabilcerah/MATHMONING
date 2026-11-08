"""Algebra (expressions and substitution) and equations (finding the unknown).

Equation answers are verified by substituting the solution back into both sides.
"""
from fractions import Fraction

from mathematics.question_engine.generators import Draft
from mathematics.question_engine.safe_eval import safe_eval


def _holds(lhs, rhs, x):
    """True when the equation lhs = rhs is satisfied by x (checked exactly)."""
    return safe_eval(lhs.replace("x", f"({x})")) == safe_eval(rhs.replace("x", f"({x})"))


def algebra(rng, level):
    if level <= 1:
        x, k = rng.randint(2, 12), rng.randint(2, 15)
        answer = x + k
        return Draft(f"If x = {x}, what is x + {k}?", answer, [x * k, k - x, answer + 1],
                     f"Replace x with {x}: {x} + {k} = {answer}.", "Swap the letter for its number.", f"{x}+{k}")
    if level == 2:
        x, a = rng.randint(2, 10), rng.randint(2, 9)
        answer = a * x
        return Draft(f"If n = {x}, what is {a}n?", answer, [int(f"{a}{x}"), a + x, answer + a],
                     f"{a}n means {a} × n = {a} × {x} = {answer}.", "A number next to a letter means multiply.", f"{a}*{x}")
    if level == 3:
        x, a, b = rng.randint(2, 9), rng.randint(2, 7), rng.randint(1, 15)
        answer = a * x + b
        return Draft(f"If x = {x}, what is {a}x + {b}?", answer, [a * (x + b), a + x + b, int(f"{a}{x}") + b],
                     f"Multiply first: {a} × {x} = {a * x}. Then add {b}: {answer}.", "Multiply before adding.",
                     f"{a}*{x}+{b}")
    if level == 4:
        x, a, b = rng.randint(-6, 9), rng.randint(2, 6), rng.randint(2, 9)
        answer = a * x * x - b
        shown = f"({x})" if x < 0 else str(x)
        return Draft(f"If x = {x}, what is {a}x² − {b}?", answer, [(a * x) ** 2 - b, a * 2 * x - b, a * x * x + b],
                     f"Square first: {shown}² = {x * x}. Then × {a} = {a * x * x}, then − {b} = {answer}.",
                     "Powers come before multiplying.", f"{a}*({x})**2-{b}")
    x, y = rng.randint(1, 8), rng.randint(-5, 6)
    a, b, c = rng.randint(2, 5), rng.randint(2, 5), rng.randint(1, 9)
    answer = a * x - b * y + c
    return Draft(f"If x = {x} and y = {y}, what is {a}x − {b}y + {c}?", answer, [a * x + b * y + c, a * x - b * y - c, answer + b],
                 f"{a} × {x} = {a * x}; {b} × ({y}) = {b * y}. So {a * x} − ({b * y}) + {c} = {answer}.",
                 "Substitute carefully - keep brackets around negative values.", f"{a}*{x}-{b}*({y})+{c}")


def equations(rng, level):
    if level <= 1:
        x, k = rng.randint(1, 20), rng.randint(2, 20)
        lhs, rhs = f"x+{k}", str(x + k)
        return Draft(f"? + {k} = {x + k}", Fraction(x), [x + 2 * k, k, x + 1],
                     f"Undo + {k} by taking {k} away: {x + k} − {k} = {x}.", "Use the inverse operation.",
                     verify=lambda: _holds(lhs, rhs, x))
    if level == 2:
        x, a = rng.randint(2, 12), rng.randint(2, 9)
        lhs, rhs = f"{a}*x", str(a * x)
        return Draft(f"Solve for x: {a}x = {a * x}", Fraction(x), [a * x - a, a * a * x, x + a],
                     f"Divide both sides by {a}: x = {a * x} ÷ {a} = {x}.", "Undo the multiplication by dividing.",
                     verify=lambda: _holds(lhs, rhs, x))
    if level == 3:
        x, a, b = rng.randint(2, 12), rng.randint(2, 7), rng.randint(1, 20)
        total = a * x + b
        lhs, rhs = f"{a}*x+{b}", str(total)
        return Draft(f"Solve for x: {a}x + {b} = {total}", Fraction(x), [Fraction(total + b, a), Fraction(total - b), Fraction(total, a)],
                     f"Subtract {b} from both sides: {a}x = {total - b}. Divide by {a}: x = {x}.",
                     "Undo the + first, then the ×.", verify=lambda: _holds(lhs, rhs, x))
    if level == 4:
        x = rng.randint(-6, 12)
        a, c = rng.randint(4, 9), rng.randint(1, 3)
        b = rng.randint(-10, 10)
        d = (a - c) * x + b
        lhs, rhs = f"{a}*x+({b})", f"{c}*x+({d})"
        b_text = f"+ {b}" if b >= 0 else f"− {-b}"
        d_text = f"+ {d}" if d >= 0 else f"− {-d}"
        c_text = "x" if c == 1 else f"{c}x"
        return Draft(f"Solve: {a}x {b_text} = {c_text} {d_text}", Fraction(x),
                     [Fraction(d - b, a + c), Fraction(d + b, a - c), Fraction(-x)],
                     f"Collect x on one side: {a - c}x = {d} − ({b}) = {d - b}. So x = {d - b} ÷ {a - c} = {x}.",
                     "Move the x terms together first, then the numbers.", verify=lambda: _holds(lhs, rhs, x))
    x = rng.randint(-5, 12)
    a, k = rng.randint(2, 5), rng.randint(1, 6)
    c = a + rng.randint(1, 3)
    total = a * (x + k)
    d = c * x - total  # a(x + k) = cx - d  ->  d = cx - a(x + k)
    lhs, rhs = f"{a}*(x+{k})", f"{c}*x-({d})"
    d_text = f"− {d}" if d >= 0 else f"+ {-d}"
    return Draft(f"Solve: {a}(x + {k}) = {c}x {d_text}", Fraction(x),
                 [Fraction(-x), Fraction(a * k + d, c - a) + 1, Fraction(k + d, c - a)],
                 f"Expand: {a}x + {a * k} = {c}x {d_text}. Collect: {a * k} + ({d}) = {c - a}x, so x = {x}.",
                 "Expand the bracket, then collect like terms.", verify=lambda: _holds(lhs, rhs, x))

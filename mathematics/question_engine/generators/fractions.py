"""Fractions and percentages."""
from fractions import Fraction
from math import gcd

from mathematics.question_engine.generators import Draft
from mathematics.question_engine.model import fmt


def _proper(rng, denominators):
    d = rng.choice(denominators)
    return Fraction(rng.randint(1, d - 1), d)


def fractions(rng, level):
    if level <= 1:
        d = rng.choice([4, 5, 6, 8, 10])
        a, b = rng.randint(1, d - 2), 1
        b = rng.randint(1, d - a - 1) if d - a - 1 >= 1 else 1
        answer = Fraction(a + b, d)
        return Draft(f"{a}/{d} + {b}/{d} = ?", answer, [Fraction(a + b, 2 * d), Fraction(a * b, d), Fraction(a + b + 1, d)],
                     f"Same denominator: add the tops and keep the bottom. {a + b}/{d}" +
                     (f" = {fmt(answer)} in simplest form." if answer.denominator != d else "."),
                     "When the bottoms match, only the tops change.", f"{a}/{d}+{b}/{d}")
    if level == 2:
        d = rng.choice([2, 3, 4, 5, 10])
        n = rng.randint(1, d - 1)
        whole = d * rng.randint(2, 12)
        answer = Fraction(n * whole, d)
        return Draft(f"What is {n}/{d} of {whole}?", answer, [whole // d, whole * n, whole - answer],
                     f"Find 1/{d} first: {whole} ÷ {d} = {whole // d}. Then take {n} of those: {fmt(answer)}.",
                     "Divide by the bottom, multiply by the top.", f"{n}/{d}*{whole}")
    if level == 3:
        a, b = _proper(rng, [2, 3, 4, 5, 6]), _proper(rng, [2, 3, 4, 6, 8])
        op = rng.choice("+-")
        if op == "-" and a < b:
            a, b = b, a
        if a == b:
            b = Fraction(1, b.denominator * 2)
        answer = a + b if op == "+" else a - b
        wrong = Fraction(a.numerator + (b.numerator if op == "+" else -b.numerator), a.denominator + b.denominator)
        common = a.denominator * b.denominator // gcd(a.denominator, b.denominator)
        sign = "+" if op == "+" else "−"
        return Draft(f"{fmt(a)} {sign} {fmt(b)} = ?", answer, [wrong, a * b, answer + Fraction(1, common)],
                     f"Use a common denominator of {common}: {fmt(a)} = {a.numerator * (common // a.denominator)}/{common}, "
                     f"{fmt(b)} = {b.numerator * (common // b.denominator)}/{common}. So the answer is {fmt(answer)}.",
                     "Never add the bottoms! Make them the same first.", f"{a.numerator}/{a.denominator}{op}{b.numerator}/{b.denominator}")
    if level == 4:
        a, b = _proper(rng, [2, 3, 4, 5]), _proper(rng, [3, 4, 5, 6])
        answer = a * b
        return Draft(f"{fmt(a)} × {fmt(b)} = ?", answer, [Fraction(a.numerator * b.numerator, a.denominator + b.denominator),
                                                          a + b, a / b],
                     f"Multiply the tops ({a.numerator} × {b.numerator}) and the bottoms ({a.denominator} × {b.denominator}), "
                     f"then simplify: {fmt(answer)}.", "Top times top, bottom times bottom.",
                     f"{a.numerator}/{a.denominator}*{b.numerator}/{b.denominator}")
    a, b = _proper(rng, [2, 3, 4, 5, 6]), _proper(rng, [2, 3, 4, 5])
    answer = a / b
    return Draft(f"{fmt(a)} ÷ {fmt(b)} = ?", answer, [a * b, b / a, Fraction(a.numerator * b.numerator, a.denominator * b.denominator) + 1],
                 f"Dividing by {fmt(b)} is multiplying by its reciprocal {b.denominator}/{b.numerator}: "
                 f"{fmt(a)} × {b.denominator}/{b.numerator} = {fmt(answer)}.",
                 "Keep, change, flip: keep the first, change ÷ to ×, flip the second.",
                 f"{a.numerator}/{a.denominator}/({b.numerator}/{b.denominator})")


def percentages(rng, level):
    if level <= 1:
        p = rng.choice([10, 50])
        n = rng.randint(2, 20) * 10
        answer = Fraction(p * n, 100)
        return Draft(f"What is {p}% of {n}?", answer, [n - answer, p, answer * 2 if p == 10 else answer // 5],
                     f"{p}% means {p} out of 100" + (f": half of {n} is {fmt(answer)}." if p == 50 else
                                                     f": one tenth of {n} is {fmt(answer)}."),
                     "10% is one tenth; 50% is one half.", f"{p}/100*{n}")
    if level == 2:
        p = rng.choice([20, 25, 75])
        n = rng.randint(2, 12) * 20
        answer = Fraction(p * n, 100)
        return Draft(f"What is {p}% of {n}?", answer, [n - answer, Fraction(n, p // 5), answer + 10],
                     f"{p}% = {fmt(Fraction(p, 100))}. {fmt(Fraction(p, 100))} of {n} = {fmt(answer)}.",
                     "Turn the percentage into a simple fraction first.", f"{p}/100*{n}")
    if level == 3:
        p = rng.choice([5, 15, 30, 35, 40, 45, 60, 65, 70, 85])
        n = rng.randint(2, 15) * 20
        answer = Fraction(p * n, 100)
        return Draft(f"What is {p}% of {n}?", answer, [Fraction(p * n, 10), n - answer, answer + Fraction(n, 20)],
                     f"Find 10% ({fmt(Fraction(n, 10))}) and 5% ({fmt(Fraction(n, 20))}), then build {p}%: {fmt(answer)}.",
                     "Build any percentage from 10% and 5% pieces.", f"{p}/100*{n}")
    if level == 4:
        p = rng.choice([10, 20, 25, 50])
        n = rng.randint(2, 20) * 20
        up = rng.random() < 0.5
        answer = Fraction(n * (100 + p if up else 100 - p), 100)
        word = "increased" if up else "decreased"
        return Draft(f"{n} is {word} by {p}%. What is the new amount?", answer,
                     [Fraction(p * n, 100), n + p if up else n - p, Fraction(n * (100 - p if up else 100 + p), 100)],
                     f"{p}% of {n} is {fmt(Fraction(p * n, 100))}. {'Add' if up else 'Take'} it {'to' if up else 'from'} {n}: {fmt(answer)}.",
                     "Find the change first, then add or subtract it.", f"{n}{'+' if up else '-'}{p}/100*{n}")
    old = rng.randint(2, 10) * 20
    p = rng.choice([10, 20, 25, 50, 75])
    new = old + old * p // 100
    answer = Fraction(p)
    return Draft(f"A price rises from {old} to {new}. What is the percentage increase?", answer,
                 [Fraction(new - old), Fraction((new - old) * 100, new), answer + 5],
                 f"Increase = {new - old}. As a percentage of the ORIGINAL {old}: {new - old} ÷ {old} × 100 = {p}%.",
                 "Always divide by the original amount.", f"({new}-{old})/{old}*100")

"""Mixed operations (order of operations), logical reasoning and combined two-concept questions."""
from fractions import Fraction

from mathematics.question_engine.generators import Draft
from mathematics.question_engine.model import fmt
from mathematics.question_engine.safe_eval import left_to_right, safe_eval


def mixed_operations(rng, level):
    if level <= 1:
        a, b, c = rng.randint(2, 12), rng.randint(2, 6), rng.randint(2, 6)
        expression, shown = f"{a}+{b}*{c}", f"{a} + {b} × {c}"
        why = f"Multiply first: {b} × {c} = {b * c}. Then {a} + {b * c}."
    elif level == 2:
        c = rng.randint(2, 6)
        a, b, d = rng.randint(2, 9), rng.randint(2, 9), c * rng.randint(2, 6)
        expression, shown = f"{a}*{b}-{d}/{c}", f"{a} × {b} − {d} ÷ {c}"
        why = f"× and ÷ before −: {a * b} − {d // c}."
    elif level == 3:
        a, b, c, d = rng.randint(2, 9), rng.randint(2, 9), rng.randint(2, 6), rng.randint(1, 15)
        expression, shown = f"({a}+{b})*{c}-{d}", f"({a} + {b}) × {c} − {d}"
        why = f"Brackets first: {a + b}. Then × {c} = {(a + b) * c}. Then − {d}."
    elif level == 4:
        a, b, c = rng.randint(2, 20), rng.randint(2, 5), rng.randint(2, 5)
        expression, shown = f"{a}+{b}*{c}**2", f"{a} + {b} × {c}²"
        why = f"Powers first: {c}² = {c * c}. Then × {b} = {b * c * c}. Then + {a}."
    else:
        a, b, c, d = rng.randint(2, 9), rng.randint(2, 9), rng.randint(2, 5), rng.randint(2, 9)
        expression, shown = f"{a}*({b}-{c}**2)+{d}", f"{a} × ({b} − {c}²) + {d}"
        why = f"Inside the bracket, power first: {b} − {c * c} = {b - c * c}. Then × {a} = {a * (b - c * c)}, then + {d}."
    answer = safe_eval(expression)
    mistakes = [left_to_right(expression)]
    if "(" in expression:
        mistakes.append(safe_eval(expression.replace("(", "").replace(")", "")))
    if "**2" in expression:
        mistakes.append(safe_eval(expression.replace("**2", "*2")))
    mistakes += [answer + 2, answer - 3]
    return Draft(f"{shown} = ?", answer, mistakes, f"{why} Answer: {fmt(answer)}.",
                 "BIDMAS: Brackets, Indices (powers), ÷ and ×, then + and −.", expression, tags=("order_of_operations",))


NAMES = ("Ana", "Ben", "Cyrus", "Dina", "Eli", "Farah", "Gus", "Hana")


def logic(rng, level):
    if level <= 1:
        k = rng.choice([2, 5, 10])
        members = rng.sample([k * i for i in range(1, 11)], 3)
        odd = rng.choice([n for n in range(3, 50) if n % k and n not in members])
        options = [str(n) for n in members + [odd]]
        rng.shuffle(options)
        return Draft(f"Odd one out: {', '.join(options)}", str(odd), kind="choice", options=options,
                     explanation=f"All the others are multiples of {k}; {odd} is not.",
                     hint="What do most of them have in common?", tags=("patterns",))
    if level == 2:
        people = rng.sample(NAMES, 3)
        tall = people[:]
        rng.shuffle(people)
        answer = tall[2]
        return Draft(f"{tall[0]} is taller than {tall[1]}. {tall[1]} is taller than {tall[2]}. Who is shortest?", answer,
                     kind="choice", options=people,
                     explanation=f"The order is {tall[0]} > {tall[1]} > {tall[2]}, so {answer} is shortest.",
                     hint="Line them up from tallest to shortest.", tags=("ordering",))
    if level == 3:
        triangle = rng.randint(2, 12)
        circle = rng.randint(1, 15)
        return Draft(f"▲ + ▲ = {2 * triangle} and ▲ + ● = {triangle + circle}. What is ●?", Fraction(circle),
                     [triangle + circle, 2 * triangle, triangle],
                     f"▲ + ▲ = {2 * triangle}, so ▲ = {triangle}. Then ● = {triangle + circle} − {triangle} = {circle}.",
                     "Solve the first clue to unlock the second.", f"{triangle + circle}-{2 * triangle}/2", tags=("symbols",))
    if level == 4:
        while True:
            low = rng.randint(10, 60)
            high = low + 20
            k = rng.choice([3, 4, 6, 7])
            parity = rng.choice(["even", "odd"])
            digit_sum = rng.randint(4, 14)
            fits = [n for n in range(low + 1, high) if n % k == 0 and (n % 2 == 0) == (parity == "even")
                    and sum(map(int, str(n))) == digit_sum]
            if len(fits) == 1:
                break
        answer = fits[0]
        candidates = [n for n in range(low + 1, high) if n % k == 0 and n != answer]
        return Draft(f"I am between {low} and {high}. I am a multiple of {k}, I am {parity}, and my digits add to "
                     f"{digit_sum}. What number am I?", Fraction(answer), candidates[:2] + [answer + k],
                     f"Multiples of {k} in range that are {parity}: check digit sums. Only {answer} fits.",
                     "List the multiples first, then test each clue.", verify=lambda: len(fits) == 1, tags=("deduction",))
    values = {"0.5": Fraction(1, 2), "2/5": Fraction(2, 5), "45%": Fraction(45, 100), "3/8": Fraction(3, 8),
              "0.6": Fraction(3, 5), "55%": Fraction(55, 100), "4/7": Fraction(4, 7), "0.52": Fraction(52, 100)}
    while True:
        names = rng.sample(sorted(values), 4)
        biggest = max(names, key=values.get)
        if sorted(values[n] for n in names)[-2] != values[biggest]:
            break
    return Draft(f"Which is the greatest: {', '.join(names)}?", biggest, kind="choice", options=names,
                 explanation="Convert each to a percentage: " +
                 ", ".join(f"{n} = {fmt(values[n] * 100) if (values[n] * 100).denominator == 1 else round(float(values[n] * 100), 1)}%"
                           for n in names) + f". The greatest is {biggest}.",
                 hint="Turn them all into the same form (percentages work well).", tags=("comparison",))


def combined(rng, level):
    """Two concepts in one question (Infinity Zero's Paradox and Infinity phases)."""
    kind = rng.randrange(5)
    if kind == 0:
        a, b = rng.randint(2, 6), rng.randint(2, 10) * 2
        answer = a * a + b // 2
        return Draft(f"(−{a})² + ½ of {b} = ?", answer, [-a * a + b // 2, a * 2 + b // 2, a * a + b],
                     f"Negatives and powers: (−{a})² = {a * a} (negative × negative). Fractions: ½ of {b} = {b // 2}. "
                     f"Total {answer}.", "Work out each part, then combine.", f"(-{a})**2+{b}/2",
                     tags=("negative_numbers", "exponents", "fractions"))
    if kind == 1:
        x, a, b = rng.randint(2, 6), rng.randint(2, 5), rng.randint(1, 10)
        answer = x * x
        lhs, rhs = f"{a}*x+{b}", str(a * x + b)
        return Draft(f"{a}x + {b} = {a * x + b}. What is x²?", answer, [x, 2 * x, answer + 1],
                     f"Equations: x = ({a * x + b} − {b}) ÷ {a} = {x}. Exponents: x² = {answer}.",
                     "Find x first, then square it.", f"{x}**2", tags=("equations", "exponents"),
                     verify=lambda: safe_eval(lhs.replace("x", str(x))) == safe_eval(rhs))
    if kind == 2:
        power = rng.randint(3, 6)
        p = rng.choice([25, 50, 75])
        answer = Fraction(p * 2 ** power, 100)
        return Draft(f"What is {p}% of 2^{power}?", answer, [Fraction(p * 2 * power, 100), 2 ** power, answer * 2],
                     f"Exponents: 2^{power} = {2 ** power}. Percentages: {p}% of that = {fmt(answer)}.",
                     "Power first, then the percentage.", f"{p}/100*2**{power}", tags=("percentages", "exponents"))
    if kind == 3:
        start, step = rng.randint(1, 9), rng.randint(3, 8)
        terms = [start + step * i for i in range(4)]
        nxt = start + step * 4
        sub = rng.randint(nxt + 5, nxt + 40)
        answer = nxt - sub
        return Draft(f"Next term of {', '.join(map(str, terms))}, ... minus {sub} = ?", answer, [sub - nxt, terms[-1] - sub, answer + step],
                     f"Sequences: the next term is {nxt}. Negative numbers: {nxt} − {sub} = {answer}.",
                     "Find the pattern, then subtract past zero.", f"{nxt}-{sub}",
                     tags=("sequences", "negative_numbers"))
    a, b = rng.randint(30, 80), rng.randint(30, 80)
    third = 180 - a - b
    k = rng.choice([2, 3, 4])
    answer = Fraction(third, k)
    return Draft(f"A triangle has angles {a}° and {b}°. What is 1/{k} of the third angle?", answer,
                 [Fraction(360 - a - b, k), Fraction(third), Fraction(third * k)],
                 f"Angles: third = 180 − {a} − {b} = {third}°. Fractions: {third} ÷ {k} = {fmt(answer)}°.",
                 "Find the angle, then take the fraction.", f"(180-{a}-{b})/{k}", tags=("angles", "fractions"))

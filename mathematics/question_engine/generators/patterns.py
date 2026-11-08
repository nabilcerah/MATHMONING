"""Number sequences and exponents."""
from fractions import Fraction

from mathematics.question_engine.generators import Draft


def sequences(rng, level):
    if level <= 1:
        start, step = rng.randint(1, 20), rng.randint(2, 6)
        terms = [start + step * i for i in range(4)]
        answer = start + step * 4
        return Draft(f"What comes next? {', '.join(map(str, terms))}, ?", answer, [answer + step, answer - 1, terms[-1] + 1],
                     f"The pattern adds {step} each time: {terms[-1]} + {step} = {answer}.",
                     "Find the gap between neighbours.", f"{start}+{step}*4", visual=("sequence", tuple(terms)))
    if level == 2:
        start, step = rng.randint(30, 90), rng.randint(3, 9)
        terms = [start - step * i for i in range(5)]
        gap = rng.randint(1, 3)
        answer = terms[gap]
        shown = ["?" if i == gap else str(t) for i, t in enumerate(terms)]
        return Draft(f"Find the missing number: {', '.join(shown)}", answer, [answer + step, answer - step, answer + 1],
                     f"Each term is {step} less than the one before, so the gap is {answer}.",
                     "Is it going up or down? By how much?", f"{start}-{step}*{gap}")
    if level == 3:
        start, ratio = rng.randint(1, 5), rng.choice([2, 3])
        terms = [start * ratio ** i for i in range(4)]
        answer = start * ratio ** 4
        return Draft(f"What comes next? {', '.join(map(str, terms))}, ?", answer,
                     [terms[-1] + (terms[-1] - terms[-2]), terms[-1] * 2 if ratio == 3 else terms[-1] * 3, terms[-1] + ratio],
                     f"Each term is multiplied by {ratio}: {terms[-1]} × {ratio} = {answer}.",
                     "If the gaps keep growing, try multiplying.", f"{start}*{ratio}**4", visual=("sequence", tuple(terms)))
    if level == 4:
        kind = rng.choice(["squares", "steps"])
        if kind == "squares":
            offset = rng.randint(1, 4)
            terms = [(offset + i) ** 2 for i in range(4)]
            answer = (offset + 4) ** 2
            return Draft(f"What comes next? {', '.join(map(str, terms))}, ?", answer,
                         [terms[-1] + (terms[-1] - terms[-2]), answer + 1, (offset + 4) * 2],
                         f"These are square numbers: {offset + 4}² = {answer}.",
                         "Look at the gaps between the gaps.", f"({offset}+4)**2", visual=("sequence", tuple(terms)))
        start, first, grow = rng.randint(1, 10), rng.randint(1, 4), rng.randint(1, 3)
        terms, gap = [start], first
        for _ in range(4):
            terms.append(terms[-1] + gap)
            gap += grow
        answer = terms.pop()
        return Draft(f"What comes next? {', '.join(map(str, terms))}, ?", answer,
                     [terms[-1] + (terms[-1] - terms[-2]), answer + grow, answer - 1],
                     f"The gaps grow by {grow} each time, so the next gap is {answer - terms[-1]}: {answer}.",
                     "Write the gaps underneath. Do they make their own pattern?",
                     verify=lambda: answer - terms[-1] == (terms[-1] - terms[-2]) + grow, visual=("sequence", tuple(terms)))
    start, step = rng.randint(1, 12), rng.randint(2, 9)
    n = rng.randint(12, 40)
    answer = start + step * (n - 1)
    terms = [start + step * i for i in range(3)]
    return Draft(f"What is the {n}th term of {', '.join(map(str, terms))}, ...?", answer,
                 [start + step * n, step * n, answer - start],
                 f"The nth term is {start} + {step}(n − 1). For n = {n}: {start} + {step} × {n - 1} = {answer}.",
                 "Term 1 has 0 steps added, term 2 has 1 step... so term n has (n − 1) steps.",
                 f"{start}+{step}*({n}-1)")


def exponents(rng, level):
    if level <= 1:
        base = rng.randint(2, 10)
        return Draft(f"{base}² = ?", base * base, [base * 2, base + 2, base * base + base],
                     f"{base}² means {base} × {base} = {base * base}.", "Squared means times itself, not times 2.",
                     f"{base}**2")
    if level == 2:
        base = rng.randint(2, 6)
        return Draft(f"{base}³ = ?", base ** 3, [base * 3, base ** 2, base ** 3 + base],
                     f"{base}³ = {base} × {base} × {base} = {base ** 3}.", "Cubed means three of them multiplied.",
                     f"{base}**3")
    if level == 3:
        base, power = rng.choice([(2, rng.randint(4, 8)), (3, rng.randint(3, 5)), (10, rng.randint(3, 6)), (5, 3)])
        return Draft(f"{base}^{power} = ?", base ** power, [base * power, base ** (power - 1), base ** power + base],
                     f"Multiply {power} {base}s together: {base ** power}.",
                     "Count the factors: the power tells you how many.", f"{base}**{power}")
    if level == 4:
        base, m, n = rng.choice([2, 3, 5, 10]), rng.randint(2, 5), rng.randint(2, 5)
        if rng.random() < 0.5:
            return Draft(f"{base}^{m} × {base}^{n} = {base}^?", m + n, [m * n, m + n + 1, abs(m - n)],
                         f"Same base, multiplying: add the powers. {m} + {n} = {m + n}.",
                         "Write them out: the number of factors adds up.", f"{m}+{n}", tags=("laws",))
        return Draft(f"({base}^{m})^{n} = {base}^?", m * n, [m + n, m * n + 1, m ** n],
                     f"A power of a power multiplies the powers: {m} × {n} = {m * n}.",
                     "(a^m)^n is a^m written n times.", f"{m}*{n}", tags=("laws",))
    base, power = rng.choice([2, 3, 4, 5, 10]), rng.randint(1, 3)
    if rng.random() < 0.4:
        return Draft(f"{base}^0 = ?", 1, [0, base, -1], f"Any non-zero number to the power 0 is 1.",
                     "Look at the pattern 2³=8, 2²=4, 2¹=2, 2⁰=...", f"{base}**0")
    answer = Fraction(1, base ** power)
    return Draft(f"{base}^−{power} = ?", answer, [Fraction(-base ** power), Fraction(-base * power), Fraction(1, base * power)],
                 f"A negative power means 'one over': {base}^−{power} = 1/{base}^{power} = {answer}.",
                 "Negative powers make reciprocals, not negative numbers.", f"{base}**(-{power})")

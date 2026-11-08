"""Fractions, place value & rounding, shapes (area & perimeter), and time & money.

Each builder takes (rng, difficulty) and returns a dict with prompt, answer, explanation, hint,
concept, worked steps and an optional small visual. Answers are plain numbers, decimals
("3.25") or fractions ("3/4"), which the safe AnswerValidator already understands.
"""
from fractions import Fraction
from math import gcd

LABELS = {"fractions": "FRACTIONS", "place_value": "PLACE VALUE", "shapes": "SHAPES", "time_money": "TIME & MONEY"}


def _q(prompt, answer, steps, hint, concept, visual=()):
    return {"prompt": prompt, "answer": str(answer), "steps": tuple(steps), "hint": hint, "concept": concept,
            "explanation": steps[-1], "visual": visual}


def _frac(f):
    return f"{f.numerator}/{f.denominator}" if f.denominator != 1 else str(f.numerator)


# --------------------------------------------------------------------------- fractions
def fractions(rng, difficulty):
    if difficulty == "easy":
        d = rng.choice([2, 3, 4, 5])
        whole = d * rng.randint(2, 6)
        name = {2: "Half", 3: "A third", 4: "A quarter", 5: "A fifth"}[d]
        return _q(f"{name} of {whole} = ?", whole // d,
                  [f"{name.lower()} means split {whole} into {d} equal parts.",
                   f"{whole} ÷ {d} = {whole // d}.", f"So {name.lower()} of {whole} is {whole // d}."],
                  f"Share {whole} equally into {d} groups.", "fraction of a number")
    if difficulty == "intermediate":
        if rng.random() < 0.5:
            d = rng.choice([3, 4, 5, 6, 8])
            n = rng.randint(2, d - 1)
            whole = d * rng.randint(2, 6)
            part = whole // d
            return _q(f"{n}/{d} of {whole} = ?", part * n,
                      [f"First find 1/{d} of {whole}: {whole} ÷ {d} = {part}.",
                       f"We need {n} of those parts: {part} × {n} = {part * n}.",
                       f"So {n}/{d} of {whole} = {part * n}."],
                      f"Divide by {d}, then multiply by {n}.", "fraction of a number")
        n, d = rng.choice([(1, 2), (1, 3), (2, 3), (1, 4), (3, 4), (2, 5)])
        k = rng.randint(2, 4)
        return _q(f"{n}/{d} = ?/{d * k}", n * k,
                  [f"The bottom number went from {d} to {d * k}: that's × {k}.",
                   f"Do the same to the top: {n} × {k} = {n * k}.",
                   f"So {n}/{d} = {n * k}/{d * k}."],
                  "Whatever you do to the bottom, do to the top.", "equivalent fractions")
    # advanced: compare, or add with a common denominator
    if rng.random() < 0.5:
        while True:
            a = Fraction(rng.randint(1, 5), rng.randint(2, 7))
            b = Fraction(rng.randint(1, 5), rng.randint(2, 7))
            if a != b and a < 1 and b < 1:
                break
        big = max(a, b)
        common = a.denominator * b.denominator // gcd(a.denominator, b.denominator)
        return _q(f"Which is bigger: {_frac(a)} or {_frac(b)}?  Type the bigger one.", _frac(big),
                  [f"Give both the same bottom number, {common}.",
                   f"{_frac(a)} = {a.numerator * common // a.denominator}/{common} and "
                   f"{_frac(b)} = {b.numerator * common // b.denominator}/{common}.",
                   f"More parts of the same size is bigger, so {_frac(big)} is bigger."],
                  "Make the bottom numbers the same, then compare the tops.", "comparing fractions")
    d = rng.choice([5, 7, 8, 9, 10, 12])
    a, b = rng.randint(1, d - 2), 0
    b = rng.randint(1, d - 1 - a)
    total = Fraction(a + b, d)
    return _q(f"{a}/{d} + {b}/{d} = ?", _frac(total),
              [f"The bottoms match, so just add the tops: {a} + {b} = {a + b}.",
               f"Keep the bottom: {a + b}/{d}." + (f" That simplifies to {_frac(total)}." if total.denominator != d else ""),
               f"So {a}/{d} + {b}/{d} = {_frac(total)}."],
              "Same bottom number? Add the top numbers only.", "adding fractions")


# --------------------------------------------------------------------------- place value
def place_value(rng, difficulty):
    if difficulty == "easy":
        if rng.random() < 0.5:
            n = rng.randint(11, 99)
            down = n // 10 * 10
            answer = down + 10 if n % 10 >= 5 else down
            return _q(f"Round {n} to the nearest 10.", answer,
                      [f"{n} is between {down} and {down + 10}.",
                       f"Look at the ones digit: {n % 10}. 5 or more rounds up, less rounds down.",
                       f"So {n} rounds to {answer}."],
                      "Check the ones digit: 5 or more goes up.", "rounding")
        n = rng.randint(21, 99)
        while n // 10 == n % 10:  # 33 would make "the 3" ambiguous
            n = rng.randint(21, 99)
        tens = n // 10
        return _q(f"What is the {tens} worth in {n}?", tens * 10,
                  [f"In {n}, the {tens} is in the tens place.", f"{tens} tens = {tens * 10}.",
                   f"So the {tens} is worth {tens * 10}."],
                  "Which column is it in: ones or tens?", "place value")
    if difficulty == "intermediate":
        if rng.random() < 0.5:
            n = rng.randint(101, 999)
            down = n // 100 * 100
            answer = down + 100 if n % 100 >= 50 else down
            return _q(f"Round {n} to the nearest 100.", answer,
                      [f"{n} is between {down} and {down + 100}.",
                       f"Look at the tens digit: {n // 10 % 10}. 5 or more rounds up.",
                       f"So {n} rounds to {answer}."],
                      "Check the tens digit: 5 or more goes up.", "rounding")
        while True:
            n = rng.randint(1000, 9999)
            digits = str(n)
            # Ask about a non-zero digit that appears only once, so "the 8" is never ambiguous.
            options = [i for i in range(3) if digits[i] != "0" and digits.count(digits[i]) == 1]
            if options:
                position = rng.choice(options)
                break
        place = ("thousands", "hundreds", "tens")[position]
        value = int(digits[position]) * (1000, 100, 10)[position]
        return _q(f"What is the {digits[position]} worth in {n:,}?", value,
                  [f"Name the columns of {n:,}: thousands, hundreds, tens, ones.",
                   f"The {digits[position]} is in the {place} column.",
                   f"So it is worth {value:,}."],
                  "Count the columns from the right: ones, tens, hundreds, thousands.", "place value")
    if rng.random() < 0.5:
        n = rng.randint(1001, 9999)
        down = n // 1000 * 1000
        answer = down + 1000 if n % 1000 >= 500 else down
        return _q(f"Round {n:,} to the nearest 1,000.", answer,
                  [f"{n:,} is between {down:,} and {down + 1000:,}.",
                   f"Look at the hundreds digit: {n // 100 % 10}. 5 or more rounds up.",
                   f"So {n:,} rounds to {answer:,}."],
                  "Check the hundreds digit.", "rounding")
    n = rng.randint(100, 999) * 10
    return _q(f"How many tens are in {n:,}?", n // 10,
              [f"One ten is 10, so divide by 10.", f"{n:,} ÷ 10 = {n // 10}.", f"There are {n // 10} tens in {n:,}."],
              "Each ten is 10: divide by 10.", "place value")


# --------------------------------------------------------------------------- shapes
def shapes(rng, difficulty):
    w, h = (rng.randint(2, 6), rng.randint(2, 5)) if difficulty == "easy" else (rng.randint(3, 12), rng.randint(2, 9))
    if difficulty == "advanced" and rng.random() < 0.5:
        area = w * h
        return _q(f"A rectangle has area {area} and width {w}. How long is it?", h,
                  [f"Area = length × width, so length × {w} = {area}.",
                   f"Undo the × {w}: {area} ÷ {w} = {h}.", f"So the length is {h}."],
                  f"Which number times {w} makes {area}?", "missing side", ("rect", w, "?"))
    if difficulty == "easy" or rng.random() < 0.5:
        return _q(f"What is the area of a {w} by {h} rectangle?", w * h,
                  [f"Area counts the squares inside: {h} rows of {w}.",
                   f"{w} × {h} = {w * h}.", f"So the area is {w * h} square units."],
                  "Multiply the length by the width.", "area", ("rect", w, h))
    return _q(f"What is the perimeter of a {w} by {h} rectangle?", 2 * (w + h),
              [f"Perimeter is the distance all the way around.",
               f"Two lengths and two widths: {w} + {h} + {w} + {h}.",
               f"= {2 * (w + h)}, so the perimeter is {2 * (w + h)}."],
              "Add all four sides.", "perimeter", ("rect", w, h))


# --------------------------------------------------------------------------- time & money
def _clock(h, m):
    return f"{h}:{m:02d}"


def time_money(rng, difficulty):
    if rng.random() < 0.5:  # time: minutes between two clock times
        if difficulty == "easy":
            h, m = rng.randint(1, 11), rng.choice([0, 5, 10, 15, 20])
            gap = rng.choice([5, 10, 15, 20, 25, 30])
        elif difficulty == "intermediate":
            h, m = rng.randint(1, 11), rng.choice([30, 35, 40, 45, 50])
            gap = rng.choice([15, 20, 25, 30, 35, 40])
        else:
            h, m = rng.randint(1, 10), rng.choice([10, 20, 35, 40, 50])
            gap = rng.choice([65, 75, 80, 95, 110])
        end = h * 60 + m + gap
        eh, em = end // 60, end % 60
        eh = (eh - 1) % 12 + 1
        next_hour = 60 - m
        steps = [f"Start at {_clock(h, m)}."]
        if m + gap > 60:
            steps.append(f"From {_clock(h, m)} to {_clock(h % 12 + 1, 0)} is {next_hour} minutes.")
            steps.append(f"From {_clock(h % 12 + 1, 0)} to {_clock(eh, em)} is {gap - next_hour} minutes.")
            steps.append(f"{next_hour} + {gap - next_hour} = {gap} minutes.")
        else:
            steps.append(f"Count on from {m} minutes to {m + gap} minutes past.")
            steps.append(f"{m + gap} − {m} = {gap} minutes.")
        return _q(f"How many minutes from {_clock(h, m)} to {_clock(eh, em)}?", gap, steps,
                  "Jump to the next o'clock first, then count the rest.", "elapsed time", ("clock", h, m))
    # money: change from a payment
    if difficulty == "easy":
        pay, cost = rng.choice([5, 10]), rng.randint(1, 4)
    elif difficulty == "intermediate":
        pay = rng.choice([5, 10, 20])
        cost = round(rng.randint(100, pay * 100 - 25) / 25) * 0.25
    else:
        pay = rng.choice([10, 20])
        count, each = rng.randint(2, 4), rng.choice([1.25, 1.75, 2.50, 3.25])
        cost = count * each
        change = round(pay - cost, 2)
        return _q(f"You buy {count} snacks at ${each:.2f} each and pay ${pay}. How much change?", f"{change:.2f}",
                  [f"Total cost: {count} × ${each:.2f} = ${cost:.2f}.",
                   f"Change = ${pay} − ${cost:.2f}.", f"= ${change:.2f}."],
                  "Find the total first, then take it away from what you paid.", "money")
    change = round(pay - cost, 2)
    cost_text = f"${cost:.2f}" if cost != int(cost) else f"${int(cost)}"
    answer = f"{change:.2f}" if change != int(change) else str(int(change))
    return _q(f"You pay ${pay} for something that costs {cost_text}. How much change?", answer,
              [f"Change = what you paid − the cost.", f"${pay} − {cost_text}.",
               f"Count up from {cost_text} to ${pay}: that's ${answer}."],
              "Count up from the cost to what you paid.", "money")


BUILDERS = {"fractions": fractions, "place_value": place_value, "shapes": shapes, "time_money": time_money}

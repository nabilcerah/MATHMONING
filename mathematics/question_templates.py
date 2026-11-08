"""GDD 18: deterministic question templates for every mastery topic at four difficulty bands.

Each template returns a draft dict. Nothing here is trusted on its own: question_generator.py
re-proves every answer (``expression`` is evaluated exactly, ``equation`` is checked by
substitution, ``same_as`` by symbolic equivalence) before a question is ever shown.

Drafts also carry:
* three progressive ``hints`` (a nudge, a strategy, the first step) that never state the answer;
* ``misconceptions``: wrong answers a learner typically gives, tagged with the misconception
  that produces them, so the Learning Analyst can recognise repeated mistakes.
"""
from fractions import Fraction
from math import gcd

# Misconception tag -> (short label, what the tutor says about it).
MISCONCEPTIONS = {
    "forgot_carry": ("forgetting to carry", "When a column adds up to 10 or more, carry the ten into the next column."),
    "column_swap": ("subtracting the smaller digit from the larger", "In each column take the BOTTOM digit away from the TOP one; if the top is smaller, borrow first."),
    "added_instead": ("adding instead of subtracting", "Read the sign carefully before you start."),
    "place_value": ("losing a place value", "When you multiply by the tens digit, the answer is worth ten times more: add a zero."),
    "decimal_point": ("misplacing the decimal point", "Line the decimal points up, or count the decimal places in the question."),
    "added_denominators": ("adding the denominators", "The denominator names the size of the pieces. Make the pieces the same size, then add only the numerators."),
    "unsimplified": ("not simplifying", "Divide the top and bottom by their highest common factor."),
    "no_flip": ("dividing fractions without flipping", "To divide by a fraction, multiply by its reciprocal (flip the second fraction)."),
    "ratio_total": ("using a ratio part as the total", "Add the parts of the ratio first to find how many equal shares there are."),
    "minus_negative": ("treating minus a negative as minus", "Subtracting a negative is the same as adding: 5 − (−4) = 5 + 4."),
    "sign_rule": ("the sign rule", "Same signs multiply or divide to a positive; different signs give a negative."),
    "isolating_variables": ("isolating the variable", "Undo operations in reverse order: first remove the + or −, then divide by the number in front of x."),
    "wrong_inverse": ("using the wrong inverse operation", "Undo + with −, and undo × with ÷. Do the same thing to both sides."),
    "collect_terms": ("collecting like terms", "Move all the x terms to one side and the numbers to the other before dividing."),
    "area_perimeter": ("mixing up area and perimeter", "Perimeter is the distance around the edge; area is the space inside (length × width)."),
    "forgot_half": ("forgetting the ½ in triangle area", "A triangle is half of a rectangle: ½ × base × height."),
    "angle_sum": ("the angle sum", "Angles on a straight line make 180°; angles in a triangle also make 180°."),
    "added_sides": ("adding the sides for Pythagoras", "Square the two shorter sides, add the squares, then take the square root."),
    "nth_term": ("the nth-term rule", "The first term is already there, so you add the difference (n − 1) times."),
    "wrong_step": ("the step size", "Find the difference between neighbouring terms before you continue the pattern."),
    "time_base": ("counting time in hundreds", "An hour has 60 minutes, not 100. Count on to the next hour first."),
    "one_side": ("counting only one side", "Check how many sides or pieces the question asks for."),
}


def fmt(value):
    value = Fraction(value)
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def dec(value, places=2):
    text = f"{float(value):.{places}f}".rstrip("0").rstrip(".")
    return text or "0"


def draft(prompt, answer, answer_type, subtopic, hints, steps, misconceptions=None, expression=None,
          equation=None, same_as=None, minutes=None, visual=(), check=None):
    return {"prompt": prompt, "answer": str(answer), "answer_type": answer_type, "subtopic": subtopic,
            "hints": list(hints), "steps": list(steps), "explanation": " ".join(steps),
            "misconceptions": {str(k): v for k, v in (misconceptions or {}).items()
                               if str(k) not in (str(answer), "x", "None")},
            "expression": expression, "equation": equation, "same_as": same_as, "minutes": minutes,
            "visual": visual, "check": check}


# --------------------------------------------------------------------------- arithmetic
def addition(rng, difficulty, subtopic=None):
    if difficulty == "foundation":
        a, b = rng.randint(3, 19), rng.randint(2, 19)
        return draft(f"{a} + {b} = ?", a + b, "integer", "single_step",
                     ["Start from the bigger number.", f"Count on {b} from {a}.", f"Make a ten first: {a} + {10 - a % 10 if a % 10 else 10} = {a + (10 - a % 10 if a % 10 else 10)}."],
                     [f"{a} + {b} = {a + b}."], {a + b - 1: "forgot_carry", a + b + 1: "forgot_carry"}, f"{a}+{b}")
    if difficulty == "intermediate":
        while True:
            a, b = rng.randint(15, 89), rng.randint(15, 89)
            if a % 10 + b % 10 >= 10:
                break
        no_carry = a + b - 10
        return draft(f"{a} + {b} = ?", a + b, "integer", "carrying",
                     ["Add the ones first, then the tens.", f"{a % 10} + {b % 10} is more than 9, so you carry a ten.",
                      f"Ones: {a % 10} + {b % 10} = {a % 10 + b % 10}. Write {(a + b) % 10}, carry 1."],
                     [f"Ones: {a % 10} + {b % 10} = {a % 10 + b % 10}, carry 1.", f"Tens: {a // 10} + {b // 10} + 1 = {(a + b) // 10}.",
                      f"So {a} + {b} = {a + b}."], {no_carry: "forgot_carry"}, f"{a}+{b}")
    if difficulty == "advanced":
        a, b = rng.randint(125, 689), rng.randint(137, 589)
        return draft(f"{a} + {b} = ?", a + b, "integer", "three_digit",
                     ["Line the numbers up in columns.", "Add ones, then tens, then hundreds, carrying when needed.",
                      f"Ones: {a % 10} + {b % 10} = {a % 10 + b % 10}."],
                     [f"Hundreds: {a // 100 * 100} + {b // 100 * 100} = {(a // 100 + b // 100) * 100}.",
                      f"The rest: {a % 100} + {b % 100} = {a % 100 + b % 100}.", f"Total: {a + b}."],
                     {a + b - 10: "forgot_carry", a + b - 100: "forgot_carry"}, f"{a}+{b}")
    a = Fraction(rng.randint(105, 989), 100)
    b = Fraction(rng.randint(12, 98), 10)
    wrong = a + b / 10
    return draft(f"{dec(a)} + {dec(b)} = ?", dec(a + b), "decimal", "decimals",
                 ["Line up the decimal points.", f"Write {dec(b)} as {float(b):.2f} so both have two decimal places.",
                  f"Now add {float(a):.2f} + {float(b):.2f} column by column."],
                 [f"{float(a):.2f} + {float(b):.2f} = {dec(a + b)}."], {dec(wrong): "decimal_point"},
                 f"{a.numerator}/{a.denominator}+{b.numerator}/{b.denominator}")


def subtraction(rng, difficulty, subtopic=None):
    if difficulty == "foundation":
        a = rng.randint(8, 25)
        b = rng.randint(2, a - 1)
        return draft(f"{a} − {b} = ?", a - b, "integer", "single_step",
                     ["Subtraction finds the difference.", f"Count up from {b} to {a}.", f"What do you add to {b} to make {a}?"],
                     [f"{a} − {b} = {a - b}."], {a + b: "added_instead"}, f"{a}-{b}")
    if difficulty == "intermediate":
        while True:
            a, b = rng.randint(41, 98), rng.randint(12, 39)
            if a % 10 < b % 10:
                break
        swapped = (a // 10 - b // 10) * 10 + (b % 10 - a % 10)
        return draft(f"{a} − {b} = ?", a - b, "integer", "borrowing",
                     ["Work from the ones column.", f"You can't take {b % 10} from {a % 10}, so borrow a ten.",
                      f"After borrowing: {a % 10 + 10} − {b % 10} = {a % 10 + 10 - b % 10} in the ones."],
                     [f"Borrow a ten: ones {a % 10 + 10} − {b % 10} = {a % 10 + 10 - b % 10}.",
                      f"Tens: {a // 10 - 1} − {b // 10} = {a // 10 - 1 - b // 10}.", f"So {a} − {b} = {a - b}."],
                     {swapped: "column_swap", a + b: "added_instead"}, f"{a}-{b}")
    if difficulty == "advanced":
        a = rng.choice([300, 400, 500, 600, 700, 800, 900]) + rng.randint(0, 9)
        b = rng.randint(112, a - 60)
        return draft(f"{a} − {b} = ?", a - b, "integer", "across_zero",
                     ["Borrowing across a zero takes two steps.", f"Count up from {b} to the next hundred, then on to {a}.",
                      f"From {b} to {(b // 100 + 1) * 100} is {(b // 100 + 1) * 100 - b}."],
                     [f"{b} → {(b // 100 + 1) * 100} is {(b // 100 + 1) * 100 - b}.", f"{(b // 100 + 1) * 100} → {a} is {a - (b // 100 + 1) * 100}.",
                      f"Together: {a - b}."], {a - b + 100: "column_swap", a - b - 10: "forgot_carry"}, f"{a}-{b}")
    a = Fraction(rng.randint(500, 990), 100)
    b = Fraction(rng.randint(12, 45), 10)
    return draft(f"{dec(a)} − {dec(b)} = ?", dec(a - b), "decimal", "decimals",
                 ["Line up the decimal points.", f"Write {dec(b)} as {float(b):.2f}.", "Subtract column by column, borrowing if needed."],
                 [f"{float(a):.2f} − {float(b):.2f} = {dec(a - b)}."], {dec(a - b / 10): "decimal_point"},
                 f"{a.numerator}/{a.denominator}-{b.numerator}/{b.denominator}")


def multiplication(rng, difficulty, subtopic=None):
    if subtopic == "bridge_bundles":
        planks, nails = rng.randint(12, 36), rng.choice([4, 6, 8])
        return draft(f"Each of the {planks} new planks needs {nails} nails. How many nails does Bram need?",
                     planks * nails, "integer", "bridge_bundles",
                     ["This is equal groups: one group of nails per plank.", f"Work out {planks} × {nails}.",
                      f"Split it: {planks // 10 * 10} × {nails} and {planks % 10} × {nails}."],
                     [f"{planks} planks × {nails} nails = {planks * nails} nails."],
                     {planks + nails: "added_instead"}, f"{planks}*{nails}")
    if difficulty == "foundation":
        a, b = rng.randint(2, 10), rng.randint(2, 10)
        return draft(f"{a} × {b} = ?", a * b, "integer", "times_tables",
                     ["Multiplication is equal groups.", f"Think of {a} groups of {b}.", f"Count in {b}s, {a} times."],
                     [f"{a} × {b} = {a * b}."], {a + b: "added_instead"}, f"{a}*{b}")
    if difficulty == "intermediate":
        a, b = rng.choice([n for n in range(13, 50) if n % 10]), rng.randint(3, 9)
        no_carry = (a // 10) * b * 10 + (a % 10) * b % 10
        return draft(f"{a} × {b} = ?", a * b, "integer", "two_by_one",
                     ["Split the bigger number into tens and ones.", f"{a} = {a // 10 * 10} + {a % 10}.",
                      f"{a // 10 * 10} × {b} = {a // 10 * 10 * b}."],
                     [f"{a // 10 * 10} × {b} = {a // 10 * 10 * b}.", f"{a % 10} × {b} = {a % 10 * b}.",
                      f"Add them: {a * b}."], {no_carry: "forgot_carry", a + b: "added_instead"}, f"{a}*{b}")
    if difficulty == "advanced":
        a, b = rng.randint(14, 48), rng.randint(13, 39)
        lost = a * (b % 10) + a * (b // 10)
        return draft(f"{a} × {b} = ?", a * b, "integer", "two_by_two",
                     ["Split the second number into tens and ones.", f"Work out {a} × {b // 10 * 10} and {a} × {b % 10}.",
                      f"{a} × {b % 10} = {a * (b % 10)}."],
                     [f"{a} × {b // 10 * 10} = {a * (b // 10) * 10}.", f"{a} × {b % 10} = {a * (b % 10)}.",
                      f"Add: {a * (b // 10) * 10} + {a * (b % 10)} = {a * b}."], {lost: "place_value"}, f"{a}*{b}")
    a, b = Fraction(rng.randint(12, 95), 10), rng.randint(3, 9)
    return draft(f"{dec(a)} × {b} = ?", dec(a * b), "decimal", "decimals",
                 ["Ignore the decimal point first.", f"Work out {a.numerator * 10 // a.denominator} × {b}.",
                  "Then put back one decimal place."],
                 [f"{int(a * 10)} × {b} = {int(a * 10) * b}.", f"One decimal place: {dec(a * b)}."],
                 {str(int(a * 10) * b): "decimal_point"}, f"{a.numerator}/{a.denominator}*{b}")


def division(rng, difficulty, subtopic=None):
    if difficulty == "foundation":
        b, q = rng.randint(2, 10), rng.randint(2, 10)
        return draft(f"{b * q} ÷ {b} = ?", q, "integer", "facts",
                     ["Division undoes multiplication.", f"Which number times {b} makes {b * q}?", f"Count in {b}s up to {b * q}."],
                     [f"{b} × {q} = {b * q}, so {b * q} ÷ {b} = {q}."], {b * q - b: "added_instead"}, f"{b * q}/{b}")
    if difficulty == "intermediate":
        b, q = rng.randint(3, 9), rng.choice([n for n in range(14, 100) if n % 10])
        return draft(f"{b * q} ÷ {b} = ?", q, "integer", "short_division",
                     ["Use short division, or split the number.", f"How many {b}s go into the first part of {b * q}?",
                      f"Try {b} × {q // 10 * 10} = {b * q // 10 * 10}."],
                     [f"{b} × {q // 10 * 10} = {b * (q // 10 * 10)}, leaving {b * q - b * (q // 10 * 10)}.",
                      f"{b * q - b * (q // 10 * 10)} ÷ {b} = {q % 10}.", f"So the answer is {q}."], {}, f"{b * q}/{b}")
    if difficulty == "advanced":
        b, q = rng.randint(12, 25), rng.choice([n for n in range(12, 49) if n % 10])
        return draft(f"{b * q} ÷ {b} = ?", q, "integer", "long_division",
                     ["Estimate first using a times-table you know.", f"{b} × 10 = {b * 10}. How many tens of {b} fit?",
                      f"{b} × {q // 10 * 10} = {b * (q // 10 * 10)}."],
                     [f"{b} × {q // 10 * 10} = {b * (q // 10 * 10)}.", f"Left over: {b * q - b * (q // 10 * 10)} = {b} × {q % 10}.",
                      f"So {b * q} ÷ {b} = {q}."], {}, f"{b * q}/{b}")
    b = Fraction(rng.choice([2, 4, 5, 8]), 10)
    q = rng.randint(3, 24)
    a = b * q
    return draft(f"{dec(a)} ÷ {dec(b)} = ?", q, "number", "decimals",
                 ["Make the divisor a whole number.", "Multiply both numbers by 10.",
                  f"That gives {dec(a * 10)} ÷ {dec(b * 10)}."],
                 [f"× 10 both: {dec(a * 10)} ÷ {dec(b * 10)} = {q}."], {dec(Fraction(q, 10)): "decimal_point"},
                 f"({a.numerator}/{a.denominator})/({b.numerator}/{b.denominator})")


# --------------------------------------------------------------------------- fractions & ratios
def fractions(rng, difficulty, subtopic=None):
    if difficulty == "foundation":
        d = rng.choice([2, 3, 4, 5, 8])
        n = rng.randint(1, d - 1)
        whole = d * rng.randint(2, 8)
        return draft(f"{n}/{d} of {whole} = ?", whole // d * n, "integer", "fraction_of_amount",
                     [f"Find 1/{d} first.", f"1/{d} of {whole} is {whole} ÷ {d}.", f"Then take {n} of those parts."],
                     [f"1/{d} of {whole} = {whole // d}.", f"{n} parts: {whole // d} × {n} = {whole // d * n}."],
                     {whole // d: "unsimplified", whole * n: "added_instead"}, f"{whole}/{d}*{n}")
    if difficulty == "intermediate":
        b = rng.choice([2, 3, 4, 5])
        k = rng.choice([2, 3])
        d = b * k
        a = rng.randint(1, b - 1)
        c = rng.randint(1, d - 1)
        total = Fraction(a, b) + Fraction(c, d)
        if total >= 1:
            c = 1
            total = Fraction(a, b) + Fraction(c, d)
        return draft(f"{a}/{b} + {c}/{d} = ?", fmt(total), "fraction", "add_related",
                     ["Make the denominators equal first.", f"What number can both {b} and {d} divide into?",
                      f"{a}/{b} = {a * k}/{d}."],
                     [f"{a}/{b} = {a * k}/{d}.", f"{a * k}/{d} + {c}/{d} = {a * k + c}/{d}.",
                      f"Simplified: {fmt(total)}."],
                     {fmt(Fraction(a + c, b + d)): "added_denominators"}, f"{a}/{b}+{c}/{d}")
    if difficulty == "advanced":
        while True:
            b, d = rng.choice([3, 4, 5, 6]), rng.choice([4, 5, 6, 7, 8])
            if b != d and d % b and b % d:
                break
        a, c = rng.randint(1, b - 1), rng.randint(1, d - 1)
        subtract = rng.random() < 0.5 and Fraction(a, b) > Fraction(c, d)
        result = Fraction(a, b) - Fraction(c, d) if subtract else Fraction(a, b) + Fraction(c, d)
        sign = "−" if subtract else "+"
        lcm = b * d // gcd(b, d)
        wrong = Fraction(a - c, b + d) if subtract else Fraction(a + c, b + d)
        return draft(f"{a}/{b} {sign} {c}/{d} = ?  (simplest form)", fmt(result), "simplified_fraction", "unlike_denominators",
                     ["The denominators are different, so the pieces are different sizes.",
                      f"Use a common denominator: {lcm} works for both {b} and {d}.",
                      f"{a}/{b} = {a * lcm // b}/{lcm} and {c}/{d} = {c * lcm // d}/{lcm}."],
                     [f"{a}/{b} = {a * lcm // b}/{lcm}, {c}/{d} = {c * lcm // d}/{lcm}.",
                      f"{a * lcm // b} {sign} {c * lcm // d} = {a * lcm // b - c * lcm // d if subtract else a * lcm // b + c * lcm // d}, over {lcm}.",
                      f"Simplest form: {fmt(result)}."],
                     {fmt(wrong) if wrong >= 0 else "x": "added_denominators"},
                     f"{a}/{b}{'-' if subtract else '+'}{c}/{d}")
    a, b = rng.randint(1, 5), rng.randint(2, 7)
    c, d = rng.randint(1, 5), rng.randint(2, 7)
    if rng.random() < 0.5:
        result = Fraction(a, b) * Fraction(c, d)
        return draft(f"{a}/{b} × {c}/{d} = ?  (simplest form)", fmt(result), "simplified_fraction", "multiply",
                     ["Multiply the tops, then multiply the bottoms.", f"Top: {a} × {c}. Bottom: {b} × {d}.",
                      f"That gives {a * c}/{b * d}. Can it be simplified?"],
                     [f"{a} × {c} = {a * c}, {b} × {d} = {b * d}.", f"{a * c}/{b * d} = {fmt(result)}."],
                     {fmt(Fraction(a + c, b + d)): "added_denominators"}, f"({a}/{b})*({c}/{d})")
    result = Fraction(a, b) / Fraction(c, d)
    wrong = Fraction(a, b) * Fraction(c, d)
    return draft(f"{a}/{b} ÷ {c}/{d} = ?  (simplest form)", fmt(result), "simplified_fraction", "divide",
                 ["Dividing by a fraction means multiplying by its reciprocal.", f"Flip {c}/{d} to {d}/{c}.",
                  f"Now work out {a}/{b} × {d}/{c}."],
                 [f"{a}/{b} ÷ {c}/{d} = {a}/{b} × {d}/{c} = {a * d}/{b * c}.", f"Simplest form: {fmt(result)}."],
                 {fmt(wrong): "no_flip"}, f"({a}/{b})/({c}/{d})")


def ratios(rng, difficulty, subtopic=None):
    if difficulty == "foundation":
        a, b, k = rng.randint(1, 4), rng.randint(2, 5), rng.randint(2, 6)
        return draft(f"For every {a} red gems there are {b} blue gems. With {a * k} red gems, how many blue?",
                     b * k, "integer", "scaling",
                     ["The ratio stays the same when you scale it.", f"How many times bigger is {a * k} than {a}?",
                      f"{a * k} ÷ {a} = {k}."],
                     [f"{a * k} ÷ {a} = {k}.", f"{b} × {k} = {b * k} blue gems."], {b + a * k - a: "added_instead"},
                     f"{b}*{k}")
    if difficulty == "intermediate":
        a, b = rng.randint(1, 4), rng.randint(2, 5)
        unit = rng.randint(3, 12)
        total = (a + b) * unit
        return draft(f"Share {total} coins in the ratio {a}:{b}. How many coins in the bigger share?",
                     max(a, b) * unit, "integer", "sharing",
                     ["Add the parts of the ratio to find the number of shares.", f"{a} + {b} = {a + b} shares.",
                      f"One share is {total} ÷ {a + b}."],
                     [f"{a} + {b} = {a + b} shares.", f"One share = {total} ÷ {a + b} = {unit}.",
                      f"Bigger share = {max(a, b)} × {unit} = {max(a, b) * unit}."],
                     {total // max(a, b) if total % max(a, b) == 0 else "x": "ratio_total"}, f"{max(a, b)}*{total}/({a}+{b})")
    if difficulty == "advanced":
        p = rng.choice([10, 20, 25, 30, 40, 50, 60, 75])
        n = rng.choice([40, 60, 80, 120, 160, 200, 240])
        return draft(f"{p}% of {n} = ?", fmt(Fraction(p * n, 100)), "number", "percentages",
                     ["Per cent means 'out of 100'.", f"Find 1% (÷ 100) or 10% (÷ 10) first.",
                      f"10% of {n} is {fmt(Fraction(n, 10))}."],
                     [f"{p}% = {p}/100.", f"{p}/100 × {n} = {fmt(Fraction(p * n, 100))}."],
                     {fmt(Fraction(n, p)) if n % p == 0 else "x": "ratio_total"}, f"{p}*{n}/100")
    count, price_tenths = rng.randint(3, 6), rng.randint(6, 25)
    unit = Fraction(price_tenths, 10)
    target = rng.randint(7, 12)
    return draft(f"{count} pens cost {dec(unit * count)} coins. How much do {target} pens cost?", dec(unit * target),
                 "decimal", "unitary",
                 ["Find the cost of ONE pen first.", f"{dec(unit * count)} ÷ {count} gives one pen.",
                  f"One pen costs {dec(unit)}."],
                 [f"One pen: {dec(unit * count)} ÷ {count} = {dec(unit)}.", f"{target} pens: {dec(unit)} × {target} = {dec(unit * target)}."],
                 {dec(unit * count + target - count): "added_instead"}, f"{price_tenths}/10*{target}")


# --------------------------------------------------------------------------- integers
def _signed(n):
    return f"({n})" if n < 0 else str(n)


def integers(rng, difficulty, subtopic=None):
    if difficulty == "foundation":
        a, b = rng.randint(-9, -1), rng.randint(2, 12)
        return draft(f"{a} + {b} = ?", a + b, "integer", "number_line",
                     ["Picture a number line.", f"Start at {a} and move {b} steps to the right.",
                      f"It takes {-a} steps to reach 0."],
                     [f"From {a}, {-a} steps reach 0.", f"{b - (-a)} more steps: {a + b}."],
                     {-a + b: "sign_rule", a - b: "added_instead"}, f"{a}+{b}")
    if difficulty == "intermediate":
        a, b = rng.randint(-8, 12), rng.randint(2, 9)
        return draft(f"{a} − (−{b}) = ?", a + b, "integer", "minus_negative",
                     ["Two minus signs next to each other...", "Taking away a negative is the same as adding.",
                      f"Rewrite it as {a} + {b}."],
                     [f"{a} − (−{b}) = {a} + {b}.", f"= {a + b}."], {a - b: "minus_negative"}, f"{a}-(-{b})")
    if difficulty == "advanced":
        a, b = rng.randint(2, 9), rng.randint(2, 9)
        if rng.random() < 0.5:
            x, y = -a, -b
            return draft(f"({x}) × ({y}) = ?", x * y, "integer", "multiply_signs",
                         ["Multiply the numbers, then decide the sign.", "Same signs give a positive answer.",
                          f"{a} × {b} = {a * b}."],
                         [f"{a} × {b} = {a * b}.", f"Negative × negative = positive: {x * y}."],
                         {-(a * b): "sign_rule"}, f"({x})*({y})")
        return draft(f"({-a * b}) ÷ {b} = ?", -a, "integer", "divide_signs",
                     ["Divide the numbers, then decide the sign.", "Different signs give a negative answer.",
                      f"{a * b} ÷ {b} = {a}."],
                     [f"{a * b} ÷ {b} = {a}.", f"Negative ÷ positive = negative: {-a}."], {a: "sign_rule"}, f"({-a * b})/{b}")
    a, b, c = rng.randint(-6, -2), rng.randint(2, 6), rng.randint(2, 9)
    value = a * b - (-c)
    return draft(f"{_signed(a)} × {b} − (−{c}) = ?", value, "integer", "mixed",
                 ["Multiply before you subtract.", f"{_signed(a)} × {b} = {a * b}.",
                  f"Then {a * b} − (−{c}) means {a * b} + {c}."],
                 [f"{_signed(a)} × {b} = {a * b}.", f"{a * b} − (−{c}) = {a * b} + {c} = {value}."],
                 {a * b - c: "minus_negative", -a * b + c: "sign_rule"}, f"({a})*{b}-(-{c})")


# --------------------------------------------------------------------------- algebra
def algebra(rng, difficulty, subtopic=None):
    if difficulty == "foundation":
        x, k = rng.randint(2, 15), rng.randint(3, 15)
        return draft(f"Solve for x: x + {k} = {x + k}", x, "equation", "one_step",
                     ["What number plus " + str(k) + f" makes {x + k}?", f"Undo + {k} by subtracting {k}.",
                      f"Do it to both sides: x = {x + k} − {k}."],
                     [f"x + {k} = {x + k}.", f"Subtract {k} from both sides: x = {x}."],
                     {x + 2 * k: "wrong_inverse"}, equation=(f"x+{k}", str(x + k)))
    if difficulty == "intermediate":
        x, a, b = rng.randint(2, 12), rng.randint(2, 7), rng.randint(1, 15)
        c = a * x + b
        wrong = {c - b: "isolating_variables", (c + b) / Fraction(a): "wrong_inverse"}
        if c % a == 0:
            wrong[c // a - b] = "isolating_variables"
        return draft(f"Solve for x: {a}x + {b} = {c}", x, "equation", "two_step",
                     ["Undo operations in reverse order.", f"First subtract {b} from both sides.",
                      f"{a}x = {c - b}. Now what do you divide by?"],
                     [f"Subtract {b}: {a}x = {c - b}.", f"Divide by {a}: x = {x}."],
                     {fmt(k): v for k, v in wrong.items()}, equation=(f"{a}*x+{b}", str(c)))
    if difficulty == "advanced":
        if rng.random() < 0.35:
            p, q, r = rng.randint(2, 6), rng.randint(2, 6), rng.randint(1, 9)
            expr, answer = f"{p}x + {q}x + {r}", f"{p + q}x + {r}"
            return draft(f"Simplify: {expr}", answer, "simplified_expression", "collect_terms",
                         ["Like terms have the same letter.", f"Add the x terms: {p}x + {q}x.", "The number stays on its own."],
                         [f"{p}x + {q}x = {p + q}x.", f"So {expr} = {answer}."],
                         {f"{p + q + r}x": "collect_terms"}, same_as=(f"{p}x+{q}x+{r}", f"{p + q}x+{r}"))
        x = rng.randint(-4, 10)
        a, c = rng.randint(4, 9), rng.randint(1, 3)
        b = rng.randint(-9, 9)
        d = (a - c) * x + b
        b_text = f"+ {b}" if b >= 0 else f"− {-b}"
        d_text = f"+ {d}" if d >= 0 else f"− {-d}"
        c_text = "x" if c == 1 else f"{c}x"
        wrong = {}
        if (a + c) and (d - b) % (a + c) == 0:
            wrong[(d - b) // (a + c)] = "collect_terms"
        return draft(f"Solve: {a}x {b_text} = {c_text} {d_text}", x, "equation", "both_sides",
                     ["Get all the x terms on one side.", f"Subtract {c_text} from both sides.",
                      f"{a - c}x {b_text} = {d}."],
                     [f"Subtract {c_text}: {a - c}x {b_text} = {d}.", f"Undo the {b}: {a - c}x = {d - b}.", f"x = {x}."],
                     wrong, equation=(f"{a}*x+({b})", f"{c}*x+({d})"))
    x, y = rng.randint(1, 9), rng.randint(1, 9)
    s, t = x + y, x - y
    return draft(f"x + y = {s} and x − y = {t}. What is x?", x, "equation", "simultaneous",
                 ["Add the two equations together.", "The y terms cancel out when you add.",
                  f"Adding gives 2x = {s + t}."],
                 [f"(x + y) + (x − y) = {s} + {t}, so 2x = {s + t}.", f"x = {s + t} ÷ 2 = {x}."],
                 {s + t: "isolating_variables", y: "collect_terms"}, equation=(f"x+{y}", str(s)),
                 check=lambda: x + y == s and x - y == t)


# --------------------------------------------------------------------------- geometry
def geometry(rng, difficulty, subtopic=None):
    if subtopic == "bridge_area":
        length, width = rng.randint(8, 16), rng.randint(2, 4)
        return draft(f"The bridge deck is {length} m long and {width} m wide. How many 1 m² planks cover it?",
                     length * width, "integer", "bridge_area",
                     ["The planks cover the AREA of the deck.", "Area of a rectangle = length × width.",
                      f"Work out {length} × {width}."],
                     [f"Area = {length} × {width} = {length * width} m², so {length * width} planks."],
                     {2 * (length + width): "area_perimeter", length + width: "area_perimeter"}, f"{length}*{width}",
                     visual=("rect", length, width))
    if subtopic == "bridge_rail":
        length = rng.randint(9, 18)
        return draft(f"A rail runs along BOTH long sides of the {length} m bridge. How many metres of rail?",
                     2 * length, "integer", "bridge_rail",
                     ["Picture the bridge from above.", "There is a rail on each long side.", f"Two sides of {length} m."],
                     [f"2 × {length} m = {2 * length} m of rail."], {length: "one_side"}, f"2*{length}")
    if difficulty == "foundation":
        w, h = rng.randint(3, 12), rng.randint(2, 9)
        if rng.random() < 0.5:
            return draft(f"A rectangle is {w} cm by {h} cm. What is its AREA in cm²?", w * h, "integer", "area",
                         ["Area is the space inside.", "Multiply length by width.", f"{w} × {h}."],
                         [f"Area = {w} × {h} = {w * h} cm²."], {2 * (w + h): "area_perimeter"}, f"{w}*{h}",
                         visual=("rect", w, h))
        return draft(f"A rectangle is {w} cm by {h} cm. What is its PERIMETER in cm?", 2 * (w + h), "integer", "perimeter",
                     ["Perimeter is the distance all the way around.", "Add all four sides.", f"{w} + {h} + {w} + {h}."],
                     [f"Perimeter = 2 × ({w} + {h}) = {2 * (w + h)} cm."], {w * h: "area_perimeter", w + h: "one_side"},
                     f"2*({w}+{h})", visual=("rect", w, h))
    if difficulty == "intermediate":
        if rng.random() < 0.5:
            base, height = rng.choice([4, 6, 8, 10, 12, 14]), rng.randint(3, 11)
            return draft(f"A triangle has base {base} cm and height {height} cm. What is its area in cm²?",
                         base * height // 2, "integer", "triangle_area",
                         ["A triangle is half of a rectangle.", "Area = ½ × base × height.", f"{base} × {height} = {base * height}."],
                         [f"{base} × {height} = {base * height}.", f"Half of that: {base * height // 2} cm²."],
                         {base * height: "forgot_half"}, f"{base}*{height}/2")
        angle = rng.randint(25, 155)
        return draft(f"Two angles sit on a straight line. One is {angle}°. What is the other?", 180 - angle, "integer",
                     "angles_line", ["Angles on a straight line add up to a special number.", "They make 180°.",
                                     f"Work out 180 − {angle}."],
                     [f"180 − {angle} = {180 - angle}°."], {360 - angle: "angle_sum", 90 - angle if angle < 90 else "x": "angle_sum"},
                     f"180-{angle}")
    if difficulty == "advanced":
        if rng.random() < 0.5:
            l, w, h = rng.randint(2, 9), rng.randint(2, 6), rng.randint(2, 6)
            return draft(f"A cuboid is {l} cm × {w} cm × {h} cm. What is its volume in cm³?", l * w * h, "integer", "volume",
                         ["Volume is length × width × height.", f"Find the area of the base first: {l} × {w}.",
                          f"Base area = {l * w}. Now multiply by the height."],
                         [f"{l} × {w} = {l * w}.", f"{l * w} × {h} = {l * w * h} cm³."], {l + w + h: "added_instead"},
                         f"{l}*{w}*{h}")
        a, b = rng.randint(30, 80), rng.randint(30, 80)
        return draft(f"A triangle has angles {a}° and {b}°. What is the third angle?", 180 - a - b, "integer", "angles_triangle",
                     ["The angles in a triangle add up to 180°.", f"Add the two you know: {a} + {b}.",
                      f"{a} + {b} = {a + b}."], [f"{a} + {b} = {a + b}.", f"180 − {a + b} = {180 - a - b}°."],
                     {360 - a - b: "angle_sum"}, f"180-{a}-{b}")
    a, b, c = rng.choice([(3, 4, 5), (6, 8, 10), (5, 12, 13), (8, 15, 17), (9, 12, 15), (7, 24, 25)])
    return draft(f"A right-angled triangle has shorter sides {a} cm and {b} cm. How long is the hypotenuse?", c, "integer",
                 "pythagoras", ["Use Pythagoras: a² + b² = c².", f"Square both sides you know: {a}² and {b}².",
                                f"{a}² + {b}² = {a * a + b * b}."],
                 [f"{a}² + {b}² = {a * a} + {b * b} = {a * a + b * b}.", f"√{a * a + b * b} = {c} cm."],
                 {a + b: "added_sides", a * a + b * b: "added_sides"}, check=lambda: c * c == a * a + b * b)


# --------------------------------------------------------------------------- sequences & time
def sequences(rng, difficulty, subtopic=None):
    if difficulty == "foundation":
        start, step = rng.randint(1, 20), rng.randint(2, 9)
        terms = [start + step * i for i in range(4)]
        return draft(f"What comes next? {', '.join(map(str, terms))}, ?", start + step * 4, "integer", "next_term",
                     ["Look at how the numbers change.", f"Find the difference: {terms[1]} − {terms[0]}.",
                      f"It goes up by {step} each time."],
                     [f"The pattern adds {step}.", f"{terms[-1]} + {step} = {start + step * 4}."],
                     {terms[-1] + step + 1: "wrong_step", terms[-1] + start: "wrong_step"}, f"{start}+{step}*4",
                     visual=("sequence", tuple(terms)))
    if difficulty == "intermediate":
        if rng.random() < 0.5:
            start, step = rng.randint(40, 90), rng.randint(3, 9)
            terms = [start - step * i for i in range(4)]
            return draft(f"What comes next? {', '.join(map(str, terms))}, ?", start - step * 4, "integer", "decreasing",
                         ["Is the pattern going up or down?", f"Find the difference between {terms[0]} and {terms[1]}.",
                          f"It goes down by {step}."],
                         [f"The pattern subtracts {step}.", f"{terms[-1]} − {step} = {start - step * 4}."],
                         {terms[-1] + step: "wrong_step"}, f"{start}-{step}*4", visual=("sequence", tuple(terms)))
        h1, m1 = rng.randint(8, 15), rng.choice([10, 15, 20, 25, 30, 35, 40, 45, 50])
        duration = rng.randint(25, 75)
        end = h1 * 60 + m1 + duration
        return draft(f"A lesson starts at {h1}:{m1:02d} and lasts {duration} minutes. When does it end?",
                     f"{end // 60}:{end % 60:02d}", "time", "time",
                     ["Count on to the next hour first.", f"From {h1}:{m1:02d} to {h1 + 1}:00 is {60 - m1} minutes.",
                      f"Then add the remaining {duration - (60 - m1)} minutes." if duration > 60 - m1 else "It finishes before the next hour."],
                     [f"{h1}:{m1:02d} + {duration} min = {end // 60}:{end % 60:02d}."],
                     {}, minutes=(f"{h1}*60+{m1}+{duration}", end))
    if difficulty == "advanced":
        first, d, n = rng.randint(1, 9), rng.randint(2, 7), rng.randint(8, 15)
        terms = [first + d * i for i in range(4)]
        value = first + d * (n - 1)
        return draft(f"What is term number {n} of {', '.join(map(str, terms))}, ...?", value, "integer", "nth_term",
                     ["Find the common difference.", f"Term 1 is {first}; you add {d} for every step after that.",
                      f"Term {n} = {first} + {d} × ({n} − 1)."],
                     [f"Difference = {d}.", f"Term {n} = {first} + {d} × {n - 1} = {value}."],
                     {d * n: "nth_term", first + d * n: "nth_term"}, f"{first}+{d}*({n}-1)",
                     visual=("sequence", tuple(terms)))
    h, m = rng.randint(6, 17), rng.choice([5, 15, 25, 35, 40, 45, 50, 55])
    dh, dm = rng.randint(1, 4), rng.choice([20, 25, 35, 40, 45, 50])
    end = h * 60 + m + dh * 60 + dm
    return draft(f"A train leaves at {h:02d}:{m:02d}. The trip takes {dh} h {dm} min. What time does it arrive?",
                 f"{end // 60}:{end % 60:02d}", "time", "time",
                 ["Add the hours first, then the minutes.", f"{h:02d}:{m:02d} + {dh} h = {h + dh:02d}:{m:02d}.",
                  "When the minutes pass 60, that's another hour."],
                 [f"{h:02d}:{m:02d} + {dh} h = {h + dh:02d}:{m:02d}.", f"+ {dm} min = {end // 60}:{end % 60:02d}."],
                 {}, minutes=(f"{h}*60+{m}+{dh}*60+{dm}", end))


TEMPLATES = {"addition": addition, "subtraction": subtraction, "multiplication": multiplication,
             "division": division, "fractions": fractions, "ratios": ratios, "integers": integers,
             "algebra": algebra, "geometry": geometry, "sequences": sequences}

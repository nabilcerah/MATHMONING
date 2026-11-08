"""Addition, subtraction, multiplication, division, negative numbers and large numbers."""
from mathematics.question_engine.generators import Draft, pick_range
from mathematics.question_engine.model import fmt


def _no_carry_sum(a, b):
    """The 'forgot to carry' answer: add each column and drop the carries."""
    result, place = 0, 1
    while a or b:
        result += ((a % 10 + b % 10) % 10) * place
        a, b, place = a // 10, b // 10, place * 10
    return result


def _no_borrow_difference(a, b):
    """The 'smaller from larger in every column' mistake."""
    result, place = 0, 1
    while a or b:
        result += abs(a % 10 - b % 10) * place
        a, b, place = a // 10, b // 10, place * 10
    return result


def addition(rng, level):
    low, high = pick_range(level, [(2, 20), (12, 99), (45, 999), (250, 9999), (1200, 99999)])
    a, b = rng.randint(low, high), rng.randint(low, high)
    total = a + b
    return Draft(f"{fmt(a)} + {fmt(b)} = ?", total, [_no_carry_sum(a, b), total + 10, total - 10, total + 1],
                 f"Add the ones, then the tens, carrying when a column passes 9: {fmt(a)} + {fmt(b)} = {fmt(total)}.",
                 "Line the numbers up by place value and add column by column.", f"{a}+{b}")


def subtraction(rng, level):
    low, high = pick_range(level, [(2, 20), (12, 99), (45, 999), (250, 9999), (1200, 99999)])
    a, b = sorted((rng.randint(low, high), rng.randint(low, high)), reverse=True)
    if a == b:
        a += rng.randint(1, 9)
    diff = a - b
    return Draft(f"{fmt(a)} − {fmt(b)} = ?", diff, [_no_borrow_difference(a, b), diff + 10, diff - 10, a + b],
                 f"Subtract column by column, borrowing when the top digit is smaller: {fmt(a)} − {fmt(b)} = {fmt(diff)}.",
                 "Check: the answer plus the number you took away gives the first number.", f"{a}-{b}")


def multiplication(rng, level):
    (a_low, a_high), (b_low, b_high) = pick_range(level, [((2, 5), (2, 10)), ((2, 12), (2, 12)), ((6, 25), (3, 12)),
                                                          ((12, 99), (6, 19)), ((25, 199), (12, 49))])
    a, b = rng.randint(a_low, a_high), rng.randint(b_low, b_high)
    product = a * b
    return Draft(f"{a} × {b} = ?", product, [a * (b - 1), a * (b + 1), a + b, product + 10],
                 f"{a} × {b} means {b} groups of {a}: {product}." + (
                     f" Split it: {a} × {b // 10 * 10} + {a} × {b % 10}." if b >= 12 and b % 10 else ""),
                 "Use a times-table fact you know, then add or take away one group.", f"{a}*{b}")


def division(rng, level):
    (d_low, d_high), (q_low, q_high) = pick_range(level, [((2, 5), (2, 10)), ((2, 12), (2, 12)), ((3, 12), (6, 25)),
                                                          ((6, 19), (12, 99)), ((12, 49), (25, 199))])
    divisor, quotient = rng.randint(d_low, d_high), rng.randint(q_low, q_high)
    dividend = divisor * quotient
    return Draft(f"{fmt(dividend)} ÷ {divisor} = ?", quotient, [quotient + 1, quotient - 1, dividend - divisor, quotient * 2],
                 f"Ask: how many groups of {divisor} make {fmt(dividend)}? {divisor} × {quotient} = {fmt(dividend)}, so the answer is {quotient}.",
                 "Division undoes multiplication. Which times-table fact matches?", f"{dividend}/{divisor}")


def negative_numbers(rng, level):
    if level <= 1:
        a, b = rng.randint(2, 9), rng.randint(1, 12)
        expression, prompt = f"(-{a})+{b}", f"−{a} + {b} = ?"
        why = f"Start at −{a} on the number line and move {b} to the right."
    elif level == 2:
        a, b = rng.randint(2, 15), rng.randint(16, 30)
        expression, prompt = f"{a}-{b}", f"{a} − {b} = ?"
        why = f"Taking away more than you have goes below zero: {a} − {b} is {b - a} below zero."
    elif level == 3:
        a, b = rng.randint(3, 20), rng.randint(2, 20)
        if rng.random() < 0.5:
            expression, prompt = f"(-{a})-(-{b})", f"−{a} − (−{b}) = ?"
            why = f"Subtracting a negative is the same as adding: −{a} + {b}."
        else:
            expression, prompt = f"(-{a})*{b % 9 + 2}", f"−{a} × {b % 9 + 2} = ?"
            why = "A negative times a positive is negative."
    elif level == 4:
        a, b = rng.randint(2, 12), rng.randint(2, 12)
        if rng.random() < 0.5:
            expression, prompt = f"(-{a})*(-{b})", f"(−{a}) × (−{b}) = ?"
            why = "A negative times a negative is positive."
        else:
            expression, prompt = f"(-{a * b})/{b}", f"−{a * b} ÷ {b} = ?"
            why = "A negative divided by a positive is negative."
    else:
        a, b, c = rng.randint(2, 15), rng.randint(2, 9), rng.randint(2, 9)
        expression, prompt = f"(-{a})-{b}*(-{c})", f"−{a} − {b} × (−{c}) = ?"
        why = f"Multiply first: {b} × (−{c}) = −{b * c}. Then −{a} − (−{b * c}) = −{a} + {b * c}."
    from mathematics.question_engine.safe_eval import safe_eval
    answer = safe_eval(expression)
    mistakes = [-answer, abs(answer), answer + 2, answer - 2]
    return Draft(prompt, answer, mistakes, f"{why} The answer is {fmt(answer)}.",
                 "Picture a number line: adding moves right, subtracting moves left.", expression,
                 tags=("integers",))


def large_numbers(rng, level):
    if level <= 1:
        a, b = rng.sample(range(100, 1000), 2)
        answer = str(max(a, b))
        return Draft(f"Which is greater: {a} or {b}?", answer, [], kind="choice", options=[str(a), str(b)],
                     explanation=f"Compare the hundreds first, then the tens: {answer} is greater.",
                     hint="Look at the leftmost digit first.", tags=("comparison",))
    if level == 2:
        number = rng.randint(10000, 99999)
        digits = str(number)
        position = rng.randint(0, 3)
        digit = int(digits[position])
        while digit == 0 or digits.count(digits[position]) > 1:
            number = rng.randint(10000, 99999)
            digits = str(number)
            digit = int(digits[position])
        place = 10 ** (len(digits) - 1 - position)
        value = digit * place
        return Draft(f"What is the value of the digit {digit} in {fmt(number)}?", value,
                     [digit, digit * place // 10, digit * place * 10],
                     f"The {digit} is in the {fmt(place)}s place, so it is worth {digit} × {fmt(place)} = {fmt(value)}.",
                     "Count places from the right: ones, tens, hundreds, thousands...", f"{digit}*{place}",
                     tags=("place_value",))
    if level == 3:
        a, b = rng.randint(10000, 99999), rng.randint(10000, 99999)
        op = rng.choice("+-")
        a, b = (a, b) if op == "+" or a > b else (b, a)
        answer = a + b if op == "+" else a - b
        mistake = _no_carry_sum(a, b) if op == "+" else _no_borrow_difference(a, b)
        return Draft(f"{fmt(a)} {'+' if op == '+' else '−'} {fmt(b)} = ?", answer, [mistake, answer + 1000, answer - 1000],
                     f"Work column by column from the ones: the answer is {fmt(answer)}.",
                     "Big numbers follow the same column rules as small ones.", f"{a}{op}{b}")
    if level == 4:
        number = rng.randint(100000, 999999)
        place = rng.choice([1000, 10000])
        answer = (number + place // 2) // place * place
        down = number // place * place
        other_way = down + place if answer == down else down  # rounded the wrong direction
        return Draft(f"Round {fmt(number)} to the nearest {fmt(place)}.", answer,
                     [other_way, number, answer + place, answer - place],
                     f"Look at the digit after the {fmt(place)}s place: round {'up' if answer > number else 'down'} to {fmt(answer)}.",
                     "5 or more rounds up, 4 or less rounds down.",
                     verify=lambda: abs(answer - number) <= place // 2 and answer % place == 0, tags=("rounding",))
    millions = rng.randint(2, 9) * 1_000_000 + rng.randint(1, 9) * 100_000
    divisor = rng.choice([100, 1000])
    answer = millions // divisor
    return Draft(f"{fmt(millions)} ÷ {fmt(divisor)} = ?", answer, [answer * 10, answer // 10, millions // (divisor * 100)],
                 f"Dividing by {fmt(divisor)} moves every digit {len(str(divisor)) - 1} places to the right: {fmt(answer)}.",
                 "Remove one zero for every zero in the divisor.", f"{millions}/{divisor}")

"""Step-by-step worked solutions for the 'solve it together' walkthrough.

Every step is generated from the question's own numbers (parsed from its prompt), so the
child sees *their* question solved - not a generic example. Works fully offline.
"""
import re

NUMBER = r"(\d+)"


def _tens_ones(n):
    return n // 10 * 10, n % 10


def _addition(a, b):
    total = a + b
    if a < 10 and b < 10:
        big, small = max(a, b), min(a, b)
        counts = ", ".join(str(big + i) for i in range(1, small + 1))
        return [f"Start at the bigger number: {big}.",
                f"Count on {small} more: {counts}.",
                f"So {a} + {b} = {total}."]
    (at, ao), (bt, bo) = _tens_ones(a), _tens_ones(b)
    steps = [f"Split each number into tens and ones: {a} = {at} + {ao}, {b} = {bt} + {bo}.",
             f"Add the tens: {at} + {bt} = {at + bt}.",
             f"Add the ones: {ao} + {bo} = {ao + bo}."]
    steps.append(f"Put them together: {at + bt} + {ao + bo} = {total}.")
    return steps


def _subtraction(a, b):
    diff = a - b
    if b < 10 and a < 20:
        return [f"Think: what do we add to {b} to reach {a}?",
                f"Count up from {b} to {a}: that is {diff} steps.",
                f"So {a} − {b} = {diff}."]
    next_ten = (b // 10 + 1) * 10 if b % 10 else b
    if next_ten >= a:
        return [f"Think: what do we add to {b} to reach {a}?",
                f"From {b} up to {a} is {diff}.",
                f"So {a} − {b} = {diff}."]
    first, second = next_ten - b, a - next_ten
    steps = [f"Think of it as a jump: what do we add to {b} to reach {a}?"]
    if first:
        steps.append(f"Jump from {b} to the next ten, {next_ten}: that's {first}.")
    steps.append(f"Jump from {next_ten} to {a}: that's {second}.")
    steps.append(f"Add the jumps: {first} + {second} = {diff}, so {a} − {b} = {diff}.")
    return steps


def _multiplication(a, b):
    product = a * b
    big, small = (a, b) if a >= b else (b, a)
    if big < 10:
        multiples = ", ".join(str(big * i) for i in range(1, small + 1))
        return [f"{a} × {b} means {small} groups of {big}.",
                f"Count by {big}s, {small} times: {multiples}.",
                f"So {a} × {b} = {product}."]
    tens, ones = _tens_ones(big)
    steps = [f"Split {big} into {tens} + {ones}, then multiply each part by {small}.",
             f"{tens} × {small} = {tens * small}."]
    if ones:
        steps.append(f"{ones} × {small} = {ones * small}.")
        steps.append(f"Add the parts: {tens * small} + {ones * small} = {product}.")
    else:
        steps.append(f"There are no ones left over, so {a} × {b} = {product}.")
    return steps


def _division(total, divisor):
    quotient = total // divisor
    steps = [f"{total} ÷ {divisor} asks: how many groups of {divisor} make {total}?"]
    if quotient <= 10:
        multiples = ", ".join(str(divisor * i) for i in range(1, quotient + 1))
        steps.append(f"Count by {divisor}s until you reach {total}: {multiples}.")
        steps.append(f"That's {quotient} groups, so {total} ÷ {divisor} = {quotient}.")
    else:
        tens = quotient // 10 * 10
        steps.append(f"Try a friendly chunk: {divisor} × {tens} = {divisor * tens}.")
        rest = total - divisor * tens
        steps.append(f"{total} − {divisor * tens} = {rest} left, and {rest} ÷ {divisor} = {quotient - tens}.")
        steps.append(f"Add the groups: {tens} + {quotient - tens} = {quotient}, so {total} ÷ {divisor} = {quotient}.")
    return steps


def _algebra(c, o, t):
    x = (t - o) // c
    return [f"We want x alone. First undo the + {o}: take {o} away from both sides.",
            f"{t} − {o} = {t - o}, so {c}x = {t - o}.",
            f"Now undo the × {c}: divide both sides by {c}.",
            f"{t - o} ÷ {c} = {x}, so x = {x}."]


def steps_for(question):
    """Ordered steps that solve ``question``; the last step always states the answer."""
    prompt = question.prompt
    try:
        if question.topic == "algebra":
            c, o, t = map(int, re.findall(NUMBER, prompt)[:3])
            return _algebra(c, o, t)
        a, b = map(int, re.findall(NUMBER, prompt)[:2])
        builder = {"addition": _addition, "subtraction": _subtraction,
                   "multiplication": _multiplication, "division": _division}.get(question.topic)
        if builder:
            return builder(a, b)
    except (ValueError, ZeroDivisionError):
        pass
    return [question.explanation, f"The answer is {question.answer}."]

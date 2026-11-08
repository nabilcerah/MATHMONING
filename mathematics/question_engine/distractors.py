"""Plausible wrong answers.

Generators pass the results of *real* mistakes (forgetting to carry, reading left to right, adding
the denominators...). This module removes anything equal to the right answer, removes duplicates,
and tops the list up with near-misses so there are always enough options.
"""
from fractions import Fraction

from mathematics.question_engine.model import fmt, normalise_text, parse_number


def numeric_options(answer, mistakes, rng, count=3):
    answer = Fraction(answer)
    picked, seen = [], {answer}
    for value in mistakes:
        if value is None:
            continue
        value = Fraction(value)
        if value in seen:
            continue
        if answer >= 0 and value < 0 and abs(answer) > 2:
            continue  # a negative option for a positive-only question is too easy to rule out
        if answer.denominator == 1 and value.denominator != 1:
            continue  # whole-number answers get whole-number options (a fraction gives the game away)
        seen.add(value)
        picked.append(value)
        if len(picked) == count:
            break
    step = 1 if answer.denominator == 1 else Fraction(1, answer.denominator)
    big = abs(answer) >= 50
    nudges = [step, -step, 2 * step, -2 * step, 10 * step if big else 3 * step, -10 * step if big else -3 * step,
              5 * step, -5 * step]
    rng.shuffle(nudges)
    for nudge in nudges:
        if len(picked) == count:
            break
        value = answer + nudge
        if value in seen or (answer >= 0 and value < 0):
            continue
        seen.add(value)
        picked.append(value)
    while len(picked) < count:  # last resort, never repeats the answer
        value = answer + step * (len(picked) + 7)
        if value not in seen:
            seen.add(value)
            picked.append(value)
    return [fmt(v) for v in picked]


def build_choices(answer_text, wrong, rng, kind="number"):
    """Shuffle the answer in with its distractors (all distinct as numbers or as text)."""
    options, keys = [answer_text], {_key(answer_text, kind)}
    for option in wrong:
        key = _key(option, kind)
        if key in keys:
            continue
        keys.add(key)
        options.append(option)
    rng.shuffle(options)
    return options


def _key(option, kind):
    if kind == "number":
        value = parse_number(option)
        return value if value is not None else normalise_text(option)
    return normalise_text(option)

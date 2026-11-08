"""Quick puzzle formats used as battle attacks (about 1 in 3 ATTACKs).

Each turns a shrine puzzle into a ``MathQuestion`` that fits the battle box. The question's
``topic`` is the skill the puzzle really practises, so learning data stays meaningful:
a balance "? + 7 = 15" is solved by subtracting, so it counts as subtraction.
"""
import random
import uuid

from mathematics import puzzles as P  # target + magic square logic
from mathematics.question_bank import MathQuestion

TIERS = {"easy": 0, "intermediate": 1, "advanced": 2}
FORMAT_LABELS = {"sequence": "SEQUENCE STONES", "balance": "BALANCE SCALE", "target": "TARGET NUMBER",
                 "magic": "MAGIC SQUARE"}
# Which formats can practise each core topic.
FORMATS_FOR_TOPIC = {"addition": ("sequence", "magic"), "subtraction": ("balance", "sequence"),
                     "multiplication": ("target", "sequence"), "division": ("balance",)}
PUZZLE_BONUS_DAMAGE = 4


def _question(topic, difficulty, fmt, prompt, answer, explanation, hint, steps, visual, concept):
    base = {"easy": 6, "intermediate": 9, "advanced": 13}[difficulty] + PUZZLE_BONUS_DAMAGE
    return MathQuestion(uuid.uuid4().hex, topic, difficulty, prompt, str(answer), explanation, hint,
                        f"{FORMAT_LABELS[fmt].title()} Attack", base, concept, tuple(steps), visual, fmt)


def _sequence(rng, difficulty, wanted_topic):
    """Build the sequence style that practises ``wanted_topic``: count on, count back, or double."""
    tier = TIERS[difficulty]
    topic = wanted_topic if wanted_topic in ("addition", "subtraction", "multiplication") else "addition"
    if topic == "addition":
        step = rng.randint(2, 5) if tier == 0 else rng.randint(3, 12)
        first = rng.randint(1, 10 + tier * 20)
        terms = [first + step * i for i in range(5)]
        hint = f"Each stone is {step} more than the one before."
    elif topic == "subtraction":
        step = rng.randint(2, 5) if tier == 0 else rng.randint(3, 9)
        first = step * 5 + rng.randint(5, 20 + tier * 20)
        terms = [first - step * i for i in range(5)]
        hint = f"Each stone is {step} less than the one before."
    else:
        factor = 2 if tier < 2 else rng.choice([2, 3])
        first = rng.randint(1, 3 if tier == 0 else 5)
        terms = [first * factor ** i for i in range(5)]
        hint = f"Each stone is {factor} times the one before."
    shown, answer = terms[:4], terms[4]
    solution = f"The next stone is {answer}."
    return _question(topic, difficulty, "sequence", "Next stone: " + ", ".join(map(str, shown)) + ", ?", answer,
                     solution, hint, [hint, f"{shown[-1]} → {answer}.", solution], ("sequence", tuple(shown)),
                     "patterns")


def _balance(rng, difficulty, wanted_topic):
    """'? + a' practises subtraction, '? − a' addition, and 'n × ?' division."""
    tier = TIERS[difficulty]
    topic = wanted_topic if wanted_topic in ("addition", "subtraction", "division") else "subtraction"
    if topic == "subtraction":
        x, a = rng.randint(2, 12 + tier * 20), rng.randint(2, 15 + tier * 20)
        left, right = f"? + {a}", x + a
        hint, steps = f"Take {a} away from both sides.", [f"{right} − {a} = {x}."]
    elif topic == "addition":
        a = rng.randint(2, 10 + tier * 10)
        x = rng.randint(a + 1, a + 15 + tier * 20)
        left, right = f"? − {a}", x - a
        hint, steps = f"Add {a} back to both sides.", [f"{right} + {a} = {x}."]
    else:
        n = rng.randint(2, 5 if tier == 0 else 9)
        x = rng.randint(2, 10 if tier < 2 else 12)
        left, right = f"{n} × ?", n * x
        hint, steps = f"How many {n}s make {right}? Divide by {n}.", [f"{right} ÷ {n} = {x}."]
    solution = f"? = {x}, because {left.replace('?', str(x))} = {right}."
    return _question(topic, difficulty, "balance", f"Balance it: {left} = {right}", x, solution, hint,
                     [hint] + steps + [solution], ("balance", left, str(right)), "balancing equations")


def _target(rng, difficulty, wanted_topic):
    puzzle = P.target(rng, TIERS[difficulty])
    numbers, goal = puzzle.data["numbers"], puzzle.data["target"]
    prompt = f"Make {goal} from {numbers[0]}, {numbers[1]}, {numbers[2]}"
    return _question("multiplication", difficulty, "target", prompt, goal, puzzle.solution, puzzle.hint,
                     ["Use every number once with + − ×.", puzzle.hint, puzzle.solution],
                     ("target", tuple(numbers), goal), "number sense")


def _magic(rng, difficulty, wanted_topic):
    solution = rng.choice(P._symmetries(P.LO_SHU))
    r, c = rng.randrange(3), rng.randrange(3)
    grid = tuple(tuple(None if (rr, cc) == (r, c) else solution[rr][cc] for cc in range(3)) for rr in range(3))
    row = [v for v in grid[r] if v is not None]
    answer = solution[r][c]
    steps = ["In a magic square every row, column and diagonal adds to 15.",
             f"The row with the gap has {row[0]} and {row[1]}: {row[0]} + {row[1]} = {row[0] + row[1]}.",
             f"15 − {row[0] + row[1]} = {answer}, so the missing number is {answer}."]
    return _question("addition", difficulty, "magic", "Magic square: every line makes 15. What's missing?", answer,
                     steps[-1], "Pick the row with the gap and find what makes 15.", steps, ("magic", grid),
                     "addition facts")


BUILDERS = {"sequence": _sequence, "balance": _balance, "target": _target, "magic": _magic}


def puzzle_for(topic, difficulty, rng=None, avoid=None):
    """A puzzle-format question practising ``topic``, or None if no format fits that topic."""
    rng = rng or random.Random()
    formats = [f for f in FORMATS_FOR_TOPIC.get(topic, ()) if f != avoid] or list(FORMATS_FOR_TOPIC.get(topic, ()))
    if not formats:
        return None
    fmt = rng.choice(formats)
    return BUILDERS[fmt](rng, difficulty, topic)

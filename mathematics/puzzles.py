"""Puzzle shrines: generators and checkers (no drawing here).

Each generator takes a seeded ``random.Random`` and a difficulty ``tier`` (0 easy, 1, 2 hard) and
returns a ``Puzzle``. ``check(puzzle, answer)`` says whether an answer is right; answers are
strings for typed puzzles, a 3x3 grid for the magic square and an (x, y) point for the Star Chart.
"""
import ast
import itertools
import operator
from dataclasses import dataclass, field

KINDS = ("sequence", "balance", "target", "magic", "starchart")


@dataclass
class Puzzle:
    kind: str
    title: str
    prompt: str
    hint: str
    solution: str
    data: dict = field(default_factory=dict)
    answer: object = None


# --------------------------------------------------------------------------- sequence
def sequence(rng, tier=0):
    """What comes next? Skip counting, then step changes, then doubling."""
    style = rng.choice(["add"] if tier == 0 else ["add", "add", "sub"] if tier == 1 else ["add", "sub", "double", "grow"])
    if style == "add":
        step = rng.randint(2, 5) if tier == 0 else rng.randint(3, 12)
        start = rng.randint(1, 10 + tier * 20)
        terms = [start + step * i for i in range(5)]
        hint = f"Each stone is {step} more than the one before."
    elif style == "sub":
        step = rng.randint(2, 9)
        start = step * 6 + rng.randint(5, 30)
        terms = [start - step * i for i in range(5)]
        hint = f"Each stone is {step} less than the one before."
    elif style == "double":
        start = rng.randint(1, 5)
        terms = [start * 2 ** i for i in range(5)]
        hint = "Each stone doubles the one before it."
    else:  # the gap itself grows by one each time
        start, gap = rng.randint(1, 10), rng.randint(1, 3)
        terms = [start]
        for i in range(4):
            terms.append(terms[-1] + gap + i)
        hint = "Look at the gaps between stones: they grow by 1 each time."
    shown, answer = terms[:4], terms[4]
    prompt = "What number goes on the last stone?  " + ",  ".join(map(str, shown)) + ",  ?"
    return Puzzle("sequence", "SEQUENCE STONES", prompt, hint, f"The next stone is {answer}.",
                  {"terms": shown}, str(answer))


# --------------------------------------------------------------------------- balance
def balance(rng, tier=0):
    """Balance the scale: ? + a = total (tier 0), ? − a or n × ? (higher tiers)."""
    style = "add" if tier == 0 else rng.choice(["add", "sub"]) if tier == 1 else rng.choice(["add", "sub", "mul"])
    if style == "add":
        x, a = rng.randint(2, 12 + tier * 20), rng.randint(2, 15 + tier * 20)
        left, right = f"? + {a}", str(x + a)
        hint = f"Take {a} away from both pans: {x + a} − {a}."
    elif style == "sub":
        a = rng.randint(2, 20)
        x = rng.randint(a + 1, a + 30)
        left, right = f"? − {a}", str(x - a)
        hint = f"Add {a} back to both pans: {x - a} + {a}."
    else:
        n, x = rng.randint(2, 9), rng.randint(2, 12)
        left, right = f"{n} × ?", str(n * x)
        hint = f"How many {n}s make {n * x}? Divide: {n * x} ÷ {n}."
    prompt = f"Make the scale balance:   {left}  =  {right}"
    return Puzzle("balance", "BALANCE SCALE", prompt, hint, f"? = {x}, because {left.replace('?', str(x))} = {right}.",
                  {"left": left, "right": right}, str(x))


# --------------------------------------------------------------------------- target
_OPS = {"+": operator.add, "-": operator.sub, "*": operator.mul}


def _expressions(numbers):
    """Every (expression, value) using each number once with + − × (both groupings)."""
    for a, b, c in itertools.permutations(numbers):
        for o1, o2 in itertools.product(_OPS, repeat=2):
            yield f"({a}{o1}{b}){o2}{c}", _OPS[o2](_OPS[o1](a, b), c)
            yield f"{a}{o1}({b}{o2}{c})", _OPS[o1](a, _OPS[o2](b, c))


def target(rng, tier=0):
    """Use all three numbers once with + − × (and brackets) to make the target."""
    hi = (6, 9, 12)[tier]
    while True:
        numbers = sorted(rng.randint(2, hi) for _ in range(3))
        values = {value: expr for expr, value in _expressions(numbers) if 0 < value <= 60 + tier * 60}
        # Prefer targets that need a multiplication, so it isn't just "add them all".
        interesting = [v for v, e in values.items() if "*" in e and v != sum(numbers)]
        if interesting:
            goal = rng.choice(interesting)
            break
    shown = values[goal].replace("*", " × ").replace("-", " − ").replace("+", " + ")
    prompt = f"Use {numbers[0]}, {numbers[1]} and {numbers[2]} once each with + − × to make {goal}."
    hint = "Try multiplying two of the numbers first, then add or take away the third."
    return Puzzle("target", "TARGET NUMBER", prompt, hint, f"One way: {shown} = {goal}.",
                  {"numbers": numbers, "target": goal}, goal)


def evaluate_expression(text, numbers):
    """Safely evaluate a typed expression; it must use exactly ``numbers`` once each. Returns value or None."""
    cleaned = text.replace("x", "*").replace("X", "*").replace("×", "*").replace("−", "-").strip()
    if not cleaned or len(cleaned) > 40:
        return None
    try:
        tree = ast.parse(cleaned, mode="eval")
    except SyntaxError:
        return None
    used = []

    def walk(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            used.append(node.value)
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult):
            left, right = walk(node.left), walk(node.right)
            return {ast.Add: left + right, ast.Sub: left - right, ast.Mult: left * right}[type(node.op)]
        raise ValueError("only whole numbers with + - x are allowed")

    try:
        value = walk(tree.body)
    except (ValueError, RecursionError):
        return None
    return value if sorted(used) == sorted(numbers) else None


# --------------------------------------------------------------------------- magic square
LO_SHU = ((2, 7, 6), (9, 5, 1), (4, 3, 8))


def _symmetries(square):
    grids = []
    grid = [list(row) for row in square]
    for _ in range(4):
        grid = [list(row) for row in zip(*grid[::-1])]  # rotate 90°
        grids.append(grid)
        grids.append([row[::-1] for row in grid])  # mirror
    return grids


def magic(rng, tier=0):
    """Fill the 3x3 square so every row, column and diagonal adds to 15."""
    solution = rng.choice(_symmetries(LO_SHU))
    hidden = (3, 4, 5)[tier]
    cells = rng.sample([(r, c) for r in range(3) for c in range(3)], hidden)
    given = [[None if (r, c) in cells else solution[r][c] for c in range(3)] for r in range(3)]
    prompt = "Fill the empty squares (1 to 9) so every row, column and diagonal adds up to 15."
    hint = "The middle square is always 5. Then find a row that only misses one number."
    return Puzzle("magic", "MAGIC SQUARE", prompt, hint, "Every line adds to 15: "
                  + " / ".join(" ".join(map(str, row)) for row in solution),
                  {"given": given, "solution": solution}, solution)


def magic_ok(grid):
    lines = [list(row) for row in grid] + [list(col) for col in zip(*grid)]
    lines += [[grid[i][i] for i in range(3)], [grid[i][2 - i] for i in range(3)]]
    values = sorted(v for row in grid for v in row if v is not None)
    return values == list(range(1, 10)) and all(sum(line) == 15 for line in lines)


# --------------------------------------------------------------------------- star chart (secret)
def line_rule(m, c):
    """Write y = mx + c the way a maths book would: y = x + 2, y = 2x, y = 3x + 1."""
    slope = "x" if m == 1 else f"{m}x"
    return f"y = {slope}" + (f" + {c}" if c else "")


def starchart(rng, tier=0, round_index=0):
    """Coordinates and straight-line graphs: place the star on the right point of the grid.

    Round 0 plots a point; round 1 follows y = mx + c; round 2 finds where a line meets a height.
    """
    size = 8
    if round_index == 0:
        x, y = rng.randint(1, size - 1), rng.randint(1, size - 1)
        prompt = f"Place the star at ({x}, {y}).  Go {x} across, then {y} up."
        hint = "The first number is how far ACROSS (x), the second is how far UP (y)."
        line = None
    else:
        m, c = rng.choice([(1, 1), (1, 2), (2, 1), (2, 0), (1, 0), (3, 1)])
        if round_index == 1:
            x = rng.randint(1, max(1, (size - 1 - c) // m))
            y = m * x + c
            prompt = f"The comet flies along {line_rule(m, c)}.  Where is it when x = {x}?"
            hint = f"Put x = {x} into the rule: y = {m} × {x}" + (f" + {c}." if c else ".")
        else:
            y = rng.choice([m * x + c for x in range(1, size) if m * x + c < size and m * x + c > c])
            x = (y - c) // m
            prompt = f"The comet flies along {line_rule(m, c)}.  Find the point on its path where y = {y}."
            hint = (f"Undo the rule: take {c} away from {y}, then divide by {m}." if c
                    else f"Undo the rule: divide {y} by {m}.")
        line = (m, c)
    return Puzzle("starchart", "STAR CHART", prompt, hint, f"The star belongs at ({x}, {y}).",
                  {"size": size, "line": line, "round": round_index}, (x, y))


GENERATORS = {"sequence": sequence, "balance": balance, "target": target, "magic": magic, "starchart": starchart}


def check(puzzle, answer):
    if puzzle.kind in ("sequence", "balance"):
        return str(answer).strip() == puzzle.answer
    if puzzle.kind == "target":
        return evaluate_expression(str(answer), puzzle.data["numbers"]) == puzzle.answer
    if puzzle.kind == "magic":
        return magic_ok(answer)
    if puzzle.kind == "starchart":
        return tuple(answer) == tuple(puzzle.answer)
    return False

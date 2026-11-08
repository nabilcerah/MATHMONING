"""Visual hints (bug report: "the hint should not be by words").

``hint_visual(question)`` reads the numbers out of a question and picks a picture that shows the
strategy - hops on a number line, a dot array, fraction bars, a balance scale, a labelled shape,
a pattern with "+d" arrows, a clock. ``draw_visual`` animates it step by step (``age`` = frames
since the hint opened), so the hint is something to watch, not a sentence to read.

The pictures never contain the answer: the final box is always "?".
"""
import math
import re

import pygame

from config import PALETTE
from game.ui import text

NUM = r"(-?\d+)"
MINUS = "[−-]"
STEP = 22          # frames per animation step


def _ints(*values):
    return tuple(int(v) for v in values)


def hint_visual(question):
    """A visual spec tuple for the question, or None when no picture fits."""
    prompt = getattr(question, "prompt", "").replace("−", "-").replace("×", "x").replace("÷", "/")
    topic = getattr(question, "topic", "")
    patterns = [
        (r"^(\d+) \+ (\d+) = \?", lambda a, b: ("hops", int(a), int(b), "+")),
        (r"^(\d+) - (\d+) = \?", lambda a, b: ("gap", int(b), int(a))),
        (r"^(\d+) x (\d+) = \?", lambda a, b: ("array", int(a), int(b))),
        (r"^(\d+) / (\d+) = \?", lambda t, d: ("groups", int(t), int(d))),
        (r"Each of the (\d+) new planks needs (\d+) nails", lambda p, n: ("array", int(p), int(n))),
        (r"^(\d+)/(\d+) of (\d+) = \?", lambda n, d, w: ("bar_of", int(n), int(d), int(w))),
        (r"^(Half|A third|A quarter|A fifth) of (\d+)", lambda name, w: ("bar_of", 1, {"Half": 2, "A third": 3,
                                                                                   "A quarter": 4, "A fifth": 5}[name], int(w))),
        (r"^(\d+)/(\d+) ([+-]) (\d+)/(\d+)", lambda a, b, op, c, d: ("bars", *_ints(a, b, c, d), op)),
        (r"^(\d+)/(\d+) = \?/(\d+)", lambda n, d, big: ("equiv", *_ints(n, d, big))),
        (r"^(\d+)/(\d+) x (\d+)/(\d+)", lambda a, b, c, d: ("bars", *_ints(a, b, c, d), "x")),
        (r"For every (\d+) red gems there are (\d+) blue gems\. With (\d+) red", lambda a, b, n: ("ratio_chips", *_ints(a, b, n))),
        (r"Share (\d+) coins in the ratio (\d+):(\d+)", lambda t, a, b: ("share", *_ints(t, a, b))),
        (r"^(\d+)% of (\d+)", lambda p, n: ("percent", *_ints(p, n))),
        (r"^" + NUM + r" \+ (\d+) = \?", lambda a, b: ("hops", int(a), int(b), "+")),
        (r"^" + NUM + r" - \(-(\d+)\)", lambda a, b: ("hops", int(a), int(b), "+neg")),
        (r"^\((-\d+)\) x \((-\d+)\)", lambda a, b: ("signs", int(a), int(b), "x")),
        (r"^\((-\d+)\) / (\d+)", lambda a, b: ("signs", int(a), int(b), "/")),
        (r"Solve for x: x \+ (\d+) = (\d+)", lambda b, c: ("balance", 1, int(b), int(c))),
        (r"Solve for x: (\d+)x \+ (\d+) = (\d+)", lambda a, b, c: ("balance", *_ints(a, b, c))),
        (r"Simplify: (\d+)x \+ (\d+)x \+ (\d+)", lambda p, q, r: ("tiles", *_ints(p, q, r))),
        (r"x \+ y = " + NUM + r" and x - y = " + NUM, lambda s, d: ("pairs", *_ints(s, d))),
        (r"(\d+) cm by (\d+) cm\. What is its AREA", lambda w, h: ("rect", int(w), int(h), "area")),
        (r"(\d+) cm by (\d+) cm\. What is its PERIMETER", lambda w, h: ("rect", int(w), int(h), "perimeter")),
        (r"deck is (\d+) m long and (\d+) m wide", lambda w, h: ("rect", int(w), int(h), "area")),
        (r"BOTH long sides of the (\d+) m bridge", lambda w: ("rect", int(w), 3, "rails")),
        (r"triangle has base (\d+) cm and height (\d+) cm", lambda b, h: ("triangle", *_ints(b, h))),
        (r"straight line\. One is (\d+)", lambda a: ("line_angle", int(a))),
        (r"triangle has angles (\d+). and (\d+)", lambda a, b: ("tri_angles", *_ints(a, b))),
        (r"cuboid is (\d+) cm x (\d+) cm x (\d+) cm", lambda l, w, h: ("cuboid", *_ints(l, w, h))),
        (r"shorter sides (\d+) cm and (\d+) cm", lambda a, b: ("pythag", *_ints(a, b))),
        (r"What comes next\? (.*), \?", lambda terms: ("sequence", tuple(int(t) for t in terms.split(", ")))),
        (r"term number (\d+) of (.*), \.\.\.", lambda n, terms: ("nth", int(n), tuple(int(t) for t in terms.split(", ")))),
        (r"^(\d+\.\d+|\d+) ([+-]) (\d+\.\d+|\d+) = \?", lambda p, op, q: ("decimal_cols", p, q, op)),
        (r"^(\d+\.\d+) x (\d+) = \?", lambda p, n: ("steps", ("ignore the point", f"{p.replace('.', '')} x {n}",
                                                                 "put 1 decimal place back"))),
        (r"^(\d+\.?\d*) / (0\.\d+) = \?", lambda p, q: ("steps", ("x 10 both numbers",
                                                                       f"{float(p) * 10:g} / {float(q) * 10:g}", "now divide"))),
        (r"^(\d+)/(\d+) / (\d+)/(\d+)", lambda a, b, c, d: ("flip", *_ints(a, b, c, d))),
        (r"^(\d+) pens cost ([\d.]+) coins\. How much do (\d+) pens", lambda n, c, t: ("unitary", int(n), c, int(t))),
        (r"^\((-\d+)\) x (\d+) - \(-(\d+)\)", lambda a, b, c: ("steps", (f"({a}) x {b} first", f"then - (-{c})",
                                                                          "minus a negative = plus"))),
        (r"Solve: (\d+)x ([+-]) (\d+) = (\d*)x ([+-]) (\d+)", lambda a, s1, b, c, s2, d: (
            "balance2", int(a), int(b) * (1 if s1 == "+" else -1), int(c or 1), int(d) * (1 if s2 == "+" else -1))),
        (r"starts at (\d+):(\d+) and lasts (\d+) minutes", lambda h, m, d: ("clock", *_ints(h, m), 0, int(d))),
        (r"leaves at (\d+):(\d+)\. The trip takes (\d+) h (\d+) min", lambda h, m, dh, dm: ("clock", *_ints(h, m, dh, dm))),
    ]
    for pattern, build in patterns:
        match = re.search(pattern, prompt)
        if match:
            try:
                return build(*match.groups())
            except (ValueError, ZeroDivisionError):
                return None
    del topic
    return None


# ------------------------------------------------------------------------------- drawing helpers
def _arc(surface, color, start, end, height, progress=1.0, width=2):
    (x0, y0), (x1, _) = start, end
    points = []
    steps = max(2, int(12 * progress))
    for i in range(steps + 1):
        t = progress * i / steps
        points.append((x0 + (x1 - x0) * t, y0 - height * math.sin(math.pi * t)))
    if len(points) > 1:
        pygame.draw.lines(surface, color, False, points, width)


def _box(surface, rect, fill, border=None, label=None, size=8, label_color=None):
    pygame.draw.rect(surface, fill, rect)
    pygame.draw.rect(surface, border or PALETTE["ink"], rect, 1)
    if label is not None:
        text(surface, str(label), pygame.Rect(rect).center, size, label_color or PALETTE["ink"], center=True)


def _steps(age, count):
    """How many animation steps are showing (loops after a pause so it can be watched again)."""
    cycle = (count + 3) * STEP
    return min(count, (age % cycle) // STEP)


def draw_visual(surface, spec, rect, age):
    """Draw the animated hint ``spec`` inside ``rect``."""
    x, y, w, h = rect
    pygame.draw.rect(surface, PALETTE["ink"], rect)
    pygame.draw.rect(surface, PALETTE["gold"] if (age // 15) % 2 else PALETTE["sky"], rect, 1)
    kind = spec[0]
    painter = globals().get(f"_draw_{kind}")
    if painter:
        painter(surface, spec, pygame.Rect(x + 3, y + 3, w - 6, h - 6), age)


def _draw_hops(surface, spec, r, age):
    start, amount, mode = spec[1], spec[2], spec[3]
    if mode == "+neg":
        amount = abs(amount)
    end = start + amount
    lo, hi = min(start, end, 0 if start < 0 else start), max(start, end)
    span = max(1, hi - lo)
    line_y = r.bottom - 14

    def px(value):
        return r.x + 6 + (value - lo) * (r.w - 12) / span

    pygame.draw.line(surface, PALETTE["cream"], (r.x + 2, line_y), (r.right - 2, line_y), 1)
    for value in {lo, hi, start} | ({0} if lo < 0 < hi else set()):
        pygame.draw.line(surface, PALETTE["cream"], (px(value), line_y - 3), (px(value), line_y + 3))
    text(surface, str(start), (px(start), line_y + 7), 8, PALETTE["gold"], center=True)
    if lo < 0 < hi:
        text(surface, "0", (px(0), line_y + 7), 8, PALETTE["muted"], center=True)
    # Jump to the next ten first, then the rest (the "make a ten" strategy).
    chunks = []
    if mode in ("+", "up", "+neg") and start >= 0 and amount > 10 - start % 10 > 0 and start % 10:
        first = 10 - start % 10
        chunks = [first, amount - first]
    elif start < 0 < end:
        chunks = [-start, end]
    else:
        chunks = [amount]
    shown = _steps(age, len(chunks))
    position = start
    for index, chunk in enumerate(chunks):
        progress = 1.0 if index < shown else (min(1.0, (age % STEP) / STEP) if index == shown else 0)
        if progress <= 0:
            break
        _arc(surface, PALETTE["mint"], (px(position), line_y), (px(position + chunk), line_y), 18 - index * 3, progress)
        if progress >= 1:
            text(surface, f"+{chunk}", ((px(position) + px(position + chunk)) / 2, line_y - 22 + index * 3), 8,
                 PALETTE["mint"], center=True)
        position += chunk
    text(surface, "?", (px(end), line_y + 7), 9, PALETTE["coral"], center=True)
    caption = {"up": "count up", "+neg": "- (-n) = + n"}.get(mode, "add on")
    text(surface, caption, (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_array(surface, spec, r, age):
    rows, cols = spec[1], spec[2]
    if rows * cols > 80 or rows > 12 or cols > 12:   # too many dots: split the big number into tens and ones
        big, small = max(rows, cols), min(rows, cols)
        tens, ones = big // 10 * 10, big % 10
        total_w = r.w - 10
        tens_w = int(total_w * tens / big) if big else 0
        top = r.y + 14
        height = r.h - 26
        shown = _steps(age, 2)
        _box(surface, (r.x + 5, top, tens_w, height), PALETTE["sky"] if shown >= 1 else PALETTE["deep"],
             label=f"{tens}x{small}", size=8)
        if ones:
            _box(surface, (r.x + 5 + tens_w, top, total_w - tens_w, height), PALETTE["gold"] if shown >= 2 else PALETTE["deep"],
                 label=f"{ones}x{small}", size=8)
        text(surface, "split, then add", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)
        text(surface, "+  =  ?", (r.centerx, r.bottom - 5), 8, PALETTE["coral"], center=True)
        return
    size = max(3, min((r.w - 10) // cols, (r.h - 18) // rows))
    shown_rows = min(rows, (age // 8) % (rows + 6))
    for row in range(rows):
        for col in range(cols):
            color = PALETTE["gold"] if row < shown_rows else PALETTE["deep"]
            cx = r.x + 5 + col * size + size // 2
            cy = r.y + 14 + row * size + size // 2
            pygame.draw.circle(surface, color, (cx, cy), max(1, size // 2 - 1))
    text(surface, f"{rows} rows of {cols}", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_groups(surface, spec, r, age):
    total, size = spec[1], spec[2]
    groups = total // size if size else 0
    if total > 60 or groups > 12:
        text(surface, f"{size} x ? = {total}", r.center, 11, PALETTE["gold"], center=True)
        text(surface, "undo the times", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)
        return
    # Show the first couple of groups being made, then "?" - the learner finishes the count.
    drawn = min(groups, 3)
    shown = _steps(age, drawn)
    per_row = drawn + 1
    cell_w = (r.w - 6) // per_row
    _box(surface, (r.x + 3 + drawn * cell_w, r.y + 14, cell_w - 3, 17), PALETTE["deep"], PALETTE["coral"], "...?", 8,
         PALETTE["coral"])
    for g in range(drawn):
        gx = r.x + 3 + (g % per_row) * cell_w
        gy = r.y + 14 + (g // per_row) * 20
        lit = g < shown
        pygame.draw.rect(surface, PALETTE["mint"] if lit else PALETTE["deep"], (gx, gy, cell_w - 3, 17), 1)
        for d in range(size):
            pygame.draw.circle(surface, PALETTE["gold"] if lit else PALETTE["muted"],
                               (gx + 4 + (d % 5) * 5, gy + 5 + (d // 5) * 6), 2)
    text(surface, f"groups of {size}: how many?", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _bar(surface, x, y, w, h, parts, shaded, color):
    parts = max(1, parts)
    for i in range(parts):
        x0 = x + w * i // parts
        x1 = x + w * (i + 1) // parts
        pygame.draw.rect(surface, color if i < shaded else PALETTE["deep"], (x0, y, x1 - x0, h))
        pygame.draw.rect(surface, PALETTE["ink"], (x0, y, x1 - x0, h), 1)


def _draw_bar_of(surface, spec, r, age):
    n, d, whole = spec[1], spec[2], spec[3]
    shown = _steps(age, 2)
    _bar(surface, r.x + 4, r.y + 18, r.w - 8, 16, d, d if shown >= 1 else 0, PALETTE["sky"])
    text(surface, f"{whole} split into {d}", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)
    if shown >= 2:
        _bar(surface, r.x + 4, r.y + 40, r.w - 8, 16, d, n, PALETTE["gold"])
        text(surface, f"take {n} part" + ("s" if n > 1 else ""), (r.centerx, r.bottom - 4), 8, PALETTE["gold"], center=True)


def _draw_bars(surface, spec, r, age):
    a, b, c, d, op = spec[1:]
    lcm = b * d // math.gcd(b, d)
    shown = _steps(age, 3)
    width = r.w - 30
    _bar(surface, r.x + 26, r.y + 14, width, 10, b, a, PALETTE["gold"])
    _bar(surface, r.x + 26, r.y + 28, width, 10, d, c, PALETTE["sky"])
    text(surface, f"{a}/{b}", (r.x + 2, r.y + 14), 8, PALETTE["gold"])
    text(surface, f"{c}/{d}", (r.x + 2, r.y + 28), 8, PALETTE["sky"])
    if op != "x" and shown >= 1:
        _bar(surface, r.x + 26, r.y + 44, width, 10, lcm, a * lcm // b, PALETTE["gold"])
        _bar(surface, r.x + 26, r.y + 56, width, 10, lcm, c * lcm // d, PALETTE["sky"])
        text(surface, f"/{lcm}", (r.x + 2, r.y + 50), 8, PALETTE["mint"])
        caption = "same-size pieces first"
    else:
        caption = "tops x tops, bottoms x bottoms" if op == "x" else "different-size pieces..."
    text(surface, caption, (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_equiv(surface, spec, r, age):
    n, d, big = spec[1:]
    shown = _steps(age, 2)
    _bar(surface, r.x + 4, r.y + 16, r.w - 8, 14, d, n, PALETTE["gold"])
    if shown >= 1:
        _bar(surface, r.x + 4, r.y + 38, r.w - 8, 14, big, 0, PALETTE["gold"])
        text(surface, f"cut each piece into {big // d}", (r.centerx, r.bottom - 4), 8, PALETTE["mint"], center=True)
    text(surface, "same amount, smaller pieces", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_ratio_chips(surface, spec, r, age):
    a, b, n = spec[1:]
    groups = n // a if a else 0
    shown = _steps(age, min(groups, 6))
    for g in range(min(groups, 6)):
        gx = r.x + 3 + g * ((r.w - 6) // max(1, min(groups, 6)))
        lit = g < shown
        for i in range(a):
            pygame.draw.circle(surface, PALETTE["coral"] if lit else PALETTE["deep"], (gx + 4, r.y + 18 + i * 6), 2)
        for i in range(b):
            pygame.draw.circle(surface, PALETTE["sky"] if lit else PALETTE["deep"], (gx + 10, r.y + 18 + i * 6), 2)
    text(surface, f"{a} red : {b} blue, again and again", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_share(surface, spec, r, age):
    total, a, b = spec[1:]
    shown = _steps(age, 2)
    _bar(surface, r.x + 4, r.y + 18, r.w - 8, 16, a + b, a if shown >= 1 else 0, PALETTE["gold"])
    text(surface, f"{a} + {b} = {a + b} shares", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)
    if shown >= 2:
        text(surface, f"each share = {total} / {a + b}", (r.centerx, r.bottom - 6), 8, PALETTE["mint"], center=True)


def _draw_percent(surface, spec, r, age):
    p, n = spec[1:]
    shown = min(10, (age // 6) % 22)
    _bar(surface, r.x + 4, r.y + 18, r.w - 8, 16, 10, min(shown, round(p / 10)), PALETTE["gold"])
    text(surface, f"each box = 10% = {n / 10:g}", (r.centerx, r.bottom - 6), 8, PALETTE["mint"], center=True)
    text(surface, "100% split into 10", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_signs(surface, spec, r, age):
    rows = (("+", "+", "+"), ("-", "-", "+"), ("+", "-", "-"), ("-", "+", "-"))
    a, b = spec[1], spec[2]
    pick = ("-" if a < 0 else "+", "-" if b < 0 else "+")
    for i, (s1, s2, out) in enumerate(rows):
        y = r.y + 14 + i * 11
        lit = (s1, s2) == pick and (age // 20) % 2
        text(surface, f"{s1} {spec[3]} {s2}  =  {out}", (r.centerx, y), 9, PALETTE["gold"] if lit else PALETTE["muted"],
             center=True)
    text(surface, "same signs: +   different: -", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _scale(surface, cx, y, left, right, tilt=0):
    pygame.draw.line(surface, PALETTE["cream"], (cx, y), (cx, y + 26), 2)
    pygame.draw.line(surface, PALETTE["cream"], (cx - 46, y + tilt), (cx + 46, y - tilt), 2)
    for side, items in ((-1, left), (1, right)):
        px = cx + side * 34
        pygame.draw.line(surface, PALETTE["muted"], (px - 14, y + 14 - side * tilt), (px + 14, y + 14 - side * tilt))
        offset = 0
        for label, color in items:
            width = 7 + 4 * len(label)
            _box(surface, (px - 14 + offset, y + 4 - side * tilt, width, 10), color, label=label, size=7)
            offset += width + 1


def _draw_balance(surface, spec, r, age):
    a, b, c = spec[1:]
    shown = _steps(age, 2)
    left = [("x", PALETTE["gold"])] * min(a, 4) + ([(str(b), PALETTE["sky"])] if shown < 1 else [])
    right = [(str(c) if shown < 1 else f"{c}-{b}", PALETTE["sky"] if shown < 1 else PALETTE["mint"])]
    _scale(surface, r.centerx, r.y + 22, left, right)
    caption = "keep it balanced" if shown < 1 else (f"take {b} off BOTH sides" if shown < 2 or a == 1
                                                    else f"then share by {a}")
    text(surface, caption, (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_tiles(surface, spec, r, age):
    p, q, k = spec[1:]
    shown = _steps(age, 1)
    x0 = r.x + 4
    for i in range(p + q):
        color = PALETTE["gold"] if (i < p or shown) else PALETTE["sky"]
        offset = i * 9 if shown else i * 9 + (6 if i >= p else 0)
        _box(surface, (x0 + offset, r.y + 20, 8, 12), color, label="x", size=7)
    _box(surface, (r.right - 22, r.y + 20, 18, 12), PALETTE["coral"], label=str(k), size=7)
    text(surface, "x tiles join together", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_pairs(surface, spec, r, age):
    s, d = spec[1:]
    shown = _steps(age, 2)
    text(surface, f"x + y = {s}", (r.centerx, r.y + 16), 9, PALETTE["gold"], center=True)
    text(surface, f"x - y = {d}", (r.centerx, r.y + 28), 9, PALETTE["sky"], center=True)
    if shown >= 1:
        pygame.draw.line(surface, PALETTE["cream"], (r.x + 20, r.y + 36), (r.right - 20, r.y + 36))
        text(surface, f"2x = {s} + {d}", (r.centerx, r.y + 44), 9, PALETTE["mint"], center=True)
    text(surface, "add them: +y and -y cancel", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_rect(surface, spec, r, age):
    w, h, mode = spec[1:]
    unit = max(3, min((r.w - 24) // max(1, w), (r.h - 26) // max(1, h)))
    bw, bh = w * unit, h * unit
    x0, y0 = r.centerx - bw // 2, r.y + 14 + (r.h - 26 - bh) // 2
    pygame.draw.rect(surface, PALETTE["deep"], (x0, y0, bw, bh))
    if mode == "area":
        filled = min(w * h, (age // 3) % (w * h + 30))
        for i in range(filled):
            pygame.draw.rect(surface, PALETTE["sky"], (x0 + (i % w) * unit + 1, y0 + (i // w) * unit + 1, unit - 1, unit - 1))
        caption = f"{h} rows of {w} squares"
    else:
        progress = (age % 120) / 120
        perimeter = 2 * (bw + bh)
        dist = progress * perimeter
        points = [(x0, y0), (x0 + bw, y0), (x0 + bw, y0 + bh), (x0, y0 + bh), (x0, y0)]
        if mode == "rails":
            points = [(x0, y0), (x0 + bw, y0)]
            dist = progress * bw * 2
            pygame.draw.line(surface, PALETTE["gold"], (x0, y0), (x0 + min(bw, dist), y0), 2)
            if dist > bw:
                pygame.draw.line(surface, PALETTE["gold"], (x0, y0 + bh), (x0 + dist - bw, y0 + bh), 2)
        else:
            walked = 0
            for (ax, ay), (bx, by) in zip(points, points[1:]):
                seg = abs(bx - ax) + abs(by - ay)
                if walked + seg <= dist:
                    pygame.draw.line(surface, PALETTE["gold"], (ax, ay), (bx, by), 2)
                elif walked < dist:
                    t = (dist - walked) / seg
                    pygame.draw.line(surface, PALETTE["gold"], (ax, ay), (ax + (bx - ax) * t, ay + (by - ay) * t), 2)
                walked += seg
        caption = "walk all the way round" if mode == "perimeter" else "a rail on each long side"
    pygame.draw.rect(surface, PALETTE["cream"], (x0, y0, bw, bh), 1)
    text(surface, str(w), (r.centerx, y0 - 5), 8, PALETTE["cream"], center=True)
    text(surface, str(h), (x0 + bw + 7, y0 + bh // 2), 8, PALETTE["cream"], center=True)
    text(surface, caption, (r.centerx, r.bottom - 4), 8, PALETTE["sky"], center=True)


def _draw_triangle(surface, spec, r, age):
    base, height = spec[1:]
    x0, y0 = r.x + 12, r.bottom - 14
    bw, bh = r.w - 30, r.h - 28
    show_rect = (age // 40) % 2 == 0
    if show_rect:
        pygame.draw.rect(surface, PALETTE["deep"], (x0, y0 - bh, bw, bh))
        pygame.draw.rect(surface, PALETTE["muted"], (x0, y0 - bh, bw, bh), 1)
    pygame.draw.polygon(surface, PALETTE["sky"], [(x0, y0), (x0 + bw, y0), (x0 + bw // 2, y0 - bh)])
    text(surface, f"b={base}", (r.centerx, y0 + 6), 8, PALETTE["cream"], center=True)
    text(surface, f"h={height}", (x0 + bw + 8, y0 - bh // 2), 8, PALETTE["cream"], center=True)
    text(surface, "half of the rectangle" if show_rect else "triangle = 1/2 b x h", (r.centerx, r.y + 4), 8,
         PALETTE["sky"], center=True)


def _draw_line_angle(surface, spec, r, age):
    a = spec[1]
    cx, cy, rad = r.centerx, r.bottom - 12, min(r.w // 2 - 8, r.h - 20)
    pygame.draw.line(surface, PALETTE["cream"], (cx - rad - 6, cy), (cx + rad + 6, cy), 2)
    angle = math.radians(180 - a)
    end = (cx + rad * math.cos(angle), cy - rad * math.sin(angle))
    pygame.draw.line(surface, PALETTE["cream"], (cx, cy), end, 2)
    text(surface, f"{a}", (cx + 16 * math.cos(math.radians(180 - a / 2)) - 4, cy - 12), 8, PALETTE["gold"], center=True)
    text(surface, "?", (cx + 16, cy - 8), 9, PALETTE["coral"], center=True)
    text(surface, "a straight line is 180", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_tri_angles(surface, spec, r, age):
    a, b = spec[1:]
    p1, p2, p3 = (r.x + 8, r.bottom - 8), (r.right - 8, r.bottom - 8), (r.centerx - 6, r.y + 18)
    pygame.draw.polygon(surface, PALETTE["deep"], [p1, p2, p3])
    pygame.draw.polygon(surface, PALETTE["cream"], [p1, p2, p3], 1)
    text(surface, str(a), (p1[0] + 16, p1[1] - 6), 8, PALETTE["gold"], center=True)
    text(surface, str(b), (p2[0] - 16, p2[1] - 6), 8, PALETTE["gold"], center=True)
    text(surface, "?", (p3[0], p3[1] + 12), 9, PALETTE["coral"], center=True)
    text(surface, "all three make 180", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_cuboid(surface, spec, r, age):
    l, w, h = spec[1:]
    layers = min(h, (age // 12) % (h + 4))
    cell = max(3, min(10, (r.w - 30) // max(1, l)))
    for layer in range(layers):
        y = r.bottom - 10 - layer * (cell + 1)
        for i in range(l):
            pygame.draw.rect(surface, PALETTE["sky"], (r.x + 10 + i * cell, y - cell, cell - 1, cell - 1))
    text(surface, f"{l} x {w} on each layer, {h} layers", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_pythag(surface, spec, r, age):
    a, b = spec[1:]
    shown = _steps(age, 2)
    ox, oy = r.x + 18, r.bottom - 10                       # the right angle
    scale = min((r.w - 60) / b, (r.h - 26) / a) if a and b else 1
    pa, pb = a * scale, b * scale
    pygame.draw.polygon(surface, PALETTE["deep"], [(ox, oy), (ox + pb, oy), (ox, oy - pa)])
    pygame.draw.polygon(surface, PALETTE["cream"], [(ox, oy), (ox + pb, oy), (ox, oy - pa)], 1)
    pygame.draw.rect(surface, PALETTE["cream"], (ox, oy - 5, 5, 5), 1)
    text(surface, str(a), (ox - 7, oy - pa / 2), 8, PALETTE["gold"], center=True)
    text(surface, str(b), (ox + pb / 2, oy + 5), 8, PALETTE["sky"], center=True)
    text(surface, "?", (ox + pb / 2 + 4, oy - pa / 2 - 4), 10, PALETTE["coral"], center=True)
    lines = [f"{a}² + {b}²", "= c²", "c = square root"]
    for i, line in enumerate(lines[:shown + 1]):
        text(surface, line, (r.right - 30, r.y + 18 + i * 12), 8, PALETTE["mint"], center=True)
    text(surface, "square, add, then root", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_sequence(surface, spec, r, age):
    terms = list(spec[1]) + ["?"]
    shown = _steps(age, len(terms) - 1)
    width = (r.w - 4) // len(terms)
    for i, value in enumerate(terms):
        bx = r.x + 2 + i * width
        _box(surface, (bx, r.y + 26, width - 4, 14), PALETTE["coral"] if value == "?" else PALETTE["cream"],
             label=value, size=8)
        if i and i <= shown:
            diff = (terms[i] - terms[i - 1]) if value != "?" else None
            label = f"{diff:+d}" if diff is not None else "?"
            _arc(surface, PALETTE["mint"], (bx - width + width // 2, r.y + 26), (bx + width // 2 - 4, r.y + 26), 8)
            text(surface, label, (bx - 2, r.y + 14), 7, PALETTE["mint"], center=True)
    text(surface, "find the jump", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_nth(surface, spec, r, age):
    n, terms = spec[1], list(spec[2])
    d = terms[1] - terms[0]
    _draw_sequence(surface, ("sequence", tuple(terms[:3])), pygame.Rect(r.x, r.y, r.w, r.h - 14), age)
    text(surface, f"term {n} = {terms[0]} + {d} x ({n} - 1)", (r.centerx, r.bottom - 5), 8, PALETTE["gold"], center=True)


def _draw_clock(surface, spec, r, age):
    hour, minute, dh, dm = spec[1:]
    total = dh * 60 + dm
    cx, cy, rad = r.x + 26, r.centery + 4, min(22, r.h // 2 - 4)
    # Only the first step is shown - counting on to the next hour - so the clock never gives away the answer.
    to_hour = (60 - minute) % 60 or 60
    progress = (age % 160) / 120
    moved = min(total, to_hour, int(to_hour * min(1.0, progress)))
    now = hour * 60 + minute + moved
    pygame.draw.circle(surface, PALETTE["cream"], (cx, cy), rad)
    pygame.draw.circle(surface, PALETTE["ink"], (cx, cy), rad, 2)
    m_angle = math.radians((now % 60) * 6)
    h_angle = math.radians(((now // 60) % 12) * 30 + (now % 60) * 0.5)
    pygame.draw.line(surface, PALETTE["ink"], (cx, cy), (cx + math.sin(h_angle) * rad * 0.5, cy - math.cos(h_angle) * rad * 0.5), 3)
    pygame.draw.line(surface, PALETTE["coral"], (cx, cy), (cx + math.sin(m_angle) * rad * 0.8, cy - math.cos(m_angle) * rad * 0.8), 2)
    text(surface, f"start {hour:02d}:{minute:02d}", (r.x + 54, r.y + 16), 8, PALETTE["gold"])
    text(surface, f"+{dh} h" if dh else "", (r.x + 54, r.y + 28), 8, PALETTE["sky"])
    text(surface, f"+{dm} min" if dm else f"+{total} min", (r.x + 54, r.y + 40), 8, PALETTE["sky"])
    text(surface, f"{to_hour} min to the next hour", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_decimal_cols(surface, spec, r, age):
    p, q, op = spec[1:]
    places = max(len(v.split(".")[1]) if "." in v else 0 for v in (p, q))

    def padded(value):
        whole, _, frac = value.partition(".")
        return whole.rjust(3) + "." + frac.ljust(places, "0")

    shown = _steps(age, 2)
    rows = (padded(p), op + padded(q)[1:] if len(padded(q)) > 1 else padded(q))
    for i, row in enumerate((padded(p), padded(q))):
        text(surface, (op if i else " ") + " " + (row if shown >= 1 else (p if i == 0 else q)), (r.x + 20, r.y + 16 + i * 12),
             10, PALETTE["cream"])
    if shown >= 1:
        dot_x = r.x + 20 + 6 * 6
        pygame.draw.line(surface, PALETTE["gold"], (dot_x, r.y + 14), (dot_x, r.y + 42), 1)
        pygame.draw.line(surface, PALETTE["cream"], (r.x + 16, r.y + 42), (r.right - 16, r.y + 42))
        text(surface, "?", (r.centerx, r.y + 50), 10, PALETTE["coral"], center=True)
    del rows
    text(surface, "line up the points", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_steps(surface, spec, r, age):
    steps = spec[1]
    shown = _steps(age, len(steps))
    for i, step in enumerate(steps[:max(1, shown + 1)]):
        y = r.y + 6 + i * 18
        lit = i <= shown
        _box(surface, (r.x + 4, y, r.w - 8, 14), PALETTE["deep"], PALETTE["gold"] if lit else PALETTE["muted"])
        text(surface, f"{i + 1}. {step}", (r.x + 8, y + 3), 8, PALETTE["cream"] if lit else PALETTE["muted"])


def _draw_flip(surface, spec, r, age):
    a, b, c, d = spec[1:]
    flipped = (age // 30) % 2
    text(surface, f"{a}/{b}", (r.x + 22, r.y + 26), 11, PALETTE["gold"], center=True)
    text(surface, "/" if not flipped else "x", (r.x + 48, r.y + 26), 11, PALETTE["cream"], center=True)
    text(surface, f"{c}/{d}" if not flipped else f"{d}/{c}", (r.x + 76, r.y + 26), 11,
         PALETTE["sky"] if not flipped else PALETTE["mint"], center=True)
    _arc(surface, PALETTE["mint"], (r.x + 68, r.y + 20), (r.x + 86, r.y + 20), 8)
    text(surface, "divide = flip and multiply", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_unitary(surface, spec, r, age):
    count, cost, target = spec[1:]
    shown = _steps(age, 2)
    for i in range(min(count, 6)):
        _box(surface, (r.x + 6 + i * 12, r.y + 16, 9, 12), PALETTE["sky"])
    text(surface, f"= {cost}", (r.x + 12 + min(count, 6) * 12, r.y + 18), 8, PALETTE["cream"])
    if shown >= 1:
        _box(surface, (r.x + 6, r.y + 36, 9, 12), PALETTE["gold"])
        text(surface, f"= {cost} / {count}", (r.x + 20, r.y + 38), 8, PALETTE["gold"])
    if shown >= 2:
        text(surface, f"then x {target}", (r.x + 20, r.y + 52), 8, PALETTE["mint"])
    text(surface, "find ONE first", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)


def _draw_balance2(surface, spec, r, age):
    a, b, c, d = spec[1:]
    shown = _steps(age, 2)
    left_x = a - (c if shown >= 1 else 0)
    right_x = 0 if shown >= 1 else c
    left = [("x", PALETTE["gold"])] * min(left_x, 4) + [(f"{b:+d}", PALETTE["sky"])]
    right = [("x", PALETTE["gold"])] * min(right_x, 3) + [(f"{d:+d}", PALETTE["sky"])]
    _scale(surface, r.centerx, r.y + 22, left, right)
    text(surface, "x's to one side first" if shown < 1 else f"took {c}x off both sides", (r.centerx, r.y + 4), 8,
         PALETTE["sky"], center=True)


def _draw_gap(surface, spec, r, age):
    """Subtraction as a gap to measure: count up from the smaller number. Only the first jump (to the
    next ten) is labelled - the rest of the gap is the learner's to find."""
    low, high = spec[1], spec[2]
    line_y = r.bottom - 14
    span = max(1, high - low)

    def px(value):
        return r.x + 8 + (value - low) * (r.w - 16) / span

    pygame.draw.line(surface, PALETTE["cream"], (r.x + 2, line_y), (r.right - 2, line_y), 1)
    for value in (low, high):
        pygame.draw.line(surface, PALETTE["cream"], (px(value), line_y - 3), (px(value), line_y + 3))
        text(surface, str(value), (px(value), line_y + 7), 8, PALETTE["gold"], center=True)
    next_ten = (low // 10 + 1) * 10
    shown = _steps(age, 2)
    if low % 10 and next_ten < high:
        progress = 1.0 if shown >= 1 else min(1.0, (age % STEP) / STEP)
        _arc(surface, PALETTE["mint"], (px(low), line_y), (px(next_ten), line_y), 14, progress)
        if shown >= 1:
            text(surface, f"+{next_ten - low}", ((px(low) + px(next_ten)) / 2, line_y - 20), 8, PALETTE["mint"], center=True)
            pygame.draw.line(surface, PALETTE["cream"], (px(next_ten), line_y - 3), (px(next_ten), line_y + 3))
        start = next_ten
    else:
        start = low
    if shown >= 2 or start == low:
        _arc(surface, PALETTE["coral"], (px(start), line_y), (px(high), line_y), 18)
        text(surface, "+?", ((px(start) + px(high)) / 2, line_y - 24), 9, PALETTE["coral"], center=True)
    text(surface, "how far apart? count up", (r.centerx, r.y + 4), 8, PALETTE["sky"], center=True)

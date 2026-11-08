"""Geometry (perimeter and area) and angles."""
from fractions import Fraction

from mathematics.question_engine.generators import Draft


def geometry(rng, level):
    if level <= 1:
        w, h = rng.randint(2, 9), rng.randint(2, 9)
        answer = 2 * (w + h)
        return Draft(f"A rectangle is {w} cm by {h} cm. What is its perimeter?", answer, [w * h, w + h, 2 * w + h],
                     f"Perimeter is the distance all the way round: {w} + {h} + {w} + {h} = {answer} cm.",
                     "Walk around all four sides and add them.", f"2*({w}+{h})", visual=("rect", w, h))
    if level == 2:
        w, h = rng.randint(3, 12), rng.randint(3, 12)
        answer = w * h
        return Draft(f"A rectangle is {w} m by {h} m. What is its area?", answer, [2 * (w + h), w + h, answer + w],
                     f"Area counts the square units inside: {w} × {h} = {answer} m².",
                     "Area = length × width.", f"{w}*{h}", visual=("rect", w, h))
    if level == 3:
        b, h = rng.randint(2, 12) * 2, rng.randint(3, 14)
        answer = b * h // 2
        return Draft(f"A triangle has base {b} cm and height {h} cm. What is its area?", answer, [b * h, b + h, answer + h],
                     f"A triangle is half of a rectangle: ½ × {b} × {h} = {answer} cm².",
                     "Area of a triangle = ½ × base × height.", f"{b}*{h}/2")
    if level == 4:
        a, b, h = rng.randint(3, 10), rng.randint(11, 20), rng.randint(2, 10) * 2
        answer = Fraction((a + b) * h, 2)
        return Draft(f"A trapezium has parallel sides {a} m and {b} m and height {h} m. What is its area?", answer,
                     [(a + b) * h, a * b, Fraction(a * h, 2) + b],
                     f"Average the parallel sides and multiply by the height: ({a} + {b}) ÷ 2 × {h} = {answer} m².",
                     "Area = ½ × (a + b) × h.", f"({a}+{b})/2*{h}")
    w, h, cut_w, cut_h = rng.randint(8, 15), rng.randint(8, 15), rng.randint(2, 5), rng.randint(2, 5)
    answer = w * h - cut_w * cut_h
    return Draft(f"An L-shape is a {w} × {h} rectangle with a {cut_w} × {cut_h} corner cut out. What is its area?",
                 answer, [w * h, w * h + cut_w * cut_h, 2 * (w + h)],
                 f"Whole rectangle {w * h}, minus the missing corner {cut_w * cut_h}: {answer} square units.",
                 "Find the big rectangle, then subtract the missing piece.", f"{w}*{h}-{cut_w}*{cut_h}")


def angles(rng, level):
    if level <= 1:
        a = rng.randint(2, 16) * 10
        answer = 180 - a
        return Draft(f"Two angles make a straight line. One is {a}°. What is the other?", answer, [360 - a, 90 - a if a < 90 else a - 90, a],
                     f"Angles on a straight line add to 180°: 180 − {a} = {answer}°.",
                     "A straight line is half a turn: 180°.", f"180-{a}", tags=("angles",))
    if level == 2:
        a, b = rng.randint(30, 80), rng.randint(30, 80)
        answer = 180 - a - b
        return Draft(f"A triangle has angles {a}° and {b}°. What is the third angle?", answer, [360 - a - b, a + b, 90 - abs(a - b)],
                     f"Triangle angles add to 180°: 180 − {a} − {b} = {answer}°.",
                     "All three angles of any triangle add to 180°.", f"180-{a}-{b}", tags=("angles",))
    if level == 3:
        a, b = rng.randint(60, 150), rng.randint(40, 130)
        answer = 360 - a - b
        return Draft(f"Three angles meet at a point. Two are {a}° and {b}°. What is the third?", answer,
                     [180 - a - b if a + b < 180 else a + b - 180, a + b, answer + 10],
                     f"Angles around a point add to 360°: 360 − {a} − {b} = {answer}°.",
                     "A full turn is 360°.", f"360-{a}-{b}", tags=("angles",))
    if level == 4:
        n = rng.choice([3, 4, 5, 6, 8, 9, 10, 12])
        answer = Fraction((n - 2) * 180, n)
        names = {3: "triangle", 4: "square", 5: "pentagon", 6: "hexagon", 8: "octagon", 9: "nonagon",
                 10: "decagon", 12: "dodecagon"}
        return Draft(f"Each interior angle of a regular {names[n]} ({n} sides) is how many degrees?", answer,
                     [Fraction(360, n), (n - 2) * 180, answer + 10],
                     f"Interior angles sum to (n − 2) × 180 = {(n - 2) * 180}°. Shared by {n} angles: {answer}°.",
                     "Sum of interior angles = (sides − 2) × 180.", f"({n}-2)*180/{n}", tags=("angles",))
    n = rng.randint(5, 14)
    answer = (n - 2) * 180
    return Draft(f"What is the sum of the interior angles of a polygon with {n} sides?", answer,
                 [n * 180, (n - 1) * 180, 360 * (n - 2)],
                 f"A {n}-sided polygon splits into {n - 2} triangles: {n - 2} × 180 = {answer}°.",
                 "Count the triangles you can draw from one corner.", f"({n}-2)*180", tags=("angles",))

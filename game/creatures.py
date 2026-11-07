"""Original MATHMON creature definitions and pixel sprites."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CreatureSpec:
    name: str
    element: str
    hp: int
    attack: int
    accent: tuple[int, int, int]
    base: tuple[int, int, int]
    skills: tuple[str, ...]
    evolution_level: int = 8


STARTERS = {
    "PYROX": CreatureSpec("PYROX", "FIRE", 34, 8, (250, 151, 67), (205, 77, 58), ("Addition Spark", "Multiplication Flare")),
    "AQUABIT": CreatureSpec("AQUABIT", "WATER", 38, 7, (126, 212, 221), (62, 137, 180), ("Subtraction Splash", "Division Current")),
    "TERRABIT": CreatureSpec("TERRABIT", "EARTH", 42, 6, (203, 190, 119), (115, 147, 85), ("Subtraction Shield", "Multiplication Boulder")),
}

EVOLUTIONS = {
    "PYROX": CreatureSpec("PYRONYX", "FIRE", 48, 11, (255, 218, 105), (173, 63, 78), ("Solar Addition", "Multiplication Nova"), 99),
    "AQUABIT": CreatureSpec("AQUACREST", "WATER", 52, 10, (171, 241, 232), (45, 118, 167), ("Tidal Subtraction", "Division Surge"), 99),
    "TERRABIT": CreatureSpec("TERRAVOLT", "EARTH", 57, 9, (229, 209, 139), (93, 123, 74), ("Subtraction Shield", "Multiplication Boulder"), 99),
}


def creature_spec(name: str, level: int = 1) -> CreatureSpec:
    """Return the earned form for a starter while retaining its save identity."""
    base = STARTERS.get(name)
    if base and level >= base.evolution_level:
        return EVOLUTIONS[name]
    for starter, evolved in EVOLUTIONS.items():
        if name == evolved.name:
            return evolved
    return base or STARTERS["PYROX"]

ENEMIES = (
    CreatureSpec("MOSSNIP", "LEAF", 24, 5, (163, 205, 113), (69, 127, 88), ("Vine Tap",)),
    CreatureSpec("CINDERKIT", "EMBER", 26, 6, (255, 184, 97), (193, 88, 69), ("Warm Pounce",)),
    CreatureSpec("DROPLET", "WATER", 28, 5, (162, 221, 224), (67, 139, 179), ("Bubble Bop",)),
    CreatureSpec("ARITHMETIC BEAST", "BOSS", 58, 7, (255, 210, 104), (117, 72, 129), ("Number Roar",), 99),
)


def pixel_monster(surface, x: int, y: int, spec: CreatureSpec, scale: int = 2, flip: bool = False) -> None:
    """Draw a chunky, original creature from rectangles (no external assets)."""
    import pygame

    # 16x16 bit silhouette; 1 = body, 2 = accent, 3 = eye, 4 = shadow.
    shape = [
        "0000000011000000", "0000001122110000", "0000112222221100", "0011222222222210",
        "0112222222222221", "1122222222222221", "1222222222222211", "1222222222222110",
        "1222222222222110", "0122222222222100", "0012222222221000", "0001222222210000",
        "0001122222110000", "0000110001100000", "0001100000110000", "0011000000011000",
    ]
    colors = {"1": spec.base, "2": spec.accent, "3": (255, 249, 220), "4": tuple(max(0, c - 42) for c in spec.base)}
    px = x
    for row_index, row in enumerate(shape):
        for col_index, cell in enumerate(row):
            if cell == "0":
                continue
            col = 15 - col_index if flip else col_index
            # Eyes and feet use a contrasting outline for crisp low-res silhouettes.
            actual = "3" if (row_index == 6 and col_index in (4, 11)) else ("4" if row_index >= 13 else cell)
            pygame.draw.rect(surface, colors[actual], (px + col * scale, y + row_index * scale, scale, scale))
    # Distinctive silhouettes and elemental marks keep the trio recognizable.
    if spec.element == "FIRE" or spec.element == "EMBER":
        pygame.draw.rect(surface, (255, 215, 102), (px + 13 * scale, y + 9 * scale, 3 * scale, scale))
        pygame.draw.rect(surface, (245, 126, 73), (px + 15 * scale, y + 7 * scale, 2 * scale, 3 * scale))
    elif spec.element == "WATER":
        pygame.draw.rect(surface, (174, 235, 227), (px + 2 * scale, y + 4 * scale, 2 * scale, 5 * scale))
        pygame.draw.rect(surface, (174, 235, 227), (px + 12 * scale, y + 4 * scale, 2 * scale, 5 * scale))
    elif spec.element == "EARTH":
        pygame.draw.rect(surface, (226, 213, 159), (px + 2 * scale, y + 2 * scale, 2 * scale, 4 * scale))
        pygame.draw.rect(surface, (226, 213, 159), (px + 12 * scale, y + 2 * scale, 2 * scale, 4 * scale))
    elif spec.element == "BOSS":
        pygame.draw.rect(surface, (255, 222, 125), (px + 5 * scale, y, 2 * scale, 4 * scale))
        pygame.draw.rect(surface, (255, 222, 125), (px + 10 * scale, y, 2 * scale, 4 * scale))

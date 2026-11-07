"""MATHMON creature definitions.

Creatures with a ``sprite`` use the processed art in assets/sprites/monsters (drawn by
``draw_creature``). ``pixel_monster`` remains as a code-drawn fallback for any creature
without art.
"""
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
    topic: str = ""            # the maths skill this creature is linked to (bond challenges, friend bonus)
    habitat: tuple[str, ...] = ()  # overworld area ids whose tall grass it lives in
    shape: str = "blob"
    blurb: str = ""
    rarity: int = 10           # relative encounter weight inside its habitat
    sprite: str = ""           # folder name under assets/sprites/monsters
    size: float = 1.0          # drawing scale (evolved forms stand taller)


STARTERS = {
    "PYRON": CreatureSpec("PYRON", "FIRE", 34, 8, (250, 151, 67), (205, 77, 58), ("Addition Spark", "Multiplication Flare"),
                          8, "addition", (), "blob", "A bold little dragon. Its belly glows with a plus sign.",
                          sprite="PYRON"),
    "AQUABIT": CreatureSpec("AQUABIT", "WATER", 38, 7, (126, 212, 221), (62, 137, 180), ("Subtraction Splash", "Division Current"),
                            8, "subtraction", (), "blob", "A calm turtle. The minus mark on its shell shines when it thinks.",
                            sprite="AQUABIT"),
    "GEOMAX": CreatureSpec("GEOMAX", "EARTH", 42, 6, (203, 190, 119), (115, 147, 85), ("Subtraction Shield", "Multiplication Boulder"),
                           8, "multiplication", (), "blob", "A sturdy stone golem with a glowing triangle heart.",
                           sprite="GEOMAX"),
}

EVOLUTIONS = {
    "PYRON": CreatureSpec("PYRONYX", "FIRE", 48, 11, (255, 218, 105), (173, 63, 78), ("Solar Addition", "Multiplication Nova"),
                          99, "addition", sprite="PYRON", size=1.18),
    "AQUABIT": CreatureSpec("AQUACREST", "WATER", 52, 10, (171, 241, 232), (45, 118, 167), ("Tidal Subtraction", "Division Surge"),
                            99, "subtraction", sprite="AQUABIT", size=1.18),
    "GEOMAX": CreatureSpec("GEOMAXIMUS", "EARTH", 57, 9, (229, 209, 139), (93, 123, 74), ("Subtraction Shield", "Multiplication Boulder"),
                           99, "multiplication", sprite="GEOMAX", size=1.18),
}

# Saves made before the new art used these starter ids.
LEGACY_NAMES = {"PYROX": "PYRON", "TERRABIT": "GEOMAX", "TERRAVOLT": "GEOMAXIMUS"}


def canonical_name(name):
    return LEGACY_NAMES.get(name, name)


def creature_spec(name: str, level: int = 1) -> CreatureSpec:
    """Return the earned form for a starter while retaining its save identity."""
    name = canonical_name(name)
    base = STARTERS.get(name)
    if base and level >= base.evolution_level:
        return EVOLUTIONS[name]
    for starter, evolved in EVOLUTIONS.items():
        if name == evolved.name:
            return evolved
    if not base and name in WILD_BY_NAME:
        return WILD_BY_NAME[name]
    return base or STARTERS["PYRON"]


VOLTIX = CreatureSpec("VOLTIX", "SPARK", 26, 6, (255, 214, 80), (128, 72, 170), ("Times Bolt", "Multiply Storm"), 99,
                      "multiplication", ("meadow", "ridge"), sprite="VOLTIX",
                      blurb="A crackling fox. Its tails spark in groups: 3, 6, 9, 12...")
DIVOWL = CreatureSpec("DIVOWL", "LEAF", 28, 5, (178, 232, 140), (70, 150, 70), ("Share Gust", "Division Dive"), 99,
                      "division", ("meadow", "grove", "falls"), sprite="DIVOWL",
                      blurb="A wise leaf owl that splits every snack into equal shares.")
FRACTELLA = CreatureSpec("FRACTELLA", "CRYSTAL", 30, 6, (250, 150, 230), (150, 90, 200), ("Shard Split", "Fraction Burst"), 99,
                         "division", ("grove", "ridge", "falls"), sprite="FRACTELLA",
                         blurb="A cheerful crystal slime. It breaks into perfect, equal pieces.")
CHRONOX = CreatureSpec("CHRONOX", "TIME", 36, 8, (230, 190, 90), (140, 90, 40), ("Clockwork Plus", "Time Split"), 99,
                       "", ("meadow", "grove", "ridge", "falls"), sprite="CHRONOX", rarity=2,
                       blurb="A legendary clockwork dragon. It appears to learners who keep practising.")
BOSS = CreatureSpec("NUMEREX", "BOSS", 58, 7, (190, 120, 255), (60, 30, 110), ("Number Roar",), 99,
                    "", (), sprite="NUMEREX", size=1.2,
                    blurb="The Arithmetic Beast, a shadow spirit guarding the old stone arch. It tests every skill.")

# ENEMIES keeps its historic shape: three wild creatures followed by the boss at index 3.
ENEMIES = (VOLTIX, DIVOWL, FRACTELLA, BOSS)
WILD = (VOLTIX, DIVOWL, FRACTELLA, CHRONOX)
WILD_BY_NAME = {spec.name: spec for spec in WILD}
TOPIC_COLORS = {"addition": (137, 199, 124), "subtraction": (110, 177, 206),
                "multiplication": (242, 187, 82), "division": (235, 112, 92), "": (220, 200, 240)}


def leader_spec(player, flags):
    """The team member that fights and follows you: a captured monster chosen in the MathDex,
    otherwise your partner (the starter, in its earned form). The partner is never removed."""
    chosen = [f.split(":", 1)[1] for f in flags if f.startswith("companion:")]
    name = chosen[0] if chosen else None
    if name in WILD_BY_NAME and f"dex_friend:{name}" in flags:
        return WILD_BY_NAME[name]
    return creature_spec(player.creature, player.level)


def encounter_for(area_id, rng):
    """Pick a wild creature for the area's tall grass, weighted by rarity."""
    pool = [spec for spec in WILD if area_id in spec.habitat] or [spec for spec in WILD if "meadow" in spec.habitat]
    return rng.choices(pool, weights=[spec.rarity for spec in pool])[0]


def bond_topic(spec, rng):
    """Bond challenges use the creature's topic; topic-less rare creatures mix all four."""
    return spec.topic or rng.choice(("addition", "subtraction", "multiplication", "division"))


def draw_creature(surface, spec, anchor, height, pose="idle", flip=False, tint=None):
    """Draw ``spec`` standing with its feet at ``anchor`` (centre-x, bottom-y), about ``height`` px tall.

    Uses the creature's sprite art when it exists, otherwise the code-drawn fallback.
    """
    from game import monster_sprites
    height = max(4, round(height * spec.size))
    if monster_sprites.available(spec.sprite):
        return monster_sprites.draw(surface, spec.sprite, anchor, height, pose, flip, tint)
    scale = max(1, round(height / 16))
    pixel_monster(surface, anchor[0] - 8 * scale, anchor[1] - 16 * scale, spec, scale, flip, tint)
    return None


SHAPES = {
    "blob": ((
        "0000000011000000", "0000001122110000", "0000112222221100", "0011222222222210",
        "0112222222222221", "1122222222222221", "1222222222222211", "1222222222222110",
        "1222222222222110", "0122222222222100", "0012222222221000", "0001222222210000",
        "0001122222110000", "0000110001100000", "0001100000110000", "0011000000011000",
    ), {(6, 4), (6, 11)}),
    "eared": ((
        "0100000000000010", "1210000000000121", "1221000000001221", "1222111111112221",
        "0122222222222210", "0122222222222210", "0122222222222210", "0122222222222210",
        "0012222222222100", "0012222222222100", "0001222222221000", "0001222222221000",
        "0000122222210000", "0000110000110000", "0001100000011000", "0001100000011000",
    ), {(6, 4), (6, 11)}),
    "squat": ((
        "0000000000000000", "0000000000000000", "0000000000000000", "0000011111100000",
        "0001122222211000", "0012222222222100", "0122222222222210", "1222222222222221",
        "1222222222222221", "1222222222222221", "1222222222222221", "0122222222222210",
        "0012222222222100", "0110000000000110", "1100000000000011", "0000000000000000",
    ), {(6, 5), (6, 10)}),
    "wing": ((
        "0000000110000000", "0000001221000000", "1100012222100011", "1211122222211121",
        "1222222222222221", "1222222222222221", "0122222222222210", "0012222222222100",
        "0001222222221000", "0011222222221100", "0122222222222210", "0122100000012210",
        "0011000000001100", "0000011001100000", "0000110000110000", "0000000000000000",
    ), {(6, 5), (6, 10)}),
    "tall": ((
        "0000001111000000", "0000012222100000", "0000122222210000", "0000122222210000",
        "0001122222211000", "0012222222222100", "0122222222222210", "0122222222222210",
        "0012222222222100", "0001222222221000", "0001222222221000", "0000122222210000",
        "0000122222210000", "0000011001100000", "0000110000110000", "0001100000011000",
    ), {(3, 6), (3, 9)}),
}


def pixel_monster(surface, x: int, y: int, spec: CreatureSpec, scale: int = 2, flip: bool = False, tint=None) -> None:
    """Draw a chunky, original creature from rectangles (no external assets).

    ``tint`` paints the whole silhouette one colour, used for hit flashes.
    """
    import pygame

    # 16x16 bit silhouette; 1 = body, 2 = accent, 3 = eye, 4 = shadow.
    shape, eyes = SHAPES.get(spec.shape, SHAPES["blob"])
    colors = {"1": spec.base, "2": spec.accent, "3": (255, 249, 220), "4": tuple(max(0, c - 42) for c in spec.base)}
    if tint:
        colors = {key: tint for key in colors}
    px = int(x)
    y = int(y)
    for row_index, row in enumerate(shape):
        for col_index, cell in enumerate(row):
            if cell == "0":
                continue
            col = 15 - col_index if flip else col_index
            # Eyes and feet use a contrasting outline for crisp low-res silhouettes.
            actual = "3" if (row_index, col_index) in eyes else ("4" if row_index >= 13 else cell)
            pygame.draw.rect(surface, colors[actual], (px + col * scale, y + row_index * scale, scale, scale))
    # Distinctive silhouettes and elemental marks keep the trio recognizable.
    if tint or spec.shape != "blob":
        return

    def mark(color, col, row, w, h):
        # Elemental marks mirror with the body so flipped enemies stay consistent.
        col = 16 - col - w if flip else col
        pygame.draw.rect(surface, color, (px + col * scale, y + row * scale, w * scale, h * scale))

    if spec.element == "FIRE" or spec.element == "EMBER":
        mark((255, 215, 102), 13, 9, 3, 1)
        mark((245, 126, 73), 15, 7, 2, 3)
    elif spec.element == "WATER":
        mark((174, 235, 227), 2, 4, 2, 5)
        mark((174, 235, 227), 12, 4, 2, 5)
    elif spec.element == "EARTH":
        mark((226, 213, 159), 2, 2, 2, 4)
        mark((226, 213, 159), 12, 2, 2, 4)
    elif spec.element == "BOSS":
        mark((255, 222, 125), 5, 0, 2, 4)
        mark((255, 222, 125), 10, 0, 2, 4)

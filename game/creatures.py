"""Drawing MATHMON creatures, plus lookups that older screens (Arena, Trials) still use.

Species data lives in data/monsters.json (see monsters.monster_data). ``draw_creature`` uses a
species' processed sprite frames when they exist and a code-drawn placeholder otherwise, so the
game stays playable with missing art (GDD 24.1).
"""
from monsters.monster_data import has_species, species, species_ids, starter_ids

STARTERS = {sid: species(sid) for sid in starter_ids()}
BOSS = species("NUMEREX_BOSS")
WILD = tuple(species(sid) for sid in species_ids() if not species(sid).boss and species(sid).stage == 1)
WILD_BY_NAME = {spec.name: spec for spec in WILD}
ENEMIES = (species("VOLTIX"), species("DIVOWL"), species("FRACTELLA"), BOSS)
TOPIC_COLORS = {"addition": (137, 199, 124), "subtraction": (110, 177, 206), "multiplication": (242, 187, 82),
                "division": (235, 112, 92), "fractions": (240, 150, 200), "ratios": (250, 180, 220),
                "integers": (180, 140, 240), "algebra": (240, 200, 100), "geometry": (203, 170, 105),
                "sequences": (120, 210, 190), "reasoning": (220, 200, 240), "": (220, 200, 240)}


def creature_spec(name, level=1):
    """Species by id or display name (older code passes names like "VOLTIX")."""
    from monsters.monster_data import canonical_species
    if has_species(str(name)):
        return species(name)
    for sid in species_ids():
        if species(sid).name == name and not species(sid).boss:
            return species(sid)
    return species(canonical_species(name))


def leader_spec(player, flags=()):
    """The lead monster's species (Arena portrait)."""
    return creature_spec(getattr(player, "creature", "FRACTELLA"))


def draw_creature(surface, spec, anchor, height, pose="idle", flip=False, tint=None):
    """Draw ``spec`` standing with its feet at ``anchor`` (centre-x, bottom-y), about ``height`` px tall."""
    from game import monster_sprites
    height = max(4, round(height * getattr(spec, "size", 1.0)))
    if monster_sprites.available(getattr(spec, "sprite", "")):
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
}


def pixel_monster(surface, x, y, spec, scale=2, flip=False, tint=None):
    """Placeholder sprite drawn from rectangles, used when a species has no art."""
    import pygame
    shape, eyes = SHAPES["blob"]
    base = tuple(getattr(spec, "base", (120, 120, 160)))
    colors = {"1": base, "2": tuple(getattr(spec, "accent", (220, 220, 240))), "3": (255, 249, 220),
              "4": tuple(max(0, c - 42) for c in base)}
    if tint:
        colors = {key: tint for key in colors}
    for row_index, row in enumerate(shape):
        for col_index, cell in enumerate(row):
            if cell == "0":
                continue
            col = 15 - col_index if flip else col_index
            actual = "3" if (row_index, col_index) in eyes else ("4" if row_index >= 13 else cell)
            pygame.draw.rect(surface, colors[actual], (int(x) + col * scale, int(y) + row_index * scale, scale, scale))

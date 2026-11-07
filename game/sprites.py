"""Palette-driven 16x16 character sprites with facing directions and a walk cycle.

Template keys: o outline, h hair, s skin, e eyes, c clothes, a accent, p trousers, k shoes.
"""
import pygame

BODY_DOWN = (
    "................",
    ".....oooooo.....",
    "....ohhhhhho....",
    "....ohhhhhho....",
    "....ohssssho....",
    "....osesseso....",
    ".....ossssso....",
    "....occsscco....",
    "...occcaaccco...",
    "...occcaaccco...",
    "...occcccccco...",
    "...sccccccccs...",
    "....oppppppo....",
)
BODY_UP = (
    "................",
    ".....oooooo.....",
    "....ohhhhhho....",
    "....ohhhhhho....",
    "....ohhhhhho....",
    "....ohhhhhho....",
    ".....ossssso....",
    "....occcccco....",
    "...occcccccco...",
    "...occcccccco...",
    "...occcccccco...",
    "...sccccccccs...",
    "....oppppppo....",
)
BODY_SIDE = (
    "................",
    ".....oooooo.....",
    "....ohhhhhho....",
    "....ohhhhhho....",
    "....ohhhssso....",
    "....ohhsseso....",
    ".....osssso.....",
    ".....occcco.....",
    "....occccaco....",
    "....occccaco....",
    "....occcscco....",
    "....occcccco....",
    "....oppppppo....",
)
LEGS_FRONT_STAND = ("....opp..ppo....", "....opp..ppo....", "....okk..kko....")
LEGS_FRONT_WALK = ("....opp..ppo....", "....okk..ppo....", ".........kko....")
LEGS_SIDE_STAND = (".....oppppo.....", ".....oppppo.....", ".....okkkko.....")
LEGS_SIDE_WALK = ("....opp.ppo.....", "...opp...ppo....", "...kk.....kk....")

DEFAULT_LOOK = {
    "outline": "#15101a", "hair": "#1a1a1a", "skin": "#c68a5e", "eyes": "#15101a",
    "clothes": "#2b3f6a", "accent": "#e8a33d", "pants": "#22222c", "shoes": "#141010",
}
PLAYER_LOOK = {"hair": "#2b1d17", "skin": "#c08a5e", "clothes": "#2f5d8a", "accent": "#f2bb52",
               "pants": "#1b2a44", "shoes": "#0b0b10"}

_cache = {}


def _color(value):
    return pygame.Color(value)


def _sprite(rows, palette):
    surface = pygame.Surface((16, 16), pygame.SRCALPHA)
    for y, row in enumerate(rows[:16]):
        for x, key in enumerate(row[:16]):
            if key in palette:
                surface.set_at((x, y), palette[key])
    return surface


def character_frames(look=None):
    """Return {"down": [stand, walk, walk_mirrored], "up": [...], "side": [...]} (side faces right)."""
    look = {**DEFAULT_LOOK, **(look or {})}
    key = tuple(sorted(look.items()))
    if key in _cache:
        return _cache[key]
    names = {"o": "outline", "h": "hair", "s": "skin", "e": "eyes", "c": "clothes",
             "a": "accent", "p": "pants", "k": "shoes"}
    palette = {code: _color(look[name]) for code, name in names.items()}
    down_walk = _sprite(BODY_DOWN + LEGS_FRONT_WALK, palette)
    up_walk = _sprite(BODY_UP + LEGS_FRONT_WALK, palette)
    frames = {
        "down": [_sprite(BODY_DOWN + LEGS_FRONT_STAND, palette), down_walk, pygame.transform.flip(down_walk, True, False)],
        "up": [_sprite(BODY_UP + LEGS_FRONT_STAND, palette), up_walk, pygame.transform.flip(up_walk, True, False)],
        "side": [_sprite(BODY_SIDE + LEGS_SIDE_STAND, palette), _sprite(BODY_SIDE + LEGS_SIDE_WALK, palette),
                 _sprite(BODY_SIDE + LEGS_SIDE_STAND, palette)],
    }
    _cache[key] = frames
    return frames


def frame_for(frames, facing, walk_time, moving):
    """Pick the texture for a facing (dx, dy) and walk animation time in seconds."""
    if facing == (0, -1):
        sequence = frames["up"]
    elif facing[0] != 0:
        sequence = frames["side"]
    else:
        sequence = frames["down"]
    index = (1, 0, 2, 0)[int(walk_time * 8) % 4] if moving else 0
    image = sequence[index]
    if facing == (-1, 0):
        image = pygame.transform.flip(image, True, False)
    return image

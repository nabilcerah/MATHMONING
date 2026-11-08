"""Load and draw the processed monster sprite frames (see tools/process_monster_sprites.py).

Frames are stored at ~96px tall. Each manifest pose records its offset from the idle
pose's bottom-centre, so every pose can be drawn at one anchor point (the creature's
feet) without the creature jumping between frames. Sprites face right.
"""
import json
from pathlib import Path

import pygame

from config import ROOT

SPRITE_DIR = ROOT / "assets" / "sprites" / "monsters"
SPRITE_ROOT = ROOT / "assets" / "sprites"


def _folder(name):
    """Monster names live in sprites/monsters; "characters/ALEX"-style names are relative to sprites/."""
    return Path(SPRITE_ROOT) / name if "/" in name else Path(SPRITE_DIR) / name


POSE_INDEX = {"idle": 0, "idle2": 1, "idle3": 2, "windup": 3, "attack": 4, "special": 5,
              "burst": 6, "hurt": 7, "happy": 8}
# "rows" sheets (idle x3 / walk x3 / attack x3) have no hurt or happy frames: those poses fall back
# to idle frames and the battle screen adds placeholder effects (flash, shake, fade) on top.
ROW_POSE_INDEX = {"idle": 0, "idle2": 1, "idle3": 2, "idle1": 0, "walk1": 3, "walk2": 4, "walk3": 5,
                  "windup": 6, "attack1": 6, "attack": 7, "attack2": 7, "special": 8, "attack3": 8,
                  "burst": 8, "hurt": 0, "happy": 1}

_manifests = {}
_raw = {}
_cache = {}


def manifest(name):
    if name not in _manifests:
        path = _folder(name) / "manifest.json"
        _manifests[name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return _manifests[name]


def available(name):
    return bool(name) and manifest(name) is not None


def _raw_frame(name, index):
    key = (name, index)
    if key not in _raw:
        info = manifest(name)["poses"][index]
        image = pygame.image.load(str(_folder(name) / info["file"]))
        _raw[key] = image.convert_alpha() if pygame.display.get_surface() else image
    return _raw[key]


def _binarise_alpha(surface):
    """Smooth scaling leaves soft edges; snap alpha so sprites stay crisp on the pixel canvas."""
    width, height = surface.get_size()
    surface.lock()
    for y in range(height):
        for x in range(width):
            r, g, b, a = surface.get_at((x, y))
            if a and a != 255:
                surface.set_at((x, y), (r, g, b, 255 if a >= 110 else 0))
    surface.unlock()
    return surface


def _tinted(surface, tint):
    tinted = surface.copy()
    tinted.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
    tinted.fill((*tint[:3], 0), special_flags=pygame.BLEND_RGBA_ADD)
    return tinted


def pose_index(name, pose):
    if not isinstance(pose, str):
        return int(pose)
    table = ROW_POSE_INDEX if (manifest(name) or {}).get("layout") == "rows" else POSE_INDEX
    return table.get(pose, 0)


def animations(name):
    """{"idle": [0, 1, 2], "walk": [...], "attack": [...]} for row sheets, else a best-effort map."""
    info = manifest(name) or {}
    return info.get("animations") or {"idle": [0, 1, 2], "walk": [0, 1, 2], "attack": [3, 4, 5]}


def frame(name, pose, height, flip=False, tint=None):
    """Return (surface, (dx, dy)) where dx, dy offset the surface from the feet anchor."""
    index = pose_index(name, pose)
    key = (name, index, int(height), bool(flip), tuple(tint) if tint else None)
    cached = _cache.get(key)
    if cached:
        return cached
    info = manifest(name)
    pose_info = info["poses"][index]
    scale = height / info["idle_height"]
    raw = _raw_frame(name, index)
    size = (max(1, round(raw.get_width() * scale)), max(1, round(raw.get_height() * scale)))
    image = _binarise_alpha(pygame.transform.smoothscale(raw.convert_alpha() if pygame.display.get_surface() else raw, size))
    dx, dy = round(pose_info["dx"] * scale), round(pose_info["dy"] * scale)
    if flip:
        image = pygame.transform.flip(image, True, False)
        dx = -dx - size[0]
    if tint:
        image = _tinted(image, tint)
    _cache[key] = (image, (dx, dy))
    return _cache[key]


def draw(surface, name, anchor, height, pose="idle", flip=False, tint=None):
    """Draw a pose with its feet at ``anchor`` (x = centre, y = bottom). Returns the drawn rect."""
    image, (dx, dy) = frame(name, pose, height, flip, tint)
    return surface.blit(image, (round(anchor[0] + dx), round(anchor[1] + dy)))

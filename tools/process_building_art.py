"""Turn the hand-made building art in assets/ into game-ready files (bug report: Mathmart and the
Mathmon Recovery Center).

    python tools/process_building_art.py

* Interiors become painted map backgrounds (16 px tiles): the Mathmart is 11 x 9 tiles, the
  Recovery Center 30 x 18. Collision grids are written by hand below (the art has no clean
  colour rule for furniture), and every walkable cell is checked to be connected.
* The recovery-chamber and nurse sheets are cut into frames with MANUAL cell rectangles, because
  each cell has a "FRAME n" caption that must not be included (GDD 24.1: inspect the real files;
  provide a manual fallback for cell positions).
* The building exteriors have a fake checkerboard "transparency" baked into the JPEG; it is keyed
  out with a flood fill from the image border, which stops at the buildings' dark outlines.
Needs Pillow + numpy (requirements-dev.txt). Deterministic.
"""
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BG = ROOT / "assets" / "backgrounds"
CLINIC = ROOT / "assets" / "sprites" / "clinic"
MAPS = ROOT / "data" / "maps"

MART_COLLISION = """
###########
###########
####...##.#
####...##.#
####...##.#
.......##.#
.##....##.#
..........#
###########
"""
MCR_COLLISION = """
###############
###############
##.############
....#######....
...............
##.........##..
##.........##.#
#..........##.#
###############
"""   # 15 x 9 tiles (the painting at half size); row 2, columns 12-14 hold three recovery capsules


def grid(text):
    rows = [row for row in text.strip().splitlines()]
    assert len({len(r) for r in rows}) == 1, "ragged collision grid"
    return rows


def connected(rows, start):
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= ny < len(rows) and 0 <= nx < len(rows[0]) and rows[ny][nx] == "." and (nx, ny) not in seen:
                seen.add((nx, ny))
                queue.append((nx, ny))
    floor = {(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == "."}
    assert floor == seen, f"unreachable floor cells: {sorted(floor - seen)[:5]}"


FLOOR_PERIOD = 16     # the MCR floor tiles repeat every 16 px in the source art


def erase_painted_people(image):
    """Paint the nurse (behind the counter), the receptionist (by the info board) and the ball emblem
    on the floor out of the MCR art, using the repeating floor / wall pattern next to them.
    Coordinates are source pixels."""
    a = np.asarray(image).copy()
    # Nurse: x 204-262, y 42-88. Copy each column from 16 px to its right, right to left, so
    # the clean wall + floor beside her (x 262-278) repeats across.
    for x in range(261, 210, -1):
        a[42:89, x] = a[42:89, x + FLOOR_PERIOD]
    # The healing machine left of her is symmetric (centre x = 185): rebuild its hidden right edge.
    for x in range(204, 211):
        a[28:89, x] = a[28:89, 370 - x]
    # Receptionist, floor part (y 79-96): repeat the clean floor on her left, left to right.
    for x in range(78, 129):
        a[79:97, x] = a[79:97, x - FLOOR_PERIOD]
    # Receptionist, information-board part (y 47-78): empty shelves (each row's typical colour)
    # and the board's right frame continued down.
    for y in range(47, 79):
        a[y, 78:124] = np.median(a[y, 68:78], axis=0)
        a[y, 124:129] = a[44, 124:129]
    # The ball emblem on the floor (x 192-287, y 160-252): plain floor tiles from 6 tiles to the left.
    for x in range(190, 290):
        a[158:255, x] = a[158:255, x - 6 * FLOOR_PERIOD]
    return Image.fromarray(a)


def interiors():
    mart = Image.open(BG / "Interior mathmart.jpeg").convert("RGB")
    assert mart.size == (176, 144), mart.size          # exactly 11 x 9 tiles of 16 px
    mart.save(BG / "village_shop_interior.png", optimize=True)
    rows = grid(MART_COLLISION)
    connected(rows, (4, 7))
    (MAPS / "village_shop_collision.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")

    mcr = Image.open(BG / "Interior Mathmon Recovery Center (MCR).jpeg").convert("RGB")
    # The nurse and the receptionist are real, moving characters now: paint them out of the art.
    mcr = erase_painted_people(mcr)
    # Half size (15 x 9 tiles): at full size the painted nurse was ~3x taller than the characters.
    mcr = mcr.resize((480, 296), Image.NEAREST).crop((0, 4, 480, 292)).resize((240, 144), Image.LANCZOS)
    # A new file: the earlier village_recovery_interior.png (with the painted people) is kept.
    mcr.save(BG / "village_recovery_interior_v2.png", optimize=True)
    rows = grid(MCR_COLLISION)
    connected(rows, (7, 7))
    (MAPS / "village_recovery_collision.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


# The recovery chamber sheet: 3 x 3 cells of ~191 x 341 px, each with a ~52 px caption on top.
CHAMBER_CELLS = [(c * 191 + 6, r * 341 + (80 if r == 2 else 56), c * 191 + 185, r * 341 + 336)
                 for r in range(3) for c in range(3)]   # the bottom row has two-line captions
CHAMBER_STAGES = ["Patient admitted", "Diagnostics", "Injection", "Pulse phase 1", "Wound closure",
                  "Pulse phase 2", "Restoration complete", "Verification", "Ready for discharge"]
# The nurse sheet: 5 x 3 portraits; the "FRAME n" label sits in each cell's bottom-right corner.
NURSE_X = (72, 330, 588, 846, 1104)
NURSE_Y = (30, 271, 517)
NURSE_CELLS = [(x, y, x + 232, y + 205) for y in NURSE_Y for x in NURSE_X]
NURSE_MOODS = {"welcome": 0, "idea": 1, "pen": 2, "listen": 3, "happy": 4, "thinking": 5, "reading": 6,
               "point": 7, "check": 8, "pulse": 9, "steth": 11, "cheer": 13, "done": 14}


def frames():
    CLINIC.mkdir(parents=True, exist_ok=True)
    # The recovery capsule is drawn in code with the player's own MathMon inside (states/clinic_state.py);
    # the old capsule sheet showed a person, so its frames are no longer cut out.
    nurse = Image.open(ROOT / "assets" / "Characters" / "Nurse.jpeg").convert("RGB")
    for i, box in enumerate(NURSE_CELLS):
        nurse.crop(box).resize((88, 78), Image.LANCZOS).save(CLINIC / f"nurse_{i}.png", optimize=True)
    manifest = {"source": "tools/process_building_art.py", "chamber_cells": CHAMBER_CELLS,
                "chamber_stages": CHAMBER_STAGES, "nurse_cells": NURSE_CELLS, "nurse_moods": NURSE_MOODS}
    (CLINIC / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")


def key_out(image, box=None, tolerance=40):
    """Make the border-connected background transparent (checkerboard or flat dark)."""
    img = image.convert("RGB") if box is None else image.convert("RGB").crop(box)
    a = np.asarray(img).astype(int)
    h, w, _ = a.shape
    corners = [a[0, 0], a[0, w - 1], a[h - 1, 0], a[h - 1, w - 1]]
    sat = a.max(axis=2) - a.min(axis=2)

    def background(y, x):
        if sat[y, x] < 18 and a[y, x].mean() > 150:          # light grey/white checker squares
            return True
        return any(np.abs(a[y, x] - c).sum() < tolerance for c in corners)

    mask = np.zeros((h, w), dtype=bool)
    queue = deque((y, x) for y in range(h) for x in (0, w - 1)) + deque((y, x) for x in range(w) for y in (0, h - 1))
    for y, x in list(queue):
        mask[y, x] = background(y, x)
    queue = deque(p for p in queue if mask[p])
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < h and 0 <= nx < w and not mask[ny, nx] and background(ny, nx):
                mask[ny, nx] = True
                queue.append((ny, nx))
    rgba = np.dstack([a.astype(np.uint8), np.where(mask, 0, 255).astype(np.uint8)])
    out = Image.fromarray(rgba, "RGBA")
    return out.crop(out.getbbox())


def exteriors():
    mcr = key_out(Image.open(BG / "Mathmon Recovery Center (MCR).jpeg"))
    # 64 x 48: as tall as the Mathmart, so it fills its 3 x 3 plot (at its natural 64 x 34 the top tile of
    # the plot was an invisible wall over bare grass, and the building looked smaller than its neighbours).
    small = mcr.resize((64, 48), Image.LANCZOS)
    # At this size the roof's red cross blurs into a red-and-white disc (it read like a ball logo):
    # repaint it as a crisp first-aid cross - a white tile with a thick red plus. The emblem sits in the
    # white gable under the roof peak, at about (49%, 28%) of the building.
    px = small.load()
    cx, cy = round(small.width * 0.49), round(small.height * 0.28)
    for y in range(cy - 4, cy + 4):
        for x in range(cx - 4, cx + 4):
            px[x, y] = (250, 250, 250, 255)
    for y in range(cy - 3, cy + 3):
        for x in range(cx - 1, cx + 1):
            px[x, y] = (214, 48, 49, 255)
    for y in range(cy - 1, cy + 1):
        for x in range(cx - 3, cx + 3):
            px[x, y] = (214, 48, 49, 255)
    small.save(BG / "recovery_center_exterior.png")
    mart = key_out(Image.open(BG / "Mathmart.jpeg"), box=(28, 28, 316, 318), tolerance=30)
    mart.resize((52, round(52 * mart.height / mart.width)), Image.LANCZOS).save(BG / "mathmart_exterior.png")


def main():
    interiors()
    frames()
    exteriors()
    print("building art processed")


if __name__ == "__main__":
    main()

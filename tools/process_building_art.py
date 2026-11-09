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
##.#########...
....#######....
...............
##.........##..
##.........##.#
#..........##.#
###############
"""   # 15 x 9 tiles: the painting at HALF size, so the painted nurse is as tall as the player


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


def interiors():
    mart = Image.open(BG / "Interior mathmart.jpeg").convert("RGB")
    assert mart.size == (176, 144), mart.size          # exactly 11 x 9 tiles of 16 px
    mart.save(BG / "village_shop_interior.png", optimize=True)
    rows = grid(MART_COLLISION)
    connected(rows, (4, 7))
    (MAPS / "village_shop_collision.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")

    mcr = Image.open(BG / "Interior Mathmon Recovery Center (MCR).jpeg").convert("RGB")
    # Half size (15 x 9 tiles): at full size the painted nurse was ~3x taller than the characters.
    mcr = mcr.resize((480, 296), Image.NEAREST).crop((0, 4, 480, 292)).resize((240, 144), Image.LANCZOS)
    mcr.save(BG / "village_recovery_interior.png", optimize=True)
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
    mcr.resize((64, round(64 * mcr.height / mcr.width)), Image.LANCZOS).save(BG / "recovery_center_exterior.png")
    mart = key_out(Image.open(BG / "Mathmart.jpeg"), box=(28, 28, 316, 318), tolerance=30)
    mart.resize((52, round(52 * mart.height / mart.width)), Image.LANCZOS).save(BG / "mathmart_exterior.png")


def main():
    interiors()
    frames()
    exteriors()
    print("building art processed")


if __name__ == "__main__":
    main()

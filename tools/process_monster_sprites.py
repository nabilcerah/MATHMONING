"""Turn the generated 3x3 monster and character sheets into clean, game-ready sprite frames.

Run once whenever a sheet in assets/monsterassets changes:

    python tools/process_monster_sprites.py

For every sheet it cuts the nine poses, removes the background (a baked-in
checkerboard, plain white, or a noisy alpha halo), drops stray specks, crops each
pose and writes ``assets/sprites/monsters/<NAME>/<n>.png`` plus a ``manifest.json``
that records where each pose sits relative to the idle pose. The game itself only
needs pygame to load the results; this tool needs numpy and Pillow
(``pip install -r requirements-dev.txt``).

Pose order (left-to-right, top-to-bottom):
    monsters:   0-2 idle / walk, 3 wind-up, 4 attack, 5 special, 6 power burst, 7 hurt, 8 happy
    characters: 0 stand, 1-2 walk, 3 run, 4 wave, 5 cheer, 6 surprised, 7 hurt, 8 fist pump
    "rows" sheets (the advanced battle monsters): row 1 idle x3, row 2 walk x3, row 3 attack x3.
    Their manifest lists those three animations; there are no hurt/defeat frames, so the game
    shows those with placeholder effects instead of inventing frames.
"""
import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "monsterassets"
CHARACTER_SOURCE = ROOT / "assets" / "Characters"
OUTPUT = ROOT / "assets" / "sprites" / "monsters"
CHARACTER_OUTPUT = ROOT / "assets" / "sprites" / "characters"
TARGET_IDLE_HEIGHT = 96  # stored resolution; the game scales down further
POSES = ("idle", "idle2", "idle3", "windup", "attack", "special", "burst", "hurt", "happy")
CHARACTER_POSES = ("stand", "walk1", "walk2", "run", "wave", "cheer", "surprised", "hurt", "fist")
ROW_POSES = ("idle1", "idle2", "idle3", "walk1", "walk2", "walk3", "attack1", "attack2", "attack3")
ROW_ANIMATIONS = {"idle": [0, 1, 2], "walk": [3, 4, 5], "attack": [6, 7, 8]}

SHEETS = {
    "PYRON": ("PYRON.jpg", "checker"),
    "AQUABIT": ("Aquabit.jpg", "checker"),
    "DIVOWL": ("DIVOWL.jpg", "checker"),
    "VOLTIX": ("VOLTIX.jpg", "checker"),
    "CHRONOX": ("CHRONOX.jpg", "white"),
    "FRACTELLA": ("FRACTELLA.png", "alpha"),
    "GEOMAX": ("GEOMAX.png", "alpha"),
    "NUMEREX": ("NUMEREX.png", "alpha"),
    # People: player avatars and villagers.
    "ALEX": ("ALEX.jpg", "light_checker"),
    "LUNA": ("LUNA.jpg", "light_checker"),
    "PROFESSOR_NUMERIS": ("PROFESSOR NUMERIS.jpg", "light_checker_solid"),  # white lab coat
    "REX": ("REX.jpg", "light_checker"),
    "BRAM": ("bram.jpg.jpeg", "grey_checker"),      # the builder: a 5 x 3 sheet, see GRIDS
    "NURSE_HANA": ("NURSE HANA.jpg", "light_checker_solid"),          # white coat
    "FARAH": ("RECEPTIONIST FARAH.jpg", "checker"),
    "AINA": ("Random NPC/AINA.jpg", "checker"),
    "ZAKI": ("Random NPC/ENCIK ZAKI.jpg", "checker"),
    "HAKIM": ("Random NPC/HAKIM.jpg", "checker"),
    "SHAZLAN": ("Random NPC/UNCLE SHAZLAN.jpg", "checker"),
    "FISHERMAN": ("Random NPC/Fisherman.jpeg", "checker"),
    # Advanced battle monsters (3x3 sheets laid out as idle / walk / attack rows).
    "CRYSTALGON": ("CRYSTALGON.jpg", "grey_checker"),
    "NULLSHADE": ("NULLSHADE.jpg", "grey_checker"),
    "VOLTBYTE": ("VOLTBYTE.jpg", "grey_checker"),
    "CHRONOWL": ("SOLAR OWL.jpg", "grey_checker"),
    "INFERMATH": ("INFERMATH.jpg", "grey_checker"),
    "EQUINOX": ("EQUINOX.jpg", "grey_checker"),
    "MYCOMORPH": ("Octo-Spore.jpg", "grey_checker"),
    "HEXABYTE": ("SCOON.jpg", "grey_checker"),
    "GALAXION": ("GALAXION.jpg", "grey_checker"),
    "ARITHMORD": ("ARITHMORD.jpg", "grey_checker"),
    "SPHYNOX": ("SPHYNOX.jpg", "grey_checker"),
    "INFINITY_ZERO": ("INFINITY ZERO.jpg", "grey_checker"),
}
CHARACTERS = {"ALEX", "LUNA", "PROFESSOR_NUMERIS", "REX", "BRAM", "NURSE_HANA", "FARAH", "AINA", "ZAKI", "HAKIM",
              "SHAZLAN", "FISHERMAN"}
# Villager sheets: row 1 idle, row 2 walking, row 3 gestures (wave first).
_VILLAGER = [(0, 0), (0, 1), (2, 1), (1, 1), (0, 2), (2, 2), (1, 0), (2, 0), (1, 2)]
# Sheets that are not 3 x 3: (columns, rows, the (column, row) cell for each of the 9 poses).
GRIDS = {
    # stand, walk1, walk2, run, wave (talking: hammer raised), cheer, surprised, hurt, fist
    "BRAM": (5, 3, [(0, 0), (3, 1), (4, 0), (3, 1), (1, 0), (2, 0), (4, 1), (2, 2), (2, 1)]),
    # Nurse Hana has no walking row: her gestures double as steps; 1, 2, 6, 7 are her check-up poses.
    "NURSE_HANA": (3, 3, [(0, 0), (1, 1), (0, 1), (1, 0), (2, 0), (2, 2), (1, 2), (0, 2), (2, 1)]),
    # Farah stays at the counter: tablet, book, wave, idea...
    "FARAH": (3, 3, [(0, 1), (1, 1), (2, 1), (0, 0), (1, 0), (2, 2), (0, 2), (1, 2), (2, 0)]),
    "AINA": (3, 3, _VILLAGER), "ZAKI": (3, 3, _VILLAGER), "HAKIM": (3, 3, _VILLAGER), "SHAZLAN": (3, 3, _VILLAGER),
    # The fisherman's sheet is his fishing cycle, kept in reading order (stand, cast, ..., the catch).
    "FISHERMAN": (3, 3, [(0, 0), (1, 0), (0, 0), (2, 0), (2, 2), (1, 2), (0, 1), (1, 1), (2, 1)]),
}
ROW_LAYOUT = {"CRYSTALGON", "NULLSHADE", "VOLTBYTE", "CHRONOWL", "INFERMATH", "EQUINOX", "MYCOMORPH",
              "HEXABYTE", "GALAXION", "ARITHMORD", "SPHYNOX", "INFINITY_ZERO"}


def sheet_paths(name):
    if name in CHARACTERS:
        return CHARACTER_SOURCE, CHARACTER_OUTPUT, CHARACTER_POSES
    if name in ROW_LAYOUT:
        return SOURCE, OUTPUT, ROW_POSES
    return SOURCE, OUTPUT, POSES


def components(mask):
    """Label 4-connected True regions. Returns (labels, sizes) with labels 1..n."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    sizes = [0]
    current = 0
    ys, xs = np.nonzero(mask)
    for sy, sx in zip(ys, xs):
        if labels[sy, sx]:
            continue
        current += 1
        labels[sy, sx] = current
        queue, size = deque([(sy, sx)]), 0
        while queue:
            y, x = queue.popleft()
            size += 1
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = current
                    queue.append((ny, nx))
        sizes.append(size)
    return labels, np.array(sizes)


def regions_larger_than(sizes, minimum):
    """Label ids (never 0, the unlabelled background) whose region exceeds ``minimum`` pixels."""
    ids = np.nonzero(sizes > minimum)[0]
    return ids[ids > 0]


def border_connected(mask):
    """True where a background-like pixel connects to the cell border."""
    labels, _ = components(mask)
    edge = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    return np.isin(labels, list(edge)) if edge else np.zeros_like(mask)


def background_mask(cell, mode):
    rgb = cell[..., :3].astype(np.int16)
    high, low = rgb.max(axis=2), rgb.min(axis=2)
    saturation = high - low
    if mode == "checker":
        candidate = (saturation < 26) & (high > 128)
        removed = border_connected(candidate)
        # Checker squares trapped between a tail and body: grey, low saturation, sizeable.
        grey = candidate & ~removed & (high < 222)
        labels, sizes = components(grey)
        removed |= np.isin(labels, regions_larger_than(sizes, 60))
        return removed
    if mode == "grey_checker":
        # The advanced-monster sheets use a mid-grey checker (~75-135 and ~165-195). Black outlines
        # (max < 64) stop the flood fill from leaking into dark creatures like NULLSHADE.
        candidate = (saturation < 20) & (high >= 64) & (high <= 215)
        removed = border_connected(candidate)
        labels, sizes = components(candidate & ~removed)
        for label in regions_larger_than(sizes, 40):
            values = high[labels == label]
            if np.mean(values < 148) > 0.2 and np.mean(values >= 150) > 0.2:
                removed |= labels == label  # a gap holding both checker tones
        return removed
    if mode in ("light_checker", "light_checker_solid"):
        # A pale two-tone checker (~218 and ~242). Background touching the cell edge is always
        # removed. Gaps trapped inside the figure (between legs, under an arm) are removed when
        # they hold a sizeable mix of both tones. "light_checker_solid" skips that step for
        # characters in white clothing (the Professor's lab coat has exactly those tones).
        candidate = (saturation < 24) & (high > 200)
        removed = border_connected(candidate)
        if mode == "light_checker_solid":
            return removed
        labels, sizes = components(candidate & ~removed)
        for label in range(1, len(sizes)):
            if sizes[label] < 20:
                continue
            values = high[labels == label]
            if np.mean(values <= 228) > 0.22 and np.mean(values >= 236) > 0.22:
                removed |= labels == label
        return removed
    if mode == "white":
        candidate = (low > 226) & (saturation < 22)
        removed = border_connected(candidate)
        trapped = candidate & ~removed & (low > 236)
        labels, sizes = components(trapped)
        removed |= np.isin(labels, regions_larger_than(sizes, 120))
        return removed
    # "alpha": the sheet already has transparency, but with an opaque, noisy glow.
    alpha = cell[..., 3]
    transparent = alpha < 150
    # Glow noise is bright and highly saturated (pure blues/magentas) or washed-out white mist.
    vivid_glow = (saturation > 150) & (high > 200) & ((rgb[..., 2] > 200) | (rgb[..., 0] > 200)) & (rgb[..., 1] < 90)
    mist = (low > 170) & (saturation < 60)
    return border_connected(transparent | vivid_glow | mist) | transparent


def clean_frame(cell, mode):
    removed = background_mask(cell, mode)
    keep = ~removed
    labels, sizes = components(keep)
    if len(sizes) <= 1:
        return None
    largest = sizes[1:].max()
    big = np.nonzero(sizes >= max(30, largest * 0.02))[0]
    big = big[big > 0]
    keep = np.isin(labels, big)
    out = cell.copy()
    out[..., 3] = np.where(keep, 255, 0).astype(np.uint8)
    return out


def bbox(alpha):
    ys, xs = np.nonzero(alpha)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def process(name, filename, mode):
    source, output, pose_names = sheet_paths(name)
    sheet = np.array(Image.open(source / filename).convert("RGBA"))
    h, w = sheet.shape[:2]
    inset = 6 if mode in ("checker", "grey_checker") else 0  # skip the grid lines between cells
    frames = []
    columns, rows, cells = GRIDS.get(name, (3, 3, [(i % 3, i // 3) for i in range(9)]))
    for index in range(9):
        col, row = cells[index]
        x0, x1 = col * w // columns + inset, (col + 1) * w // columns - inset
        y0, y1 = row * h // rows + inset, (row + 1) * h // rows - inset
        cleaned = clean_frame(sheet[y0:y1, x0:x1], mode)
        if cleaned is None:
            raise SystemExit(f"{name}: pose {index} came out empty")
        bx0, by0, bx1, by1 = bbox(cleaned[..., 3])
        frames.append((cleaned[by0:by1, bx0:bx1], bx0, by0))
    idle, ix, iy = frames[0]
    scale = TARGET_IDLE_HEIGHT / idle.shape[0]
    ref_cx, ref_bottom = ix + idle.shape[1] / 2, iy + idle.shape[0]
    folder = output / name
    folder.mkdir(parents=True, exist_ok=True)
    manifest = {"name": name, "source": filename, "poses": [], "idle_height": TARGET_IDLE_HEIGHT,
                "idle_width": round(idle.shape[1] * scale)}
    if name in ROW_LAYOUT:
        manifest["layout"] = "rows"
        manifest["animations"] = ROW_ANIMATIONS
    for index, (pixels, fx, fy) in enumerate(frames):
        size = (max(1, round(pixels.shape[1] * scale)), max(1, round(pixels.shape[0] * scale)))
        image = Image.fromarray(pixels).resize(size, Image.LANCZOS)
        # Re-binarise alpha after resampling so edges stay crisp pixel-art.
        data = np.array(image)
        data[..., 3] = np.where(data[..., 3] >= 128, 255, 0)
        Image.fromarray(data).save(folder / f"{index}.png")
        manifest["poses"].append({
            "pose": pose_names[index], "file": f"{index}.png",
            # Offset of the frame's top-left from the idle pose's bottom-centre, in stored pixels.
            "dx": round((fx - ref_cx) * scale), "dy": round((fy - ref_bottom) * scale),
        })
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def contact_sheet(path):
    """Preview of every processed pose over a mid-grey background (for checking by eye)."""
    tiles = []
    for name in SHEETS:
        row = []
        for index in range(9):
            image = Image.open(sheet_paths(name)[1] / name / f"{index}.png")
            tile = Image.new("RGBA", (150, 150), (60, 90, 100, 255))
            image.thumbnail((140, 140))
            tile.alpha_composite(image, ((150 - image.width) // 2, (150 - image.height) // 2))
            row.append(tile)
        tiles.append(row)
    sheet = Image.new("RGBA", (150 * 9, 150 * len(tiles)))
    for r, row in enumerate(tiles):
        for c, tile in enumerate(row):
            sheet.paste(tile, (c * 150, r * 150))
    sheet.convert("RGB").save(path)


if __name__ == "__main__":
    only = set(sys.argv[1:]) - {"--preview"}
    for name, (filename, mode) in SHEETS.items():
        if only and name not in only:
            continue
        manifest = process(name, filename, mode)
        print(f"{name:10} {mode:8} -> {manifest['idle_width']}x{manifest['idle_height']} idle, 9 poses")
    if "--preview" in sys.argv:
        preview = OUTPUT / "_preview.jpg"
        contact_sheet(preview)
        print("preview:", preview)

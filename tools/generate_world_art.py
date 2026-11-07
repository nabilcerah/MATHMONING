"""Generate crisp pixel-art for the Number Forest from its layout.

    python tools/generate_world_art.py

The concept painting (assets/backgrounds/New maps.jpg) only has ~8 pixels per tile,
so drawn at game size it looks blurry. This tool keeps the concept's *layout* - the
collision grid from tools/build_world_map.py plus the hand fixes and buildings in
data/maps/number_forest.json - and redraws every tile as 16x16 pixel art at the
game's native resolution:

* assets/backgrounds/number_forest_tiles.png   - the ground, water, forests, houses...
* assets/backgrounds/number_forest_canopy.png  - tree tops drawn over characters, so
                                                 you can walk behind the forest edge

Everything is deterministic (seeded), so re-running gives the same world.
Needs numpy + Pillow (requirements-dev.txt).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.world_map import load_map  # noqa: E402

PAINTING = ROOT / "assets" / "backgrounds" / "number_forest_world.png"
OUT_GROUND = ROOT / "assets" / "backgrounds" / "number_forest_tiles.png"
OUT_CANOPY = ROOT / "assets" / "backgrounds" / "number_forest_canopy.png"
T = 16

# --------------------------------------------------------------------------- palette
C = {
    "grass": (104, 178, 76), "grass_dark": (86, 158, 66), "grass_light": (132, 200, 92), "grass_edge": (74, 138, 58),
    "tall": (62, 140, 66), "tall_dark": (40, 104, 54), "tall_light": (122, 196, 96),
    "dirt": (214, 178, 114), "dirt_dark": (182, 142, 88), "dirt_light": (234, 204, 146), "dirt_edge": (160, 122, 78),
    "sand": (240, 210, 142), "sand_dark": (220, 186, 118), "sand_light": (250, 228, 170), "sand_edge": (196, 160, 98),
    "foam": (232, 248, 252), "shallow": (110, 196, 230), "water": (66, 152, 212), "deep": (48, 124, 190),
    "deeper": (40, 104, 168), "sparkle": (190, 232, 248),
    "forest_floor": (40, 92, 56), "pine_dark": (28, 82, 52), "pine": (44, 118, 66), "pine_light": (78, 156, 80),
    "pine_hi": (120, 190, 98), "trunk": (98, 64, 42), "outline": (22, 40, 34),
    "rock": (132, 124, 118), "rock_dark": (98, 90, 88), "rock_light": (170, 164, 156), "rock_hi": (204, 198, 190),
    "snow": (240, 246, 250), "snow_shade": (196, 214, 230),
    "cliff": (150, 120, 92), "cliff_dark": (110, 84, 64), "cliff_light": (184, 154, 118), "cliff_shadow": (70, 54, 44),
    "soil": (140, 98, 64), "soil_dark": (108, 72, 48), "wheat": (226, 196, 92), "wheat_dark": (190, 156, 64),
    "sprout": (110, 170, 70),
    "wall": (238, 222, 184), "wall_dark": (200, 178, 136), "wood": (120, 82, 54), "window": (96, 150, 190),
    "window_hi": (190, 228, 240), "door": (92, 60, 44),
    "ruin": (92, 98, 96), "ruin_dark": (62, 68, 70), "ruin_light": (124, 130, 126), "moss": (76, 120, 72),
    "sandstone": (206, 160, 106), "sandstone_dark": (168, 122, 78), "sandstone_light": (230, 190, 132),
    "plank": (160, 116, 72), "plank_dark": (118, 82, 52), "rail": (70, 46, 30),
    "stone": (168, 170, 160), "stone_dark": (120, 124, 118), "stone_light": (198, 200, 190),
    "bush": (58, 132, 64), "bush_light": (96, 172, 82), "bush_dark": (36, 92, 50),
}
ROOFS = {"red": ((196, 70, 56), (150, 46, 40), (226, 106, 82)), "orange": ((226, 134, 56), (180, 98, 40), (246, 170, 92)),
         "yellow": ((232, 190, 70), (190, 150, 44), (248, 220, 120)), "blue": ((64, 112, 196), (44, 80, 150), (102, 150, 222)),
         "brown": ((140, 92, 60), (104, 66, 44), (172, 124, 84))}

SAND_ZONES = [(86, 0, 36, 46), (62, 0, 24, 32)]
MOUNTAIN_ZONES = [(24, 0, 46, 27), (46, 24, 20, 14), (66, 37, 13, 9), (102, 52, 16, 16)]
FARM_ZONES = [(0, 80, 32, 34)]
RUIN_ZONES = [(80, 86, 36, 32)]
DESERT = (86, 0, 36, 46)


def inside(x, y, rects):
    return any(rx <= x < rx + rw and ry <= y < ry + rh for rx, ry, rw, rh in rects)


def hash_noise(seed, *shape):
    return np.random.default_rng(seed).random(shape)


def value_noise(size, cell, seed):
    """Smooth noise in [0, 1] at roughly ``cell`` pixel features."""
    coarse = hash_noise(seed, size // cell + 2, size // cell + 2).astype(np.float32)
    image = Image.fromarray(coarse, mode="F").resize((size + cell * 2, size + cell * 2), Image.BICUBIC)
    return np.clip(np.array(image)[cell:cell + size, cell:cell + size], 0, 1)


# --------------------------------------------------------------------------- terrain
def classify(world, painting):
    """Per-tile terrain code for drawing (collision itself comes from the WorldMap)."""
    px = np.array(painting.convert("RGB")).astype(np.int16)
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    forest = (g > r + 12) & (g < 128) & (b < 105)
    dirt = (r > 170) & (g > 130) & (r > b + 45)
    grass = (g > 128) & (g > r + 40) & (b < 110)
    snow = (r > 170) & (g > 180) & (b > 190)
    yellow = (r > 140) & (g > 140) & (b < 90) & (abs(r - g) < 30)
    buildings = {}
    for index, building in enumerate(world.data.get("buildings", [])):
        x0, y0, w, h = building["rect"]
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                buildings[(x, y)] = index
    W, H = world.width, world.height
    grid = [["g"] * W for _ in range(H)]
    frac = {}
    for y in range(H):
        for x in range(W):
            win = (slice(y * 8, y * 8 + 8), slice(x * 8, x * 8 + 8))
            frac[(x, y)] = {k: float(m[win].mean()) for k, m in
                            (("forest", forest), ("dirt", dirt), ("grass", grass), ("snow", snow), ("yellow", yellow))}
    # Blocked non-forest regions: big ones are cliffs, small ones boulders/bushes.
    blocked_other = set()
    for y in range(H):
        for x in range(W):
            t = world.tile_at(x, y)
            f = frac[(x, y)]
            if (x, y) in buildings:
                grid[y][x] = "B"
            elif t == "w":
                grid[y][x] = "W"
            elif t == "G":
                grid[y][x] = "G"
            elif t == "p":
                grid[y][x] = "s" if inside(x, y, SAND_ZONES) else "d"
            elif t == "b":
                grid[y][x] = "b"
            elif t in ("g",):
                if f["dirt"] > max(0.35, f["grass"] * 0.9):
                    grid[y][x] = "s" if inside(x, y, SAND_ZONES) else "d"
                else:
                    grid[y][x] = "g"
            else:  # blocked
                if f["forest"] > 0.28 and not inside(x, y, MOUNTAIN_ZONES):
                    grid[y][x] = "F"
                elif inside(x, y, RUIN_ZONES):
                    grid[y][x] = "R"
                elif inside(x, y, [DESERT]):
                    grid[y][x] = "r" if f["dirt"] < 0.5 else "C"
                elif inside(x, y, FARM_ZONES):
                    grid[y][x] = "f" if f["yellow"] < 0.3 else "h"
                elif inside(x, y, MOUNTAIN_ZONES):
                    grid[y][x] = "M"
                elif f["forest"] > 0.28:
                    grid[y][x] = "F"
                else:
                    blocked_other.add((x, y))
    # Size of each blocked-other cluster decides cliff vs. boulder.
    seen = set()
    for start in blocked_other:
        if start in seen:
            continue
        cluster, stack = [], [start]
        seen.add(start)
        while stack:
            cx, cy = stack.pop()
            cluster.append((cx, cy))
            for n in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if n in blocked_other and n not in seen:
                    seen.add(n)
                    stack.append(n)
        code = "C" if len(cluster) >= 8 else "o"
        for cx, cy in cluster:
            grid[cy][cx] = code
    # Smooth paths: drop lone dirt specks, fill one-tile gaps, so trails read as continuous.
    for _ in range(2):
        changes = []
        for y in range(1, H - 1):
            for x in range(1, W - 1):
                code = grid[y][x]
                if code not in ("g", "d", "s"):
                    continue
                around = [grid[y - 1][x], grid[y + 1][x], grid[y][x - 1], grid[y][x + 1]]
                ground = "s" if inside(x, y, SAND_ZONES) else "d"
                paths = sum(1 for a in around if a in ("d", "s", "b"))
                if code in ("d", "s") and paths == 0 and world.tile_at(x, y) != "p":
                    changes.append((x, y, "g"))
                elif code == "g" and paths >= 3:
                    changes.append((x, y, ground))
        for x, y, code in changes:
            grid[y][x] = code
    # Blue roofs read as water in the painting: tiny "ponds" inside land become grass.
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            if grid[y][x] == "W":
                water_n = sum(grid[y + dy][x + dx] == "W" for dx in (-1, 0, 1) for dy in (-1, 0, 1))
                if water_n <= 2:
                    grid[y][x] = "o"
    return grid, frac


# --------------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.rgb = np.zeros((h, w, 3), dtype=np.uint8)
        self.canopy = np.zeros((h, w, 4), dtype=np.uint8)
        self.h, self.w = h, w

    def rect(self, x, y, w, h, color, layer=None):
        x0, y0, x1, y1 = max(0, x), max(0, y), min(self.w, x + w), min(self.h, y + h)
        if x1 > x0 and y1 > y0:
            (layer if layer is not None else self.rgb)[y0:y1, x0:x1, :3] = color
            if layer is not None:
                layer[y0:y1, x0:x1, 3] = 255

    def px(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.rgb[y, x] = color

    def stamp(self, sprite, x, y, canopy_rows=0):
        """Alpha-stamp an RGBA sprite; its top ``canopy_rows`` rows also go to the canopy layer."""
        sh, sw = sprite.shape[:2]
        for layer, rows in ((self.rgb, sh), (self.canopy, canopy_rows)):
            if not rows:
                continue
            part = sprite[:rows]
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(self.w, x + sw), min(self.h, y + rows)
            if x1 <= x0 or y1 <= y0:
                continue
            src = part[y0 - y:y1 - y, x0 - x:x1 - x]
            mask = src[..., 3] > 0
            region = layer[y0:y1, x0:x1]
            region[..., :3][mask] = src[..., :3][mask]
            if layer is self.canopy:
                region[..., 3][mask] = 255


def sprite_from_rows(rows, palette):
    h, w = len(rows), max(len(r) for r in rows)
    out = np.zeros((h, w, 4), dtype=np.uint8)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                out[y, x, :3] = palette[ch]
                out[y, x, 3] = 255
    return out


def pine(rng, tint=0):
    """A 16x24 pine: three tiers, outlined, light from the upper left."""
    rows = []
    widths = [1, 3, 5, 5, 7, 9, 7, 9, 11, 13, 9, 11, 13, 15, 15, 13]
    for i, width in enumerate(widths):
        pad = (16 - width) // 2
        line = ""
        for x in range(16):
            if x < pad or x >= pad + width:
                line += "."
            elif x == pad or x == pad + width - 1:
                line += "o"
            elif x < pad + width // 3:
                line += "h" if i % 4 in (1, 2) else "l"
            elif x > pad + 2 * width // 3:
                line += "d"
            else:
                line += "m"
        rows.append(line)
    rows += ["......otto......", "......otto......", ".......tt.......", "................",
             "................", "................", "................", "................"]
    shift = lambda c: tuple(max(0, min(255, v + tint)) for v in c)  # noqa: E731
    pal = {"o": C["outline"], "d": shift(C["pine_dark"]), "m": shift(C["pine"]), "l": shift(C["pine_light"]),
           "h": shift(C["pine_hi"]), "t": C["trunk"]}
    return sprite_from_rows(rows, pal)


def peak(width, height, snowy, rng):
    """Mountain peak triangle: lit left face, shaded right face, optional snow cap."""
    out = np.zeros((height, width, 4), dtype=np.uint8)
    cx = width // 2 + rng.integers(-2, 3)
    for y in range(height):
        half = int((y + 1) / height * width / 2)
        for x in range(max(0, cx - half), min(width, cx + half + 1)):
            edge = x in (cx - half, cx + half) or y == height - 1
            if edge:
                color = C["outline"]
            elif snowy and y < height * 0.38 + rng.integers(-1, 2):
                color = C["snow"] if x <= cx else C["snow_shade"]
            elif x < cx - 1:
                color = C["rock_light"] if (x + y) % 7 else C["rock_hi"]
            elif x <= cx:
                color = C["rock"]
            else:
                color = C["rock_dark"] if (x * 3 + y) % 9 else C["rock"]
            out[y, x, :3] = color
            out[y, x, 3] = 255
    return out


def bush(rng):
    rows = ["....oooooo....", "..oollllmmoo..", ".ollhllmmmmmo.", "olllllmmmmmddo", "ollhlmmmmmmddo",
            "olmmmmmmmmdddo", ".ommmmmmmdddo.", "..oommmddoo...", "....oooo......"]
    return sprite_from_rows(rows, {"o": C["outline"], "l": C["bush_light"], "h": C["grass_light"],
                                   "m": C["bush"], "d": C["bush_dark"]})


def boulder():
    rows = ["...oooooo...", "..olllllmo..", ".ollhllmmmo.", "olllllmmmmdo", "ollmmmmmmddo",
            "ommmmmmmdddo", ".odddddddo..", "..oooooooo.."]
    return sprite_from_rows(rows, {"o": C["outline"], "l": C["rock_light"], "h": C["rock_hi"],
                                   "m": C["rock"], "d": C["rock_dark"]})


# --------------------------------------------------------------------------- render
def render(world, grid, frac):
    W, H = world.width, world.height
    size = W * T
    cv = Canvas(size, H * T)
    rng = np.random.default_rng(7)
    noise_fine = hash_noise(11, size, size)
    noise_soft = value_noise(size, 5, 12)
    codes = np.array([[ord(c) for c in row] for row in grid], dtype=np.int32)
    per_px = np.kron(codes, np.ones((T, T), dtype=np.int32))

    def tile_mask(chars, blur_seed):
        """Organic pixel mask for a set of tile codes (curved instead of square edges)."""
        m = np.isin(codes, [ord(c) for c in chars]).astype(np.float32)
        up = np.array(Image.fromarray(m, mode="F").resize((size, size), Image.BILINEAR))
        jitter = (value_noise(size, 4, blur_seed) - 0.5) * 0.36
        return (up + jitter) > 0.5

    # 1. grass everywhere, gently dithered
    rgb = cv.rgb
    rgb[:] = C["grass"]
    rgb[(noise_soft > 0.62) & (noise_fine > 0.55)] = C["grass_dark"]
    rgb[(noise_soft < 0.30) & (noise_fine > 0.75)] = C["grass_light"]
    # grass tufts: little "v" marks
    for y in range(H):
        for x in range(W):
            if grid[y][x] == "g" and rng.random() < 0.55:
                for _ in range(rng.integers(1, 3)):
                    tx, ty = x * T + rng.integers(2, 13), y * T + rng.integers(3, 13)
                    cv.px(tx, ty, C["grass_edge"]); cv.px(tx + 2, ty, C["grass_edge"]); cv.px(tx + 1, ty + 1, C["grass_edge"])
                    cv.px(tx, ty - 1, C["grass_light"]); cv.px(tx + 2, ty - 1, C["grass_light"])

    def layer(mask, base, dark, light, edge, speck=0.08):
        rgb[mask] = base
        rgb[mask & (noise_fine < speck)] = dark
        rgb[mask & (noise_fine > 1 - speck)] = light
        border = mask & ~(np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1))
        rgb[border] = edge
        outside = ~mask & (np.roll(mask, 1, 0) | np.roll(mask, -1, 0) | np.roll(mask, 1, 1) | np.roll(mask, -1, 1))
        grassy = outside & (per_px == ord("g"))
        rgb[grassy] = C["grass_edge"]

    # 2. dirt paths and sand
    dirt = tile_mask("db", 21) & ~np.isin(per_px, [ord("W")])
    layer(dirt, C["dirt"], C["dirt_dark"], C["dirt_light"], C["dirt_edge"])
    sand = tile_mask("s", 22)
    layer(sand, C["sand"], C["sand_dark"], C["sand_light"], C["sand_edge"], 0.06)

    # 3. water with depth from the shore
    water = tile_mask("W", 23)
    depth = np.zeros(water.shape, dtype=np.int16)
    current = water.copy()
    for step in range(1, 14):
        current = current & np.roll(current, 1, 0) & np.roll(current, -1, 0) & np.roll(current, 1, 1) & np.roll(current, -1, 1)
        depth[current] = step
    rgb[water] = C["deeper"]
    rgb[water & (depth < 10)] = C["deep"]
    rgb[water & (depth < 6)] = C["water"]
    rgb[water & (depth < 3)] = C["shallow"]
    rgb[water & (depth == 0)] = C["foam"]
    waves = water & (depth > 4) & (noise_fine > 0.9975)
    rgb[waves] = C["sparkle"]
    # short horizontal wave dashes
    for _ in range(int(water.sum() / 900)):
        y, x = rng.integers(0, size), rng.integers(0, size - 6)
        if water[y, x:x + 6].all() and depth[y, x] > 3:
            rgb[y, x:x + 5] = C["shallow"]

    # 4. per-tile features
    pines = [pine(rng, tint) for tint in (-10, 0, 0, 8, 14)]
    bushes, rock = bush(rng), boulder()
    trees = []
    for y in range(H):
        for x in range(W):
            code = grid[y][x]
            X, Y = x * T, y * T
            if code == "G":
                cv.rect(X, Y, T, T, C["tall"])
                for i in range(4):
                    bx = X + 1 + i * 4 + int(rng.integers(-1, 2))
                    top = Y + 2 + (i % 2) * 3
                    cv.rect(bx, top, 2, Y + T - 1 - top, C["tall_dark"])
                    cv.rect(bx + 1, top, 1, Y + T - 3 - top, C["tall"])
                    cv.rect(bx, top, 2, 2, C["tall_light"])
                cv.rect(X, Y + T - 1, T, 1, C["tall_dark"])
            elif code in ("f", "h"):
                cv.rect(X, Y, T, T, C["soil"])
                for row in range(0, T, 4):
                    cv.rect(X, Y + row + 3, T, 1, C["soil_dark"])
                    for col in range(1, T, 3):
                        if code == "h":
                            cv.rect(X + col, Y + row, 2, 3, C["wheat"])
                            cv.px(X + col, Y + row, C["wheat_dark"])
                        elif (col + row + x) % 2 == 0:
                            cv.rect(X + col, Y + row + 1, 1, 2, C["sprout"])
            elif code == "F":
                cv.rect(X, Y, T, T, C["forest_floor"])
                trees.append((y, x))
            elif code == "M":
                cv.rect(X, Y, T, T, C["rock"])
                for _ in range(6):
                    sx, sy = X + rng.integers(0, 15), Y + rng.integers(0, 15)
                    cv.rect(sx, sy, 2, 1, C["rock_dark"] if rng.random() < 0.6 else C["rock_light"])
            elif code == "C":
                above, below = grid[y - 1][x] if y else "C", grid[y + 1][x] if y + 1 < H else "C"
                if below == "C":
                    # Cliff top: weathered rock with grass creeping over it.
                    cv.rect(X, Y, T, T, C["cliff_light"])
                    for _ in range(5):
                        sx, sy = X + rng.integers(0, 14), Y + rng.integers(0, 14)
                        cv.rect(sx, sy, 3, 1, C["cliff"])
                    if rng.random() < 0.5:
                        cv.rect(X + rng.integers(0, 10), Y + rng.integers(0, 12), 5, 3, C["grass_edge"])
                else:
                    # Cliff face: vertical cracks, strata, darker toward the foot.
                    cv.rect(X, Y, T, T, C["cliff"])
                    cv.rect(X, Y + 10, T, 6, C["cliff_dark"])
                    for col in range((x * 5) % 6, T, 6):
                        cv.rect(X + col, Y + 2, 1, 11, C["cliff_shadow"])
                        cv.rect(X + col + 1, Y + 2, 1, 6, C["cliff_light"])
                    cv.rect(X, Y, T, 2, C["cliff_light"])
                    cv.rect(X, Y + T - 1, T, 1, C["outline"])
                    if below in "gdsG":
                        cv.rect(X, Y + T, T, 3, C["grass_edge"])
                if above not in ("C", "M"):
                    cv.rect(X, Y, T, 2, C["grass_edge"])
                    cv.rect(X, Y + 2, T, 1, C["cliff_shadow"])
            elif code in ("R", "r"):
                base, dark, light = ((C["ruin"], C["ruin_dark"], C["ruin_light"]) if code == "R"
                                     else (C["sandstone"], C["sandstone_dark"], C["sandstone_light"]))
                cv.rect(X, Y, T, T, base)
                for row in range(0, T, 4):
                    cv.rect(X, Y + row, T, 1, dark)
                    off = 0 if (row // 4) % 2 else 4
                    for col in range(off, T, 8):
                        cv.rect(X + col, Y + row, 1, 4, dark)
                cv.rect(X + 1, Y + 1, 3, 1, light)
                if code == "R" and rng.random() < 0.3:
                    cv.rect(X + rng.integers(0, 12), Y + rng.integers(0, 12), 4, 2, C["moss"])
                if y + 1 < H and grid[y + 1][x] not in ("R", "r"):
                    cv.rect(X, Y + T - 3, T, 3, dark)
            elif code == "o":
                sprite = bushes if frac[(x, y)]["grass"] + frac[(x, y)]["forest"] > 0.35 else rock
                cv.stamp(sprite, X + 1, Y + 3)
            elif code == "g" and rng.random() < 0.035 and frac[(x, y)]["grass"] > 0.5:
                for _ in range(3):
                    fx, fy = X + rng.integers(2, 13), Y + rng.integers(2, 13)
                    petal = [(242, 187, 82), (235, 112, 92), (255, 247, 220), (190, 150, 230)][rng.integers(0, 4)]
                    cv.px(fx, fy, petal); cv.px(fx + 1, fy, petal); cv.px(fx, fy + 1, petal); cv.px(fx + 1, fy + 1, (250, 230, 120))

    # 5. mountain peaks, back to front
    def mountain_depth(x, y):
        """How many mountain tiles lie above (x, y): taller peaks only where the range is deep."""
        depth = 0
        while y - depth - 1 >= 0 and grid[y - depth - 1][x] == "M" and depth < 4:
            depth += 1
        return depth

    peak_rng = np.random.default_rng(31)
    for y in range(H):
        for x in range(W):
            if grid[y][x] != "M" or peak_rng.random() > 0.3:
                continue
            depth = mountain_depth(x, y)
            if depth == 0 and peak_rng.random() < 0.6:
                continue
            height = int(min(16 + depth * 9, 52) * peak_rng.uniform(0.8, 1.05))
            width = int(height * peak_rng.uniform(1.25, 1.6))
            snowy = (y < 16 and height > 28) or frac[(x, y)]["snow"] > 0.2
            cv.stamp(peak(width, height, snowy, rng), x * T + 8 - width // 2 + int(peak_rng.integers(-4, 5)),
                     y * T + T - height)

    # 6. forests: overlapping pines from back to front; tops spill into the canopy layer
    for y, x in sorted(trees):
        sprite = pines[int(rng.integers(0, len(pines)))]
        ox, oy = int(rng.integers(-2, 3)), int(rng.integers(-1, 2))
        top = y * T - 8 + oy
        spill = 8 - oy if y > 0 and grid[y - 1][x] != "F" else 0
        cv.stamp(sprite, x * T + ox, top, canopy_rows=max(0, spill))
        if y + 1 < H and grid[y + 1][x] != "F":
            cv.rect(x * T + 3, (y + 1) * T, 10, 2, C["grass_edge"])  # soft shadow on the grass below

    # 7. buildings
    for building in world.data.get("buildings", []):
        x0, y0, w, h = building["rect"]
        roof, roof_dark, roof_light = ROOFS.get(building.get("roof", "red"), ROOFS["red"])
        X, Y, Wp, Hp = x0 * T, y0 * T, w * T, h * T
        roof_h = int(Hp * 0.58)
        cv.rect(X + 1, Y + roof_h, Wp - 2, Hp - roof_h, C["wall"])
        for row in range(roof_h + 4, Hp, 5):
            cv.rect(X + 1, Y + row, Wp - 2, 1, C["wall_dark"])
        cv.rect(X - 1, Y + 2, Wp + 2, roof_h, C["outline"])
        cv.rect(X, Y + 3, Wp, roof_h - 2, roof)
        for row in range(5, roof_h, 4):
            cv.rect(X, Y + row, Wp, 1, roof_dark)
        cv.rect(X + 1, Y + 4, Wp - 2, 1, roof_light)
        cv.rect(X + Wp // 2 - 1, Y + 1, 2, roof_h, roof_dark)  # ridge line
        door_x = X + Wp // 2 - 3
        cv.rect(door_x, Y + Hp - 9, 6, 9, C["door"])
        cv.px(door_x + 4, Y + Hp - 5, (242, 187, 82))
        for wx in (X + 4, X + Wp - 10):
            if abs(wx - door_x) > 6:
                cv.rect(wx, Y + roof_h + 3, 6, 5, C["outline"])
                cv.rect(wx + 1, Y + roof_h + 4, 4, 3, C["window"])
                cv.px(wx + 1, Y + roof_h + 4, C["window_hi"])
        cv.rect(X - 1, Y + roof_h, 1, Hp - roof_h, C["outline"])
        cv.rect(X + Wp, Y + roof_h, 1, Hp - roof_h, C["outline"])
        cv.rect(X - 1, Y + Hp, Wp + 2, 2, C["grass_edge"])

    # 8. bridges: wooden planks (trails style "bridge" and the painted plank crossing) and the stone bridge
    def plank_bridge(rect):
        x0, y0, w, h = rect
        X, Y, Wp, Hp = x0 * T, y0 * T, w * T, h * T
        cv.rect(X, Y, Wp, Hp, C["plank_dark"])
        if h > w:
            for row in range(1, Hp, 4):
                cv.rect(X + 2, Y + row, Wp - 4, 3, C["plank"])
            cv.rect(X, Y, 2, Hp, C["rail"]); cv.rect(X + Wp - 2, Y, 2, Hp, C["rail"])
        else:
            for col in range(1, Wp, 4):
                cv.rect(X + col, Y + 2, 3, Hp - 4, C["plank"])
            cv.rect(X, Y, Wp, 2, C["rail"]); cv.rect(X, Y + Hp - 2, Wp, 2, C["rail"])

    for trail in world.data.get("trails", []):
        if trail.get("style") == "bridge":
            plank_bridge(trail["rect"])
    plank_bridge([73, 32, 7, 2])
    x0, y0, w, h = 75, 62, 8, 4  # stone bridge
    X, Y, Wp, Hp = x0 * T, y0 * T, w * T, h * T
    cv.rect(X, Y - 4, Wp, Hp + 8, C["stone_dark"])
    cv.rect(X, Y, Wp, Hp, C["stone"])
    for row in range(0, Hp, 6):
        cv.rect(X, Y + row + 5, Wp, 1, C["stone_dark"])
        offset = 0 if (row // 6) % 2 else 6
        for col in range(offset, Wp, 12):
            cv.rect(X + col, Y + row, 1, 5, C["stone_dark"])
            cv.rect(X + col + 1, Y + row, 4, 1, C["stone_light"])
    for rail_y in (Y - 4, Y + Hp):
        cv.rect(X, rail_y, Wp, 4, C["stone_light"])
        cv.rect(X, rail_y + 3, Wp, 1, C["outline"])
        for post in range(0, Wp, 16):
            cv.rect(X + post, rail_y - 2, 4, 6, C["stone_dark"])

    # 9. the waterfall
    for y in range(33, 42):
        for x in range(74, 78):
            if grid[y][x] == "W":
                X, Y = x * T, y * T
                cv.rect(X, Y, T, T, C["shallow"])
                for col in range(0, T, 3):
                    length = 6 + (col * 7 + y * 3) % 8
                    cv.rect(X + col, Y + (y * 5 + col) % 9, 1, length, C["foam"])
    return cv


def main():
    world = load_map()
    painting = Image.open(PAINTING)
    grid, frac = classify(world, painting)
    canvas = render(world, grid, frac)
    Image.fromarray(canvas.rgb).save(OUT_GROUND, optimize=True)
    Image.fromarray(canvas.canopy, mode="RGBA").save(OUT_CANOPY, optimize=True)
    counts = {}
    for row in grid:
        for code in row:
            counts[code] = counts.get(code, 0) + 1
    print("terrain tiles:", dict(sorted(counts.items(), key=lambda kv: -kv[1])))
    print("wrote", OUT_GROUND.name, OUT_CANOPY.name)


if __name__ == "__main__":
    main()

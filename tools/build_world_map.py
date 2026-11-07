"""Turn the painted concept map into a playable world: background + collision grid.

    python tools/build_world_map.py [--preview]

* Crops the parchment border from ``assets/backgrounds/New maps.jpg`` and saves the
  painting as ``assets/backgrounds/number_forest_world.png`` (the game scales it 2x).
* Classifies every 8x8 block of the painting (one 16px tile in game) as walkable
  grass/path/sand, water, or blocked (forest, mountains, cliffs, buildings) and writes
  ``data/maps/number_forest_collision.txt`` ('.' walk, '~' water, '#' blocked).

Hand fixes (bridges, doorways, encounter grass...) live in data/maps/number_forest.json as
``walkable`` / ``blocked`` / ``encounters`` rects and are applied by the game at load time,
so re-running this tool never overwrites them. Needs numpy + Pillow (requirements-dev.txt).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "backgrounds" / "New maps.jpg"
BACKGROUND = ROOT / "assets" / "backgrounds" / "number_forest_world.png"
COLLISION = ROOT / "data" / "maps" / "number_forest_collision.txt"
MAP_JSON = ROOT / "data" / "maps" / "number_forest.json"
CROP = (24, 24, 1000, 1000)   # inside the parchment frame
BLOCK = 8                      # painting pixels per game tile (the game draws the painting at 2x)


def classify(rgb):
    r, g, b = (rgb[..., i].astype(np.int16) for i in range(3))
    water = (b > g + 8) & (b > r + 45)
    grass = (g > 128) & (g > r + 40) & (b < 110)
    sand = (r > 175) & (g > 135) & (r > b + 45)
    forest = (g > r + 12) & (g < 128) & (b < 105)
    return water, grass, sand, forest


def build():
    painting = Image.open(SOURCE).convert("RGB").crop(CROP)
    BACKGROUND.parent.mkdir(parents=True, exist_ok=True)
    painting.save(BACKGROUND, optimize=True)
    pixels = np.array(painting)
    water, grass, sand, forest = classify(pixels)
    rows = []
    tiles = pixels.shape[0] // BLOCK
    for ty in range(tiles):
        line = []
        for tx in range(pixels.shape[1] // BLOCK):
            window = (slice(ty * BLOCK, (ty + 1) * BLOCK), slice(tx * BLOCK, (tx + 1) * BLOCK))
            w, gr, sa, fo = (mask[window].mean() for mask in (water, grass, sand, forest))
            if w > 0.5:
                line.append("~")
            elif gr + sa >= 0.5 and fo < 0.3:
                line.append(".")
            else:
                line.append("#")
        rows.append("".join(line))
    COLLISION.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return painting, rows


def preview(painting, rows, path):
    """Painting at 2x with the final collision (including hand fixes) tinted on top."""
    data = json.loads(MAP_JSON.read_text(encoding="utf-8")) if MAP_JSON.exists() else {}
    grid = [list(row) for row in rows]

    def paint(rects, code):
        for x, y, w, h in rects:
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    if 0 <= yy < len(grid) and 0 <= xx < len(grid[0]):
                        grid[yy][xx] = code

    paint(data.get("blocked", []), "#")
    paint(data.get("walkable", []), ".")
    paint(data.get("encounters", []), "G")
    image = painting.resize((painting.width * 2, painting.height * 2), Image.NEAREST).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    colors = {"#": (255, 0, 0, 70), "~": (0, 0, 255, 60), "G": (255, 255, 0, 90)}
    for y, row in enumerate(grid):
        for x, code in enumerate(row):
            if code in colors:
                draw.rectangle((x * 16, y * 16, x * 16 + 15, y * 16 + 15), fill=colors[code])
    for x in range(0, image.width, 160):
        draw.line((x, 0, x, image.height), fill=(255, 255, 255, 90))
        draw.text((x + 2, 2), str(x // 16), fill=(255, 255, 255, 255))
    for y in range(0, image.height, 160):
        draw.line((0, y, image.width, y), fill=(255, 255, 255, 90))
        draw.text((2, y + 2), str(y // 16), fill=(255, 255, 255, 255))
    Image.alpha_composite(image, overlay).convert("RGB").save(path, quality=88)


if __name__ == "__main__":
    painting, rows = build()
    walk = sum(row.count(".") for row in rows)
    print(f"{len(rows)}x{len(rows[0])} tiles, {walk} walkable -> {BACKGROUND.name}, {COLLISION.name}")
    if "--preview" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--preview") + 1]) if len(sys.argv) > sys.argv.index("--preview") + 1 \
            else ROOT / "assets" / "backgrounds" / "_collision_preview.jpg"
        preview(painting, rows, out)
        print("preview:", out)

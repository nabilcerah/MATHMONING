"""Create recoloured monster variants (Crystal Realm forms, GRAPHION, the GDD evolutions and the boss).

    python tools/make_variants.py

Reads the processed frames in assets/sprites/monsters/<BASE>/ and writes hue-shifted copies to
assets/sprites/monsters/<VARIANT>/ with the same manifest, so poses and alignment carry over.
Outlines and very dark pixels keep their colour, which keeps the art crisp after recolouring.
Needs numpy + Pillow (requirements-dev.txt).
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MONSTERS = ROOT / "assets" / "sprites" / "monsters"

# variant: (base, hue shift in turns, saturation multiplier, value multiplier)
VARIANTS = {
    "PRISMVOLT": ("VOLTIX", -0.25, 1.10, 1.10),    # crystal fox: cyan body, pink tails
    "OPALOWL": ("DIVOWL", 0.48, 1.05, 1.08),       # crystal owl: violet/pink
    "GEMELLA": ("FRACTELLA", -0.30, 1.10, 1.00),   # gem slime: emerald/teal
    "GRAPHION": ("CHRONOX", 0.58, 1.25, 1.28),     # secret: cosmic blue-violet clockwork dragon
    # GDD evolutions (stage 2): a new colourway on top of the larger drawn size.
    "PRISMELLA": ("FRACTELLA", 0.10, 1.20, 1.08),  # rose-gold crystal slime
    "GEOMAXIMUS": ("GEOMAX", -0.12, 1.15, 1.05),   # weathered bronze golem
    "NULLAREX": ("NUMEREX", 0.42, 1.10, 1.12),     # teal void phantom
    "CHRONODRAKE": ("CHRONOX", -0.07, 1.30, 1.10), # molten-gold clockwork dragon
    # The boss form of NUMEREX: darker and redder than the starter.
    "NUMEREX_BOSS": ("NUMEREX", 0.12, 1.25, 0.80),
    # World 3 boss: the lava dragon refolded into a violet dimension-dragon.
    "DIMENSION_DRAGON": ("INFERMATH", 0.62, 1.15, 0.95),
}


def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    delta = mx - mn
    hue = np.zeros_like(mx)
    mask = delta > 1e-6
    rc = np.where(mask, (mx - r) / np.where(mask, delta, 1), 0)
    gc = np.where(mask, (mx - g) / np.where(mask, delta, 1), 0)
    bc = np.where(mask, (mx - b) / np.where(mask, delta, 1), 0)
    hue = np.where(r == mx, bc - gc, np.where(g == mx, 2.0 + rc - bc, 4.0 + gc - rc))
    hue = np.where(mask, (hue / 6.0) % 1.0, 0)
    sat = np.where(mx > 1e-6, delta / np.where(mx > 1e-6, mx, 1), 0)
    return np.stack([hue, sat, mx], -1)


def hsv_to_rgb(hsv):
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    i = np.floor(h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    choices = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]
    out = np.zeros(hsv.shape)
    for index, (rr, gg, bb) in enumerate(choices):
        sel = i == index
        out[..., 0][sel], out[..., 1][sel], out[..., 2][sel] = rr[sel], gg[sel], bb[sel]
    return out


def recolour(image, shift, sat_mul, val_mul):
    data = np.array(image.convert("RGBA")).astype(np.float64)
    rgb = data[..., :3] / 255.0
    hsv = rgb_to_hsv(rgb)
    keep = (hsv[..., 2] < 0.18) | (hsv[..., 1] < 0.08)  # outlines, near-greys stay as drawn
    shifted = hsv.copy()
    shifted[..., 0] = (shifted[..., 0] + shift) % 1.0
    shifted[..., 1] = np.clip(shifted[..., 1] * sat_mul, 0, 1)
    shifted[..., 2] = np.clip(shifted[..., 2] * val_mul, 0, 1)
    new_rgb = hsv_to_rgb(shifted)
    rgb = np.where(keep[..., None], rgb, new_rgb)
    data[..., :3] = np.clip(rgb * 255.0, 0, 255)
    return Image.fromarray(data.astype(np.uint8), "RGBA")


# Story characters used to be recoloured from other sheets. Since the 9 Nov art drop VERA, STRANGER and
# ABACUS have their own art (tools/process_monster_sprites.py), so nothing is recoloured any more.
CHARACTER_VARIANTS = {}


def main():
    jobs = [(MONSTERS / base, MONSTERS / name, name, base, *rest) for name, (base, *rest) in VARIANTS.items()]
    characters = MONSTERS.parent / "characters"
    jobs += [(characters / base, characters / name, name, base, *rest) for name, (base, *rest) in CHARACTER_VARIANTS.items()]
    for source, target, name, base, shift, sat_mul, val_mul in jobs:
        target.mkdir(parents=True, exist_ok=True)
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        for pose in manifest["poses"]:
            recolour(Image.open(source / pose["file"]), shift, sat_mul, val_mul).save(target / pose["file"])
        manifest.update({"name": name, "variant_of": base})
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"{name:10} <- {base}")


if __name__ == "__main__":
    main()

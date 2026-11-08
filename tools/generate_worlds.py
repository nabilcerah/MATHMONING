"""Generate GDD worlds 2-4: layout, collision, map data and pixel art.

    python tools/generate_worlds.py            # all three
    python tools/generate_worlds.py algebra_cavern

Every world shares one shape, re-themed: an arrival camp (west), two wild areas (north and south)
and a sanctum (east) with three seals and the boss gate, joined by a ring of 2-wide passages.

    WORLD 2  Algebra Cavern     - crystal caves, tunnels, an ancient laboratory (THE UNKNOWN GUARDIAN)
    WORLD 3  Geometry Kingdom   - temples, stone courts, a castle keep            (THE DIMENSION DRAGON)
    WORLD 4  Chronos Dimension  - floating islands, clockwork, the Time Spire      (THE INFINITE OVERLORD)

Writes data/maps/<world>.json, data/maps/<world>_collision.txt and
assets/backgrounds/<world>_tiles.png / _canopy.png. Deterministic. Needs numpy + Pillow (requirements-dev.txt).
Every interactable is checked to be reachable before anything is written.
"""
import json
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
W, H, T = 64, 48, 16

# --------------------------------------------------------------------------- world definitions
NPC_LOOKS = {
    "scientist": {"hair": "#e8e8e8", "skin": "#e0ae82", "clothes": "#f0f0f0", "accent": "#3fb0a0", "pants": "#2a2a35", "shoes": "#3a2418"},
    "knight": {"hair": "#5a3a1a", "skin": "#c08a5e", "clothes": "#8a8fa0", "accent": "#e2c35b", "pants": "#3a3f50", "shoes": "#2a1d14"},
    "keeper": {"hair": "#d0a040", "skin": "#e9b48e", "clothes": "#5a3f8a", "accent": "#f2bb52", "pants": "#2e3240", "shoes": "#2a1d14"},
    "merchant": {"hair": "#b8522e", "skin": "#f0c49b", "clothes": "#c0392b", "accent": "#f2bb52", "pants": "#2e3240", "shoes": "#2a1d14"},
}

WORLDS = {
    "algebra_cavern": {
        "name": "Algebra Cavern", "theme": "cave", "seed": 21,
        "rooms": {"A": (11, 24, 8.5, 7.5), "B": (30, 12, 10.5, 7.5), "C": (30, 36, 10.5, 7.5), "D": (51, 24, 9.5, 8.5)},
        "areas": {"A": ("cave_mouth", "Cave Mouth"), "B": ("glow_tunnels", "Glow Tunnels"),
                  "C": ("echo_hollow", "Echo Hollow"), "D": ("lost_lab", "Lost Laboratory"),
                  "passages": ("cavern_passages", "Cavern Passages")},
        "back": {"destination": "number_forest", "arrive": [76, 103], "title": "CAVE EXIT",
                 "text": ["Daylight from the Number Forest shines through. Climb back out?"]},
        "forward": {"destination": "geometry_kingdom", "requires": "boss:guardian", "title": "LAB GATEWAY",
                    "text": ["A doorway of light opens onto a kingdom of perfect shapes. Step through?"],
                    "locked": ["The gateway is dark. The Unknown Guardian still holds the lab's power."]},
        "gate": {"name": "guardian chamber", "title": "THE GUARDIAN'S CHAMBER", "boss": "EQUINOX_BOSS", "level": 14,
                 "flag": "boss:guardian", "seals": ["challenge:seal_x1", "challenge:seal_x2", "challenge:seal_x3"],
                 "sealed": "Three Variable Seals bind the chamber door.",
                 "where": "Find the Seal of Unknowns, the Seal of Balance and the Seal of Pairs in the cavern.",
                 "open": "The seals flare and the chamber door slides open. A golden scarab weighs you up...",
                 "fight": "Face the guardian!",
                 "victory": "THE UNKNOWN GUARDIAN is defeated! The lab's gateway hums to life - the Geometry Kingdom awaits.",
                 "quiet": "The chamber is calm. Every unknown here has been found."},
        "seals": {"seal_x1": ("B", "Seal of Unknowns"), "seal_x2": ("C", "Seal of Balance"), "seal_x3": ("D", "Seal of Pairs")},
        "side": {"id": "lab_terminal", "room": "C", "challenge": "lab_notes", "name": "lab terminal", "verb": "Read",
                 "title": "THE LAB NOTES", "text": ["An old terminal flickers. Half the notes are missing."]},
        "npc": {"id": "vexa", "name": "Dr. Vexa", "role": "Cave Scientist", "quest": "unknown_guardian", "look": "scientist",
                "dialogue": {"not_started": ["You came through the ruins? Then you're the trainer who beat the Arithmetic Beast!",
                                             "This is the Algebra Cavern. My old lab is sealed by three Variable Seals, and "
                                             "something guards the chamber beyond. Win a few battles to warm up, then restore the seals."],
                             "active": ["The seals answer to algebra: find the unknown, keep both sides balanced, and solve pairs together."],
                             "completed": ["The lab is ours again! Its gateway leads to the Geometry Kingdom."]}},
        "chests": [("B", "Greater Potion", 2), ("C", "Math Capsule", 3)],
        "sign": ["ALGEBRA CAVERN", "Monsters here think in unknowns. Every x has a value - find it!"],
    },
    "geometry_kingdom": {
        "name": "Geometry Kingdom", "theme": "kingdom", "seed": 33,
        "rooms": {"A": (11, 24, 8.5, 7.5), "B": (31, 12, 11.5, 7.5), "C": (31, 36, 11.5, 7.5), "D": (51, 24, 9.5, 9.0)},
        "areas": {"A": ("temple_gate", "Temple Gate"), "B": ("garden_court", "Garden Court"),
                  "C": ("pillar_court", "Pillar Court"), "D": ("dragon_keep", "Dragon Keep"),
                  "passages": ("kingdom_roads", "Royal Roads")},
        "back": {"destination": "algebra_cavern", "arrive": [48, 29], "title": "TEMPLE DOORWAY",
                 "text": ["The doorway leads back to the Algebra Cavern's laboratory. Go back?"]},
        "forward": {"destination": "chronos_dimension", "requires": "boss:dragon", "title": "SUNDIAL PORTAL",
                    "text": ["The sundial's shadow spins. Beyond it, islands float in frozen time. Step through?"],
                    "locked": ["The sundial casts no shadow while the Dimension Dragon rules the keep."]},
        "gate": {"name": "keep gate", "title": "THE DRAGON KEEP", "boss": "DIMENSION_DRAGON", "level": 17,
                 "flag": "boss:dragon", "seals": ["challenge:seal_g1", "challenge:seal_g2", "challenge:seal_g3"],
                 "sealed": "Three Geometry Seals lock the keep's great gate.",
                 "where": "Find the Seal of Areas, the Seal of Angles and the Seal of Solids.",
                 "open": "The gate unfolds like paper. A dragon made of shapes uncurls inside...",
                 "fight": "Face the dragon!",
                 "victory": "THE DIMENSION DRAGON is defeated! The sundial's shadow spins - the Chronos Dimension opens.",
                 "quiet": "The keep is still. Every shape is back where it belongs."},
        "seals": {"seal_g1": ("B", "Seal of Areas"), "seal_g2": ("C", "Seal of Angles"), "seal_g3": ("D", "Seal of Solids")},
        "side": {"id": "garden_plan", "room": "B", "challenge": "royal_garden", "name": "garden plans", "verb": "Read",
                 "title": "THE ROYAL GARDEN", "text": ["The royal gardener's plans, covered in shapes and question marks."]},
        "npc": {"id": "hypot", "name": "Sir Hypot", "role": "Royal Knight", "quest": "dimension_dragon", "look": "knight",
                "dialogue": {"not_started": ["Halt, traveller! ...Ah, a trainer. Welcome to the Geometry Kingdom.",
                                             "The Dimension Dragon has folded our castle into impossible shapes. Cross to "
                                             "the Pillar Court, restore the three Geometry Seals and the keep will open."],
                             "active": ["Areas, angles and solids - the three seals measure everything. Measure carefully!"],
                             "completed": ["The kingdom is square again - in the best way. Onward to Chronos!"]}},
        "chests": [("B", "Revival Crystal", 1), ("C", "Greater Potion", 2)],
        "sign": ["GEOMETRY KINGDOM", "Every stone here was cut to an exact measure. So were its monsters."],
    },
    "chronos_dimension": {
        "name": "Chronos Dimension", "theme": "chronos", "seed": 47,
        "rooms": {"A": (11, 24, 8.5, 7.5), "B": (30, 11, 10.5, 7.5), "C": (30, 37, 10.5, 7.5), "D": (51, 24, 9.5, 8.5)},
        "areas": {"A": ("clock_gate", "Clock Gate"), "B": ("tick_isles", "Tick Isles"),
                  "C": ("tock_isles", "Tock Isles"), "D": ("time_spire", "Time Spire"),
                  "passages": ("time_bridges", "Time Bridges")},
        "back": {"destination": "geometry_kingdom", "arrive": [48, 31], "title": "SUNDIAL RETURN",
                 "text": ["The sundial leads back to the Geometry Kingdom. Go back?"]},
        "forward": {"destination": "number_forest", "requires": "boss:overlord", "title": "HOMEWARD PORTAL",
                    "text": ["Time flows again. The portal leads home to the Number Forest. Go home?"],
                    "arrive": [16, 60],
                    "locked": ["The homeward portal is frozen while the Infinite Overlord holds time."]},
        "gate": {"name": "spire gate", "title": "THE TIME SPIRE", "boss": "INFINITY_ZERO_BOSS", "level": 20,
                 "flag": "boss:overlord", "seals": ["challenge:seal_t1", "challenge:seal_t2", "challenge:seal_t3"],
                 "sealed": "Three Time Seals hold the spire shut.",
                 "where": "Restore the Seal of Patterns, the Seal of Hours and the Seal of Infinity.",
                 "open": "Every clock in the dimension strikes at once. At the top of the spire, something endless waits...",
                 "fight": "Face the Overlord!",
                 "victory": "THE INFINITE OVERLORD is defeated! Time flows again and the Numera returns to all of Mathea. You did it, Numera Trainer!",
                 "quiet": "The spire ticks peacefully. Time flows again across Mathea."},
        "seals": {"seal_t1": ("B", "Seal of Patterns"), "seal_t2": ("C", "Seal of Hours"), "seal_t3": ("D", "Seal of Infinity")},
        "side": {"id": "clock_shrine", "room": "C", "challenge": "broken_clocks", "name": "broken clocks", "verb": "Repair",
                 "title": "THE BROKEN CLOCKS", "text": ["Three stopped clocks hang in the air."]},
        "npc": {"id": "tick", "name": "Keeper Tick", "role": "Time Keeper", "quest": "infinite_overlord", "look": "keeper",
                "dialogue": {"not_started": ["...tick... tock... Oh! Someone is still moving in time!",
                                             "The Infinite Overlord has stopped every clock in the Chronos Dimension. Win a few "
                                             "battles on the isles, restore the three Time Seals, and climb the Time Spire."],
                             "active": ["Patterns, hours and infinity - the three seals keep time itself."],
                             "completed": ["Time flows again! The whole of Mathea has its Numera back."]}},
        "chests": [("B", "Revival Crystal", 2), ("C", "Greater Potion", 3)],
        "sign": ["CHRONOS DIMENSION", "Time stands still here. Only patterns still move."],
    },
}

# --------------------------------------------------------------------------- layout
LINKS = (("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"))


def inside(room, x, y):
    cx, cy, rx, ry = room
    angle = math.atan2(y - cy, x - cx)
    wobble = 1 + 0.07 * math.sin(angle * 5 + cx) + 0.05 * math.sin(angle * 9 + cy)
    return ((x - cx) / (rx * wobble)) ** 2 + ((y - cy) / (ry * wobble)) ** 2 <= 1


def build_layout(cfg):
    rooms = cfg["rooms"]
    ground = np.zeros((H, W), dtype=bool)
    room_of = np.full((H, W), "", dtype=object)
    for key, room in rooms.items():
        for y in range(H):
            for x in range(W):
                if inside(room, x, y):
                    ground[y, x] = True
                    room_of[y, x] = key
    corridor = np.zeros((H, W), dtype=bool)
    for a, b in LINKS:
        ax, ay = int(rooms[a][0]), int(rooms[a][1])
        bx, by = int(rooms[b][0]), int(rooms[b][1])
        for x in range(min(ax, bx), max(ax, bx) + 2):      # horizontal leg at a's row
            corridor[ay:ay + 2, x] = True
        for y in range(min(ay, by), max(ay, by) + 2):      # vertical leg at b's column
            corridor[y, bx:bx + 2] = True
    grass = {}
    for key in ("B", "C"):
        cx, cy = int(rooms[key][0]), int(rooms[key][1])
        grass[key] = [(cx - 7, cy - 5, 6, 3), (cx + 2, cy + 2, 6, 3)]
    return ground, corridor, room_of, grass


def reserved_mask(corridor, grass, cells):
    reserved = corridor.copy()
    for rects in grass.values():
        for x0, y0, w, h in rects:
            reserved[max(0, y0 - 1):y0 + h + 1, max(0, x0 - 1):x0 + w + 1] = True
    for x, y in cells:
        reserved[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = True
    return reserved


def place(ground, corridor, taken, cfg, room_key, target, grass=()):
    """The nearest ground cell to ``target`` in the room that is not a corridor or already used."""
    room = cfg["rooms"][room_key]
    best = None
    for y in range(H):
        for x in range(W):
            if not ground[y, x] or corridor[y, x] or not inside(room, x, y) or (x, y) in taken:
                continue
            if any(x0 - 1 <= x <= x0 + w and y0 - 1 <= y <= y0 + h for x0, y0, w, h in grass):
                continue
            if any(abs(x - tx) <= 1 and abs(y - ty) <= 1 for tx, ty in taken):
                continue
            d = abs(x - target[0]) + abs(y - target[1])
            if best is None or d < best[0]:
                best = (d, (x, y))
    taken.add(best[1])
    return list(best[1])


def objects_for(world_id, cfg, ground, corridor, grass):
    rooms = cfg["rooms"]
    taken = set()

    def at(key, dx, dy):
        cx, cy = int(rooms[key][0]), int(rooms[key][1])
        rects = [r for rs in grass.values() for r in rs]
        return place(ground, corridor, taken, cfg, key, (cx + dx, cy + dy), rects)

    objs, npcs, waypoints = [], [], {}
    spawn = [int(rooms["A"][0]) - 1, int(rooms["A"][1])]
    taken.add(tuple(spawn))
    back = cfg["back"]
    objs.append({"id": f"{world_id}_back", "kind": "portal", "pos": at("A", -5, -3), "destination": back["destination"],
                 "arrive": back["arrive"], "name": "portal", "verb": "Enter", "title": back["title"], "text": back["text"]})
    objs.append({"id": f"{world_id}_spring", "kind": "spring", "pos": at("A", -5, 3), "name": "healing spring",
                 "verb": "Use", "title": "HEALING SPRING", "text": ["Warm Numera water bubbles up here."]})
    objs.append({"id": f"{world_id}_sign", "kind": "sign", "pos": at("A", 0, -5), "name": "sign", "verb": "Read",
                 "title": cfg["sign"][0], "text": cfg["sign"][1:]})
    npc = cfg["npc"]
    waypoints[f"{npc['id']}_spot"] = at("A", 4, -3)
    waypoints["merchant_spot"] = at("A", 4, 3)
    taken.discard(tuple(waypoints[f"{npc['id']}_spot"]))
    taken.discard(tuple(waypoints["merchant_spot"]))
    npcs.append({"id": npc["id"], "name": npc["name"], "role": npc["role"], "kind": "quest", "quest": npc["quest"],
                 "look": NPC_LOOKS[npc["look"]], "routine": [{"waypoint": f"{npc['id']}_spot", "wait": 8, "face": "down"}],
                 "dialogue": npc["dialogue"], "remarks": ["Good luck, trainer!", "Mind the seals..."]})
    npcs.append({"id": f"{world_id}_merchant", "name": "Wandering Merchant", "role": "Merchant", "kind": "shop",
                 "look": NPC_LOOKS["merchant"], "routine": [{"waypoint": "merchant_spot", "wait": 8, "face": "down"}],
                 "dialogue": {"any": ["Potions, capsules and crystals - the same fair prices as the village shop!"]},
                 "remarks": ["Fresh capsules!", "Fair prices, far from home."]})
    offsets = {"B": (5, -4), "C": (5, -4), "D": (-5, -4)}
    for seal_id, (key, name) in cfg["seals"].items():
        objs.append({"id": seal_id, "kind": "challenge", "challenge": seal_id, "pos": at(key, *offsets[key]),
                     "name": name, "verb": "Restore", "title": name.upper(),
                     "text": [f"The {name} is cracked and dark."]})
    side = cfg["side"]
    objs.append({"id": side["id"], "kind": "challenge", "challenge": side["challenge"], "pos": at(side["room"], -5, 4),
                 "name": side["name"], "verb": side["verb"], "title": side["title"], "text": side["text"]})
    for i, (key, item, count) in enumerate(cfg["chests"]):
        objs.append({"id": f"{world_id}_chest{i + 1}", "kind": "chest", "pos": at(key, 7, 1), "name": "chest",
                     "verb": "Open", "item": item, "count": count, "title": "TREASURE CHEST"})
    gate = dict(cfg["gate"])
    gate_pos = at("D", 3, -1)
    objs.append({"id": f"{world_id}_gate", "kind": "boss_gate", "pos": gate_pos, "verb": "Approach", **gate})
    forward = cfg["forward"]
    objs.append({"id": f"{world_id}_forward", "kind": "portal", "pos": at("D", 3, 5), "destination": forward["destination"],
                 "arrive": forward.get("arrive", [12, 25]), "requires": forward["requires"], "name": "portal",
                 "verb": "Enter", "title": forward["title"], "text": forward["text"], "locked_text": forward["locked"]})
    return spawn, objs, npcs, waypoints


def spires_for(cfg, ground, corridor, room_of, grass, objs, waypoints, spawn):
    rng = np.random.default_rng(cfg["seed"])
    cells = [tuple(o["pos"]) for o in objs] + [tuple(c) for c in waypoints.values()] + [tuple(spawn)]
    reserved = reserved_mask(corridor, grass, cells)
    spires = np.zeros((H, W), dtype=bool)
    for key, (cx, cy, rx, ry) in cfg["rooms"].items():
        candidates = [(x, y) for y in range(H) for x in range(W) if ground[y, x] and room_of[y, x] == key
                      and not reserved[y, x] and 0.55 < math.hypot((x - cx) / rx, (y - cy) / ry) < 0.85]
        rng.shuffle(candidates)
        placed = []
        for x, y in candidates:
            if len(placed) >= 5:
                break
            if all(abs(x - px) + abs(y - py) > 4 for px, py in placed):
                placed.append((x, y))
                spires[y, x] = True
    return spires


def walkable(ground, corridor, spires, objs):
    blocked = {tuple(o["pos"]) for o in objs}
    return lambda x, y: 0 <= x < W and 0 <= y < H and (ground[y, x] or corridor[y, x]) and not spires[y, x] \
        and (x, y) not in blocked


def check_reachable(spawn, objs, waypoints, is_walkable, grass):
    seen, queue = {tuple(spawn)}, deque([tuple(spawn)])
    while queue:
        x, y = queue.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in seen and is_walkable(*n):
                seen.add(n)
                queue.append(n)
    for o in objs:
        x, y = o["pos"]
        assert any(n in seen for n in ((x, y + 1), (x, y - 1), (x + 1, y), (x - 1, y))), o["id"]
    for name, cell in waypoints.items():
        assert tuple(cell) in seen, name
    for rects in grass.values():
        for x0, y0, w, h in rects:
            assert all((x, y) in seen for x in range(x0, x0 + w) for y in range(y0, y0 + h)), (x0, y0)
    return seen


def map_data(world_id, cfg, ground, corridor, room_of, grass, spires, spawn, objs, npcs, waypoints):
    rows = ["".join("." if (ground[y, x] or corridor[y, x]) and not spires[y, x] else "#" for x in range(W))
            for y in range(H)]
    (ROOT / f"data/maps/{world_id}_collision.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    areas = []
    for key in ("A", "B", "C", "D"):
        cx, cy, rx, ry = cfg["rooms"][key]
        area_id, name = cfg["areas"][key]
        rect = [int(cx - rx) - 1, int(cy - ry) - 1, int(2 * rx) + 3, int(2 * ry) + 3]
        travel = spawn if key == "A" else (waypoints.get("merchant_spot") if False else None)
        if travel is None:
            travel = next([x, y] for r in range(0, 6) for y in range(int(cy) - r, int(cy) + r + 1)
                          for x in range(int(cx) - r, int(cx) + r + 1)
                          if ground[y, x] and not spires[y, x] and [x, y] not in [o["pos"] for o in objs])
        areas.append({"id": area_id, "name": name, "rect": rect, "travel": list(travel)})
    passages_id, passages_name = cfg["areas"]["passages"]
    areas.append({"id": passages_id, "name": passages_name, "rect": [0, 0, W, H], "travel": list(spawn)})
    return {
        "_comment": f"{cfg['name'].upper()}. Generated by tools/generate_worlds.py - edit the tool, not this file.",
        "id": world_id, "name": cfg["name"], "region": world_id,
        "background": f"{world_id}_tiles.png", "background_scale": 1, "canopy": f"{world_id}_canopy.png",
        "baked_features": True, "collision_file": f"{world_id}_collision.txt",
        "player_spawn": list(spawn), "safe_spot": list(spawn),
        "encounters": [{"rect": list(r), "paint": False} for key in ("B", "C") for r in grass[key]],
        "areas": areas, "waypoints": waypoints, "interactables": objs, "npcs": npcs,
    }


# --------------------------------------------------------------------------- art
THEMES = {
    "cave": {"void": (26, 22, 30), "void_noise": (14, 10, 12), "floor": [(76, 70, 88), (82, 76, 94)],
             "floor_hi": (110, 102, 124), "floor_lo": (60, 54, 70), "edge": (130, 120, 150), "path": (96, 90, 104),
             "path_edge": (70, 64, 80), "grass": (40, 70, 72), "blade": (90, 220, 190), "tip": (200, 255, 240),
             "sanctum": [(150, 160, 170), (120, 130, 140)], "spire": [(110, 230, 240), (120, 240, 160), (200, 160, 255)]},
    "kingdom": {"void": (32, 70, 46), "void_noise": (16, 26, 16), "floor": [(112, 170, 96), (118, 176, 100)],
                "floor_hi": (150, 200, 120), "floor_lo": (92, 146, 82), "edge": (70, 120, 64), "path": (214, 196, 150),
                "path_edge": (170, 150, 110), "grass": (70, 130, 64), "blade": (110, 190, 90), "tip": (240, 210, 120),
                "sanctum": [(190, 186, 176), (160, 156, 148)], "spire": [(220, 214, 200), (200, 190, 170), (230, 220, 190)]},
    "chronos": {"void": (20, 14, 36), "void_noise": (22, 10, 28), "floor": [(150, 120, 80), (158, 128, 86)],
                "floor_hi": (200, 170, 110), "floor_lo": (120, 94, 62), "edge": (230, 200, 120), "path": (110, 200, 220),
                "path_edge": (60, 130, 160), "grass": (110, 84, 60), "blade": (240, 200, 90), "tip": (255, 250, 200),
                "sanctum": [(90, 80, 130), (110, 100, 150)], "spire": [(240, 200, 100), (200, 170, 90), (255, 220, 140)]},
}


def render(world_id, cfg, ground, corridor, room_of, grass, spires):
    theme = THEMES[cfg["theme"]]
    rng = np.random.default_rng(cfg["seed"] + 100)
    img = np.zeros((H * T, W * T, 3), dtype=np.uint8)
    canopy = np.zeros((H * T, W * T, 4), dtype=np.uint8)
    yy, xx = np.mgrid[0:H * T, 0:W * T]
    noise = (np.sin(xx / 37.0) + np.sin(yy / 29.0 + xx / 53.0) + np.sin((xx + 2 * yy) / 23.0)) / 3
    for c in range(3):
        img[..., c] = np.clip(theme["void"][c] + noise * theme["void_noise"][c], 0, 255)
    if cfg["theme"] == "chronos":
        for _ in range(700):
            x, y = rng.integers(0, W * T), rng.integers(0, H * T)
            img[y, x] = (255, 230, 170) if rng.random() < 0.6 else (180, 200, 255)
    elif cfg["theme"] == "cave":
        for _ in range(500):   # rock speckle
            x, y = rng.integers(0, W * T - 3), rng.integers(0, H * T - 3)
            img[y:y + 2, x:x + 3] = (44, 38, 48)
    else:
        for _ in range(260):   # tree tops outside the kingdom's walls
            x, y = rng.integers(0, W * T - 12), rng.integers(0, H * T - 12)
            img[y:y + 10, x + 2:x + 10] = (40, 92, 52)
            img[y + 2:y + 4, x + 4:x + 7] = (70, 130, 70)
    walk = ground | corridor
    rects = [r for rs in grass.values() for r in rs]

    def in_grass(x, y):
        return any(x0 <= x < x0 + w and y0 <= y < y0 + h for x0, y0, w, h in rects)

    for y in range(H):
        for x in range(W):
            X, Y = x * T, y * T
            if not walk[y, x]:
                continue
            on_ground = ground[y, x]
            if on_ground and room_of[y, x] == "D":
                tile = theme["sanctum"][(x + y) % 2]
                img[Y:Y + T, X:X + T] = tile
                img[Y + T - 1, X:X + T] = tuple(max(0, c - 30) for c in tile)
                img[Y:Y + T, X + T - 1] = tuple(max(0, c - 30) for c in tile)
            elif on_ground:
                img[Y:Y + T, X:X + T] = theme["floor"][(x + y) % 2]
                img[Y + (x * 3 + y) % 9 + 3, X + 2:X + 7] = theme["floor_hi"]
                img[Y + 2:Y + 6, X + (x + y * 5) % 11 + 2] = theme["floor_lo"]
            if corridor[y, x] and not (on_ground and room_of[y, x] == "D"):
                img[Y:Y + T, X:X + T] = theme["path"]
                img[Y + T - 1, X:X + T] = theme["path_edge"]
                img[Y:Y + T, X + T - 1] = theme["path_edge"]
                if not on_ground and cfg["theme"] == "chronos":     # light bridges over the void
                    for i in range(2, T, 5):
                        img[Y + i, X:X + T] = (190, 240, 250)
            # rims where walkable meets the outside
            for nx, ny, sl in ((x, y - 1, (slice(Y, Y + 2), slice(X, X + T))),
                               (x, y + 1, (slice(Y + T - 2, Y + T), slice(X, X + T))),
                               (x - 1, y, (slice(Y, Y + T), slice(X, X + 2))),
                               (x + 1, y, (slice(Y, Y + T), slice(X + T - 2, X + T)))):
                if not (0 <= nx < W and 0 <= ny < H and walk[ny, nx]):
                    img[sl] = theme["edge"]
            if on_ground and in_grass(x, y):
                img[Y:Y + T, X:X + T] = theme["grass"]
                for i in range(4):
                    bx = X + 1 + i * 4
                    top = Y + 3 + (i % 2) * 3
                    img[top:Y + T - 1, bx:bx + 2] = theme["blade"]
                    img[top:top + 2, bx:bx + 2] = theme["tip"]
    for y in range(H):
        for x in range(W):
            if spires[y, x]:
                _spire(img, canopy, x, y, cfg["theme"], theme["spire"][(x + y) % 3])
    Image.fromarray(img).save(ROOT / f"assets/backgrounds/{world_id}_tiles.png", optimize=True)
    Image.fromarray(canopy, "RGBA").save(ROOT / f"assets/backgrounds/{world_id}_canopy.png", optimize=True)


def _put(img, canopy, px, py, base_y, value):
    if 0 <= py < img.shape[0] and 0 <= px < img.shape[1]:
        img[py, px] = value
        if py < base_y:   # anything above its own tile goes in the canopy so you can walk behind it
            canopy[py, px, :3] = value
            canopy[py, px, 3] = 255


def _spire(img, canopy, x, y, theme, color):
    X, Y = x * T, y * T
    dark = tuple(c // 2 for c in color)
    light = tuple(min(255, c + 45) for c in color)
    outline = (24, 20, 30)
    if theme == "kingdom":                       # stone obelisk
        for row in range(30):
            py = Y + T - 30 + row
            half = 3 if row > 4 else max(0, row - 1)
            for col in range(-half, half + 1):
                value = outline if col in (-half, half) or row == 29 else (light if col < 0 else color)
                _put(img, canopy, X + 8 + col, py, Y, value)
    elif theme == "chronos":                     # clock tower with a dial
        for row in range(30):
            py = Y + T - 30 + row
            for col in range(-4, 5):
                edge = col in (-4, 4) or row in (0, 29)
                _put(img, canopy, X + 8 + col, py, Y, outline if edge else (dark if col > 1 else color))
        cx, cy = X + 8, Y + T - 22
        for a in range(0, 360, 20):
            _put(img, canopy, int(cx + 3 * math.cos(math.radians(a))), int(cy + 3 * math.sin(math.radians(a))), Y, (255, 250, 220))
        for d in range(3):
            _put(img, canopy, cx, cy - d, Y, outline)
            _put(img, canopy, cx + d, cy, Y, outline)
    else:                                        # glowing crystal
        for row in range(28):
            half = max(1, (row * 6) // 28)
            py = Y + T - 28 + row
            for col in range(-half, half + 1):
                shade = light if col < 0 else (color if col == 0 else dark)
                _put(img, canopy, X + 8 + col, py, Y, outline if col in (-half, half) else shade)


def build(world_id):
    cfg = WORLDS[world_id]
    ground, corridor, room_of, grass = build_layout(cfg)
    spawn, objs, npcs, waypoints = objects_for(world_id, cfg, ground, corridor, grass)
    spires = spires_for(cfg, ground, corridor, room_of, grass, objs, waypoints, spawn)
    check_reachable(spawn, objs, waypoints, walkable(ground, corridor, spires, objs), grass)
    data = map_data(world_id, cfg, ground, corridor, room_of, grass, spires, spawn, objs, npcs, waypoints)
    (ROOT / f"data/maps/{world_id}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    render(world_id, cfg, ground, corridor, room_of, grass, spires)
    print(f"{world_id}: {int((ground | corridor).sum())} walkable tiles, {len(objs)} objects, {int(spires.sum())} spires")


def main():
    for world_id in (sys.argv[1:] or WORLDS):
        build(world_id)


if __name__ == "__main__":
    main()

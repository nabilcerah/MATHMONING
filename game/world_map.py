"""Data-driven tile map: layers from JSON, collision, named areas, waypoints and pathfinding."""
import json
from collections import deque
from pathlib import Path

from config import ROOT

TILE = 16
SOLID_TILES = frozenset("TwBDR")
ENCOUNTER_TILES = frozenset("G")
MAP_DIR = ROOT / "data" / "maps"


def load_map(map_id="number_forest"):
    with open(Path(MAP_DIR) / f"{map_id}.json", encoding="utf-8") as handle:
        return WorldMap(json.load(handle))


COLLISION_CODES = {"#": "T", "~": "w", ".": "g", ",": "g"}


class WorldMap:
    """Two kinds of map share this class:

    * tile maps: ``size`` + ``fills``/``props`` describe every tile (drawn in code);
    * painted maps: a ``background`` painting plus a generated ``collision_file``
      (see tools/build_world_map.py), corrected by hand-authored rects:
      ``blocked``, ``walkable``, ``trails`` (drawn dirt paths / plank bridges) and
      ``encounters`` (wild-creature grass).
    """

    def __init__(self, data):
        self.data = data
        self.map_id = data.get("id", "")
        self.name = data.get("name", "")
        self.background = data.get("background")
        self.background_scale = int(data.get("background_scale", 1))
        self.canopy = data.get("canopy")
        self.baked_features = bool(data.get("baked_features"))
        self.vertical_bridges = set()  # bridge cells whose planks run across a north-south span
        if data.get("collision_file"):
            rows = (Path(MAP_DIR) / data["collision_file"]).read_text(encoding="utf-8").split()
            self.width, self.height = len(rows[0]), len(rows)
            self.tiles = [[COLLISION_CODES.get(code, "T") for code in row] for row in rows]
            self._apply_rects(data.get("blocked", []), "T")
            self._apply_rects(data.get("walkable", []), "g")
            self._apply_rects([b["rect"] for b in data.get("buildings", [])], "T")
            for trail in data.get("trails", []):
                style = trail.get("style", "path")
                code = "b" if style == "bridge" else "p"
                self._apply_rects([trail["rect"]], code)
                x0, y0, w, h = trail["rect"]
                if code == "b" and h > w:
                    self.vertical_bridges |= {(x, y) for x in range(x0, x0 + w) for y in range(y0, y0 + h)}
            for zone in data.get("encounters", []):
                self._apply_rects([zone["rect"] if isinstance(zone, dict) else zone], "G")
            self.paint_encounters = {tuple(zone["rect"]) for zone in data.get("encounters", [])
                                     if isinstance(zone, dict) and zone.get("paint")}
        else:
            self.width, self.height = data["size"]
            self.paint_encounters = set()
            base = data.get("base", "g")
            self.tiles = [[base] * self.width for _ in range(self.height)]
        self._build_tiles(data)

    def _apply_rects(self, rects, code):
        for x0, y0, w, h in rects:
            for y in range(y0, y0 + h):
                for x in range(x0, x0 + w):
                    self._set(x, y, code)

    def _build_tiles(self, data):
        for fill in data.get("fills", []):
            x0, y0, w, h = fill["rect"]
            for y in range(y0, y0 + h):
                for x in range(x0, x0 + w):
                    self._set(x, y, fill["tile"])
        for prop in data.get("props", []):
            for x, y in prop.get("cells", []):
                self._set(x, y, prop["tile"])
        border = data.get("border")
        if border:
            for x in range(self.width):
                self._set(x, 0, border)
                self._set(x, self.height - 1, border)
            for y in range(self.height):
                self._set(0, y, border)
                self._set(self.width - 1, y, border)
        self.areas = [(a["id"], a["name"], tuple(a["rect"])) for a in data.get("areas", [])]
        self.waypoints = {name: tuple(cell) for name, cell in data.get("waypoints", {}).items()}
        self.spawn = tuple(data.get("player_spawn", (1, 1)))
        # Interactable objects occupy their tile (plus any extra "solid" cells).
        self.blocked = set()
        for entry in data.get("interactables", []):
            self.blocked.add(tuple(entry["pos"]))
            for cell in entry.get("solid", []):
                self.blocked.add(tuple(cell))

    def _set(self, x, y, code):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.tiles[y][x] = code

    # ----------------------------------------------------------------- queries
    def tile_at(self, x, y):
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return "T"
        return self.tiles[y][x]

    def is_walkable(self, cell):
        x, y = cell
        return self.tile_at(x, y) not in SOLID_TILES and (x, y) not in self.blocked

    def is_encounter(self, cell):
        return self.tile_at(*cell) in ENCOUNTER_TILES

    def area_at(self, cell):
        x, y = cell
        for area_id, name, (ax, ay, aw, ah) in self.areas:
            if ax <= x < ax + aw and ay <= y < ay + ah:
                return area_id, name
        return "", self.name

    def pixel_size(self):
        return self.width * TILE, self.height * TILE

    @staticmethod
    def cell_to_feet(cell):
        """World position of a character's feet when standing on ``cell``."""
        return cell[0] * TILE + TILE / 2, cell[1] * TILE + 13

    @staticmethod
    def to_cell(x, y):
        return int(x // TILE), int(y // TILE)

    def nearest_walkable(self, cell):
        if self.is_walkable(cell):
            return cell
        for radius in range(1, 8):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    candidate = (cell[0] + dx, cell[1] + dy)
                    if self.is_walkable(candidate):
                        return candidate
        return self.spawn

    def find_path(self, start, goal):
        """Breadth-first path of cells from start (exclusive) to goal (inclusive)."""
        if start == goal or not self.is_walkable(goal):
            return []
        previous = {start: None}
        queue = deque([start])
        while queue:
            cell = queue.popleft()
            if cell == goal:
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt not in previous and self.is_walkable(nxt):
                    previous[nxt] = cell
                    queue.append(nxt)
        if goal not in previous:
            return []
        path, cell = [], goal
        while cell != start:
            path.append(cell)
            cell = previous[cell]
        return path[::-1]

    def box_blocked(self, left, top, right, bottom):
        """True when any tile under the pixel box is solid."""
        for cy in range(int(top // TILE), int((bottom - 0.01) // TILE) + 1):
            for cx in range(int(left // TILE), int((right - 0.01) // TILE) + 1):
                if not self.is_walkable((cx, cy)):
                    return True
        return False

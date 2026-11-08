"""Interactive world map: the real game map in miniature, with fog, markers and fast travel.

* Drawn from the same art as the overworld, so the two always match.
* Areas you have not walked into yet stay under fog.
* Markers: you, villagers, unopened chests, the spring, the Shadow Gate and wild MATHMON.
* Arrow keys pick an area; the side panel lists which MATHMON live there and what is left to
  find. ENTER fast-travels to any area you have already visited.
"""
import math

import pygame

from config import PALETTE
from game.creatures import TOPIC_COLORS, WILD
from game.ui import heart, panel, text, wrapped

MAP_RECT = pygame.Rect(6, 24, 188, 188)
_minimaps = {}


def _minimap(world, overworld_module):
    key = world.background
    if key not in _minimaps:
        art = overworld_module.painted_background(world)
        _minimaps[key] = pygame.transform.smoothscale(art, MAP_RECT.size)
    return _minimaps[key]


class WorldMapScreen:
    def __init__(self, overworld):
        self.overworld = overworld
        self.world = overworld.world
        self.areas = [a for a in self.world.data.get("areas", []) if a.get("travel")]
        current = overworld.area_id
        self.selected = next((i for i, a in enumerate(self.areas) if a["id"] == current), 0)
        self.closed = False
        self.travel_to = None
        self.notice = ""
        self.scale = MAP_RECT.width / (self.world.width * 16)
        self._fog = self._build_fog()

    # ------------------------------------------------------------------ state
    def visited(self, area_id):
        return self.overworld.has_flag(f"visited:{area_id}")

    def _build_fog(self):
        """Fog of war over every chunk you have not walked near yet."""
        size = self.overworld.CHUNK
        cols = -(-self.world.width // size)
        rows = -(-self.world.height // size)
        fog = pygame.Surface((cols, rows), pygame.SRCALPHA)
        fog.fill((19, 25, 42, 246))
        for y in range(rows):
            for x in range(cols):
                if f"chunk:{x},{y}" in self.overworld.flags:
                    fog.set_at((x, y), (0, 0, 0, 0))
        # Scale per chunk, so fog edges line up with the map exactly.
        scaled = pygame.transform.scale(fog, (round(cols * size * 16 * self.scale), round(rows * size * 16 * self.scale)))
        return scaled

    def handle_key(self, key):
        if key in (pygame.K_n, pygame.K_ESCAPE, pygame.K_m):
            self.closed = True
        elif key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_d, pygame.K_s):
            self.selected = (self.selected + 1) % len(self.areas)
            self.notice = ""
        elif key in (pygame.K_LEFT, pygame.K_UP, pygame.K_a, pygame.K_w):
            self.selected = (self.selected - 1) % len(self.areas)
            self.notice = ""
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e):
            area = self.areas[self.selected]
            if not self.visited(area["id"]):
                self.notice = "Explore it on foot first!"
            elif area["id"] == self.overworld.area_id:
                self.notice = "You are already here."
            else:
                self.travel_to = (tuple(area["travel"]), area["name"])
                self.closed = True

    def to_map(self, world_x, world_y):
        return MAP_RECT.x + world_x * self.scale, MAP_RECT.y + world_y * self.scale

    def tile_to_map(self, cell):
        return self.to_map(cell[0] * 16 + 8, cell[1] * 16 + 8)

    # ------------------------------------------------------------------- info
    def area_info(self, area):
        area_id = area["id"]
        flags = self.overworld.flags
        species = [s for s in WILD if area_id in s.habitat]
        x0, y0, w, h = area["rect"]
        chests = [e for e in self.world.data.get("interactables", [])
                  if e.get("kind") == "chest" and self.world.area_at(tuple(e["pos"]))[0] == area_id]
        opened = sum(1 for e in chests if f"opened:{e['id']}" in flags)
        return species, chests, opened

    # ------------------------------------------------------------------- draw
    def draw(self, surface, frame=0):
        surface.fill(PALETTE["ink"])
        pygame.draw.rect(surface, PALETTE["night"], MAP_RECT.inflate(6, 6))
        pygame.draw.rect(surface, PALETTE["cream"], MAP_RECT.inflate(4, 4), 1)
        from game import overworld as overworld_module
        surface.blit(_minimap(self.world, overworld_module), MAP_RECT)
        surface.set_clip(MAP_RECT)
        surface.blit(self._fog, MAP_RECT.topleft)
        surface.set_clip(None)
        flags = self.overworld.flags

        def revealed(cell):
            return self.overworld.explored(cell)

        # Markers on explored ground only.
        for entry in self.world.data.get("interactables", []):
            cell = tuple(entry["pos"])
            if not revealed(cell):
                continue
            mx, my = self.tile_to_map(cell)
            kind = entry.get("kind")
            if kind == "chest" and f"opened:{entry['id']}" not in flags:
                pygame.draw.rect(surface, PALETTE["ink"], (mx - 2, my - 2, 5, 5))
                pygame.draw.rect(surface, PALETTE["gold"], (mx - 1, my - 1, 3, 3))
            elif kind == "spring":
                pygame.draw.circle(surface, PALETTE["sky"], (int(mx), int(my)), 2)
            elif kind == "arena":
                pygame.draw.rect(surface, PALETTE["ink"], (mx - 3, my - 3, 7, 7))
                pygame.draw.rect(surface, PALETTE["coral"], (mx - 2, my - 2, 5, 5))
            elif kind == "shrine" and not self.overworld.shrine_done(entry["id"]):
                pygame.draw.rect(surface, PALETTE["ink"], (mx - 2, my - 3, 5, 7))
                pygame.draw.rect(surface, (190, 150, 255), (mx - 1, my - 2, 3, 5))
            elif kind == "boss_gate":
                pulse = 2 + (frame // 15) % 2
                pygame.draw.circle(surface, (190, 120, 255), (int(mx), int(my)), pulse)
        for roamer in self.overworld.roamers:
            cell = self.world.to_cell(roamer.x, roamer.y - 2)
            if revealed(cell):
                mx, my = self.to_map(roamer.x, roamer.y)
                color = TOPIC_COLORS.get(roamer.spec.topic, PALETTE["muted"])
                pygame.draw.rect(surface, PALETTE["ink"], (mx - 2, my - 2, 4, 4))
                pygame.draw.rect(surface, color, (mx - 1, my - 1, 2, 2))
        for npc in self.overworld.npcs:
            mx, my = self.to_map(npc.x, npc.y)
            pygame.draw.rect(surface, PALETTE["white"], (mx - 1, my - 1, 2, 2))

        # Selected area outline.
        area = self.areas[self.selected]
        x0, y0, w, h = area["rect"]
        left, top = self.to_map(x0 * 16, y0 * 16)
        outline = pygame.Rect(int(left), int(top), max(4, int(w * 16 * self.scale)), max(4, int(h * 16 * self.scale)))
        if frame % 30 < 22:
            pygame.draw.rect(surface, PALETTE["gold"], outline.clip(MAP_RECT.inflate(2, 2)), 1)

        # You are here.
        px, py = self.to_map(self.overworld.avatar.x, self.overworld.avatar.y)
        radius = 3 + (1 if frame % 40 < 20 else 0)
        pygame.draw.circle(surface, PALETTE["ink"], (int(px), int(py)), radius + 1)
        pygame.draw.circle(surface, PALETTE["coral"], (int(px), int(py)), radius)
        pygame.draw.circle(surface, PALETTE["white"], (int(px), int(py)), 1)

        text(surface, "WORLD MAP", (8, 5), 14, PALETTE["gold"])
        text(surface, f"You are in: {self.overworld.area_name}", (314, 7), 9, PALETTE["cream"], align="right")
        self._draw_panel(surface, area, frame)
        footer = self.notice or "ARROWS: PICK AREA    ENTER: TRAVEL    N / ESC: BACK"
        text(surface, footer, (160, 228), 9, PALETTE["gold"] if self.notice else PALETTE["cream"], center=True)

    def _draw_panel(self, surface, area, frame):
        rect = pygame.Rect(200, 24, 114, 188)
        visited = self.visited(area["id"])
        panel(surface, rect, PALETTE["night"], PALETTE["gold"] if visited else PALETTE["muted"])
        x, y = rect.x + 6, rect.y + 6
        wrapped(surface, area["name"] if visited else "??? (unexplored)", (x, y, 102, 26), 11,
                PALETTE["gold"] if visited else PALETTE["muted"], 12, 2)
        y += 28
        if not visited:
            wrapped(surface, "Walk there to reveal it on the map and unlock fast travel.", (x, y, 102, 60), 9,
                    PALETTE["white"], 10, 6)
            return
        species, chests, opened = self.area_info(area)
        flags = self.overworld.flags
        text(surface, "WILD MATHMON", (x, y), 9, PALETTE["cream"])
        y += 12
        if not species:
            text(surface, "None live here.", (x, y), 9, PALETTE["muted"])
            y += 11
        for spec in species:
            seen = f"dex_seen:{spec.name}" in flags
            caught = f"dex_friend:{spec.name}" in flags
            pygame.draw.rect(surface, TOPIC_COLORS.get(spec.topic, PALETTE["muted"]), (x, y + 2, 4, 4))
            text(surface, spec.name if seen else "???", (x + 7, y), 9, PALETTE["white"] if seen else PALETTE["muted"])
            if caught:
                heart(surface, x + 92, y, PALETTE["mint"])
            y += 11
        y += 5
        if chests:
            text(surface, f"CHESTS  {opened}/{len(chests)} found", (x, y), 9, PALETTE["cream"])
            y += 13
        here = sum(1 for r in self.overworld.roamers if r.zone["area"] == area["id"])
        if here:
            text(surface, f"{here} roaming now", (x, y), 9, PALETTE["mint"])
            y += 13
        # Legend for the map markers.
        legend_y = rect.bottom - 50
        for i, (label, color) in enumerate((("You", PALETTE["coral"]), ("Wild (topic colour)", PALETTE["mint"]),
                                            ("Chest", PALETTE["gold"]), ("Puzzle shrine", (190, 150, 255)))):
            pygame.draw.rect(surface, color, (x, legend_y + i * 9 + 2, 4, 4))
            text(surface, label, (x + 7, legend_y + i * 9), 8, PALETTE["muted"])
        if area["id"] == self.overworld.area_id:
            text(surface, "You are here", (x, rect.bottom - 14), 9, PALETTE["coral"])
        else:
            text(surface, "ENTER: TRAVEL", (x, rect.bottom - 14), 9, PALETTE["gold"])

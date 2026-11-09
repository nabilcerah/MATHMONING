"""Interactive world map: the real game map in miniature, with fog, markers, spawn points and quests.

* Drawn from the same art as the overworld, so the two always match. Unexplored ground stays fogged.
* PINS you can pick directly on the map (arrow keys jump to the nearest pin that way; mouse/tap works):
    - SPAWN POINTS (flags): fast-travel to any you have already walked to; the rest show a lock.
    - QUEST PINS (!): where each active quest's objective is (and the next world between chapters).
* ENTER on an unlocked spawn point travels there. ENTER on a quest pin - or on a locked spawn point
  that a quest leads to - opens that quest in the Quest Log (``self.open_quest``).
* Small markers show chests, shrines, the arena, the boss gate, wild MATHMON and villagers.
"""
import math

import pygame

from config import PALETTE
from game import ui
from game.creatures import TOPIC_COLORS
from game.ui import heart, panel, text, wrapped
from monsters.monster_data import species as species_data
from world.encounter_manager import EncounterManager

MAP_RECT = pygame.Rect(6, 24, 188, 188)
PANEL = pygame.Rect(200, 24, 114, 188)
NEXT = "__next__"                  # the "next destination" pin (between chapters)
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
        self.closed = False
        self.travel_to = None
        self.open_quest = None
        self.notice = ""
        self.scale = MAP_RECT.width / (self.world.width * 16)
        self._fog = self._build_fog()
        self.pins = self._build_pins()
        here = next((i for i, p in enumerate(self.pins) if p["kind"] == "spawn" and p["area"] == overworld.area_id),
                    None)
        quest = next((i for i, p in enumerate(self.pins) if p["kind"] == "quest"), None)
        self.selected = quest if quest is not None else (here or 0)

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
        prefix = getattr(self.overworld, "chunk_prefix", "chunk:")
        for y in range(rows):
            for x in range(cols):
                if f"{prefix}{x},{y}" in self.overworld.flags:
                    fog.set_at((x, y), (0, 0, 0, 0))
        scaled = pygame.transform.scale(fog, (round(cols * size * 16 * self.scale), round(rows * size * 16 * self.scale)))
        return scaled

    def _build_pins(self):
        pins = []
        for area in self.world.data.get("areas", []):
            if area.get("travel"):
                x, y = self.world.cell_to_feet(tuple(area["travel"]))
                pins.append({"kind": "spawn", "area": area["id"], "name": area["name"], "area_rect": area["rect"],
                             "cell": tuple(area["travel"]), "x": x, "y": y, "unlocked": self.visited(area["id"])})
        tracker = getattr(self.overworld, "tracker", None)
        quests = self.overworld.quests
        if tracker and quests:
            upcoming = tracker.next_destination()
            if upcoming and upcoming[2] and upcoming[2][0].isdigit():
                portal = self._next_portal()
                if portal:
                    x, y = self.world.cell_to_feet(tuple(portal["pos"]))
                    pins.append({"kind": "quest", "quest": NEXT, "name": upcoming[0].title(), "step": upcoming[1],
                                 "x": x, "y": y})
            for quest_id in quests.active():
                step = quests.current_step(quest_id) or {}
                where = tracker.target(step)
                if isinstance(where, tuple):
                    pins.append({"kind": "quest", "quest": quest_id, "name": quests.definition(quest_id)["title"],
                                 "step": quests.step_text(quest_id), "x": where[0], "y": where[1]})
        return pins

    def _next_portal(self):
        from game.quest_tracker import _progress_portals
        for options in _progress_portals().values():
            for map_id, _, portal in options:
                if map_id == self.world.map_id and self.overworld.has_flag(portal["requires"]):
                    target = portal["destination"]
                    if not self.overworld.has_flag(f"region:{target}_complete"):
                        return portal
        return None

    def quest_for_area(self, pin):
        """A quest whose objective lies inside this (locked) spawn point's area, if any."""
        x0, y0, w, h = pin["area_rect"]
        for other in self.pins:
            if other["kind"] == "quest" and other["quest"] != NEXT:
                cx, cy = other["x"] // 16, other["y"] // 16
                if x0 <= cx < x0 + w and y0 <= cy < y0 + h:
                    return other["quest"]
        return None

    # ------------------------------------------------------------------ input
    def move(self, dx, dy):
        """Jump to the nearest pin in the pressed direction."""
        if not self.pins:
            return
        here = self.pins[self.selected]
        best, best_score = None, None
        for index, pin in enumerate(self.pins):
            if index == self.selected:
                continue
            vx, vy = pin["x"] - here["x"], pin["y"] - here["y"]
            along = vx * dx + vy * dy
            if along <= 0:
                continue
            across = abs(vx * dy - vy * dx)
            score = along + 2 * across
            if best_score is None or score < best_score:
                best, best_score = index, score
        if best is not None:
            self.selected = best
            self.notice = ""

    def activate(self):
        if not self.pins:
            return
        pin = self.pins[self.selected]
        if pin["kind"] == "quest":
            if pin["quest"] == NEXT:
                self.notice = pin["step"]
                return
            self.open_quest = pin["quest"]
            self.closed = True
        elif not pin["unlocked"]:
            quest = self.quest_for_area(pin)
            if quest:
                self.open_quest = quest              # a locked place your quest leads to: show it in the log
                self.closed = True
            else:
                self.notice = "Locked: walk there on foot first to unlock it."
        elif pin["area"] == self.overworld.area_id:
            self.notice = "You are already here."
        else:
            self.travel_to = (pin["cell"], pin["name"])
            self.closed = True

    def handle_key(self, key):
        if key in (pygame.K_n, pygame.K_ESCAPE, pygame.K_m):
            self.closed = True
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.move(1, 0)
        elif key in (pygame.K_LEFT, pygame.K_a):
            self.move(-1, 0)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.move(0, 1)
        elif key in (pygame.K_UP, pygame.K_w):
            self.move(0, -1)
        elif key == pygame.K_TAB and self.pins:
            self.selected = (self.selected + 1) % len(self.pins)
            self.notice = ""
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e):
            self.activate()

    def handle_click(self, window_pos):
        """Click / tap a pin: the first click selects it, a second click opens / travels."""
        x, y = ui.to_virtual(window_pos)
        best, best_distance = None, 9
        for index, pin in enumerate(self.pins):
            mx, my = self.to_map(pin["x"], pin["y"])
            distance = math.hypot(mx - x, my - y)
            if distance < best_distance:
                best, best_distance = index, distance
        if best is None:
            return
        if best == self.selected:
            self.activate()
        else:
            self.selected = best
            self.notice = ""

    def to_map(self, world_x, world_y):
        return MAP_RECT.x + world_x * self.scale, MAP_RECT.y + world_y * self.scale

    def tile_to_map(self, cell):
        return self.to_map(cell[0] * 16 + 8, cell[1] * 16 + 8)

    # ------------------------------------------------------------------- info
    def area_info(self, area_id):
        flags = self.overworld.flags
        table = EncounterManager.table(area_id) if not EncounterManager.is_safe(area_id) else {"table": []}
        species = [species_data(sid) for sid, weight in table["table"] if weight > 5]
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
        self._draw_markers(surface, frame)
        for index, pin in enumerate(self.pins):
            self._draw_pin(surface, pin, index == self.selected, frame)
        # You are here.
        px, py = self.to_map(self.overworld.avatar.x, self.overworld.avatar.y)
        radius = 3 + (1 if frame % 40 < 20 else 0)
        pygame.draw.circle(surface, PALETTE["ink"], (int(px), int(py)), radius + 1)
        pygame.draw.circle(surface, PALETTE["coral"], (int(px), int(py)), radius)
        pygame.draw.circle(surface, PALETTE["white"], (int(px), int(py)), 1)
        surface.set_clip(None)
        if self.pins:
            self._draw_label(surface, self.pins[self.selected])
        text(surface, "WORLD MAP", (8, 5), 14, PALETTE["gold"])
        text(surface, f"You are in: {self.overworld.area_name}", (314, 7), 9, PALETTE["cream"], align="right")
        self._draw_panel(surface, frame)
        footer = self.notice or "ARROWS / CLICK: PICK A PIN    ENTER: GO    N / ESC: BACK"
        text(surface, footer[:64], (160, 228), 9, PALETTE["gold"] if self.notice else PALETTE["cream"], center=True)

    def _draw_markers(self, surface, frame):
        flags = self.overworld.flags
        revealed = self.overworld.explored
        for entry in self.world.data.get("interactables", []):
            cell = tuple(entry["pos"])
            if not revealed(cell):
                continue
            mx, my = self.tile_to_map(cell)
            kind = entry.get("kind")
            if kind == "chest" and f"opened:{entry['id']}" not in flags:
                pygame.draw.rect(surface, PALETTE["ink"], (mx - 2, my - 2, 4, 4))
                pygame.draw.rect(surface, PALETTE["gold"], (mx - 1, my - 1, 2, 2))
            elif kind == "arena":
                pygame.draw.rect(surface, PALETTE["coral"], (mx - 2, my - 2, 4, 4))
            elif kind == "shrine" and not self.overworld.shrine_done(entry["id"]):
                pygame.draw.rect(surface, (190, 150, 255), (mx - 1, my - 2, 3, 4))
            elif kind == "boss_gate":
                pulse = 2 + (frame // 15) % 2
                pygame.draw.circle(surface, (190, 120, 255), (int(mx), int(my)), pulse, 1)
        for roamer in self.overworld.roamers:
            if revealed(self.world.to_cell(roamer.x, roamer.y - 2)):
                mx, my = self.to_map(roamer.x, roamer.y)
                pygame.draw.rect(surface, TOPIC_COLORS.get(roamer.spec.topic, PALETTE["muted"]), (mx - 1, my - 1, 2, 2))
        for npc in self.overworld.npcs:
            mx, my = self.to_map(npc.x, npc.y)
            pygame.draw.rect(surface, PALETTE["white"], (mx - 1, my - 1, 2, 2))

    def _draw_pin(self, surface, pin, chosen, frame):
        mx, my = (int(v) for v in self.to_map(pin["x"], pin["y"]))
        if chosen:
            ring = 7 + (frame // 10) % 3
            pygame.draw.circle(surface, PALETTE["white"], (mx, my - 4), ring, 1)
        if pin["kind"] == "quest":
            bob = 1 if frame % 30 < 15 else 0
            top = my - 11 - bob
            pygame.draw.polygon(surface, PALETTE["ink"], [(mx, top - 1), (mx + 5, top + 5), (mx, top + 11), (mx - 5, top + 5)])
            pygame.draw.polygon(surface, PALETTE["gold"], [(mx, top), (mx + 4, top + 5), (mx, top + 10), (mx - 4, top + 5)])
            pygame.draw.rect(surface, PALETTE["ink"], (mx, top + 2, 1, 4))
            pygame.draw.rect(surface, PALETTE["ink"], (mx, top + 7, 1, 1))
            return
        color = PALETTE["mint"] if pin["unlocked"] else PALETTE["muted"]
        pygame.draw.line(surface, PALETTE["ink"], (mx, my), (mx, my - 9), 2)
        pygame.draw.polygon(surface, PALETTE["ink"], [(mx, my - 10), (mx + 7, my - 7), (mx, my - 4)])
        pygame.draw.polygon(surface, color, [(mx + 1, my - 9), (mx + 6, my - 7), (mx + 1, my - 5)])
        if not pin["unlocked"]:                   # a small padlock
            pygame.draw.rect(surface, PALETTE["ink"], (mx - 4, my - 4, 6, 5))
            pygame.draw.rect(surface, PALETTE["cream"], (mx - 3, my - 3, 4, 3))
            pygame.draw.rect(surface, PALETTE["cream"], (mx - 3, my - 6, 4, 3), 1)

    def _draw_label(self, surface, pin):
        mx, my = self.to_map(pin["x"], pin["y"])
        label = pin["name"] if (pin["kind"] == "quest" or pin["unlocked"]) else f"{pin['name']} (locked)"
        width = ui.measure(label, 8)[0] + 14            # a little extra so the label never pokes past the frame
        left = max(MAP_RECT.x + 1, min(MAP_RECT.right - width - 1, int(mx) - width // 2))
        top = max(MAP_RECT.y, int(my) - 28)
        panel(surface, (left, top, width, 12), PALETTE["ink"], PALETTE["gold"] if pin["kind"] == "quest" else PALETTE["cream"])
        text(surface, label, (left + 4, top + 2), 8, PALETTE["gold"] if pin["kind"] == "quest" else PALETTE["white"])

    def _draw_panel(self, surface, frame):
        rect = PANEL
        if not self.pins:
            panel(surface, rect, PALETTE["night"], PALETTE["muted"])
            return
        pin = self.pins[self.selected]
        x, y = rect.x + 6, rect.y + 6
        if pin["kind"] == "quest":
            panel(surface, rect, PALETTE["night"], PALETTE["gold"])
            text(surface, "QUEST", (x, y), 8, PALETTE["gold"])
            y += 11
            y += 12 * wrapped(surface, pin["name"], (x, y, 102, 26), 10, PALETTE["white"], 12, 2) + 4
            y += 10 * wrapped(surface, pin["step"], (x, y, 102, 70), 9, PALETTE["cream"], 10, 7) + 6
            avatar = self.overworld.avatar
            metres = round(math.hypot(pin["x"] - avatar.x, pin["y"] - avatar.y) / 16)
            text(surface, f"{metres} m away", (x, y), 9, PALETTE["mint"])
            hint = "ENTER: SHOW IN QUESTS" if pin["quest"] != NEXT else "Follow the gold pin!"
            text(surface, hint, (x, rect.bottom - 14), 8, PALETTE["gold"])
            return
        unlocked = pin["unlocked"]
        panel(surface, rect, PALETTE["night"], PALETTE["mint"] if unlocked else PALETTE["muted"])
        text(surface, "SPAWN POINT", (x, y), 8, PALETTE["mint"] if unlocked else PALETTE["muted"])
        y += 11
        y += 12 * wrapped(surface, pin["name"], (x, y, 102, 26), 11, PALETTE["white"] if unlocked else PALETTE["muted"],
                          12, 2) + 4
        if not unlocked:
            quest = self.quest_for_area(pin)
            wrapped(surface, "Locked. Walk there on foot to unlock fast travel." +
                    (" A quest leads here - ENTER shows it." if quest else ""), (x, y, 102, 80), 9,
                    PALETTE["white"], 10, 8)
            return
        species, chests, opened = self.area_info(pin["area"])
        flags = self.overworld.flags
        text(surface, "WILD MATHMON", (x, y), 8, PALETTE["cream"])
        y += 11
        if not species:
            text(surface, "None live here.", (x, y), 8, PALETTE["muted"])
            y += 10
        for spec in species[:5]:
            seen = f"dex_seen:{spec.name}" in flags
            pygame.draw.rect(surface, TOPIC_COLORS.get(spec.topic, PALETTE["muted"]), (x, y + 2, 4, 4))
            text(surface, spec.name if seen else "???", (x + 7, y), 8, PALETTE["white"] if seen else PALETTE["muted"])
            if f"dex_friend:{spec.name}" in flags:
                heart(surface, x + 92, y, PALETTE["mint"])
            y += 10
        if chests:
            text(surface, f"CHESTS {opened}/{len(chests)}", (x, y + 4), 8, PALETTE["cream"])
        here = pin["area"] == self.overworld.area_id
        text(surface, "You are here" if here else "ENTER: TRAVEL", (x, rect.bottom - 14), 9,
             PALETTE["coral"] if here else PALETTE["gold"])

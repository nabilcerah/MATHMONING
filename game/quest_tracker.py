"""The quest tracker: active quests in the top-right corner of the map, with how far away (and in
which direction) the next objective is. A tab button (or J) shows / hides it; the choice is saved.

Where is the objective? From the quest step:
    talk              -> that person (live position)       visit       -> the nearest cell of that area
    challenge         -> that object                       flags_all   -> the nearest unfinished one
    flag (a boss)     -> the boss gate                     open_chests -> the nearest unopened chest
    win_battles / capture_species -> the nearest wild MathMon or patch of tall grass
If it is on another map, the tracker names that map instead of a distance.
"""
import math
from functools import lru_cache

import pygame

from config import PALETTE, VIRTUAL_WIDTH
from game.ui import panel, text, wrap_lines

HIDDEN_FLAG = "ui:quest_tracker_hidden"
TILE = 16
WIDTH = 122
TAB = pygame.Rect(VIRTUAL_WIDTH - 62, 25, 58, 11)     # the show / hide button


@lru_cache(maxsize=None)
def _maps_index():
    """For targets on other maps: which map has which person / object / area."""
    from game.game_manager import GameManager
    from game.world_map import load_map
    index = {}
    for map_id in GameManager.MAPS:
        try:
            world = load_map(map_id)
        except Exception:
            continue
        for npc in world.data.get("npcs", []):
            index.setdefault(("npc", npc["id"]), world.name)
        for entry in world.data.get("interactables", []):
            index.setdefault(("object", entry["id"]), world.name)
            if entry.get("challenge"):
                index.setdefault(("object", entry["challenge"]), world.name)
        for area_id, _, _ in world.areas:
            index.setdefault(("area", area_id), world.name)
    return index


# The story's worlds in order. Finishing one opens a portal to the next (data/maps: portal "requires").
WORLD_ORDER = ("number_forest", "algebra_cavern", "geometry_kingdom", "chronos_dimension")


@lru_cache(maxsize=None)
def _progress_portals():
    """{destination world: [(map id, map name, portal entry)]} for the portals that move the story on."""
    from game.world_map import load_map
    found = {}
    for map_id in WORLD_ORDER:
        world = load_map(map_id)
        for entry in world.data.get("interactables", []):
            if entry.get("kind") == "portal" and entry.get("requires") and entry.get("destination") in WORLD_ORDER:
                found.setdefault(entry["destination"], []).append((map_id, world.name, entry))
    return found


def direction(dx, dy):
    """Compass word for a vector (screen y grows downwards)."""
    angle = math.degrees(math.atan2(-dy, dx)) % 360
    return ("E", "NE", "N", "NW", "W", "SW", "S", "SE")[int((angle + 22.5) // 45) % 8]


class QuestTracker:
    def __init__(self, world):
        self.world = world

    @property
    def visible(self):
        return HIDDEN_FLAG not in self.world.flags

    def toggle(self):
        if self.visible:
            self.world.set_flag(HIDDEN_FLAG)
        else:
            self.world.clear_flag(HIDDEN_FLAG)

    # ------------------------------------------------------------------ where to go
    def target(self, step):
        """(x, y) world pixels of the step's objective on this map, a map name if elsewhere, or None."""
        w = self.world
        kind = step.get("type")
        if kind == "talk":
            npc = next((n for n in w.npcs if n.id == step["npc"]), None)
            return (npc.x, npc.y) if npc else _maps_index().get(("npc", step["npc"]))
        if kind == "visit":
            area = next((a for a in w.world.areas if a[0] == step["area"]), None)
            if area:
                ax, ay, aw, ah = area[2]
                cx, cy = w.avatar.cell()
                nearest = (min(max(cx, ax), ax + aw - 1), min(max(cy, ay), ay + ah - 1))
                return w.world.cell_to_feet(nearest)
            return _maps_index().get(("area", step["area"]))
        if kind in ("challenge", "flags_all", "flag"):
            wanted = [step["id"]] if kind == "challenge" else (
                [f.split(":", 1)[1] for f in step.get("flags", []) if not w.has_flag(f)] if kind == "flags_all"
                else [])
            objects = [e for e in w.objects.values()
                       if (e.get("challenge") in wanted or e["id"] in wanted)
                       or (kind == "flag" and e.get("flag") == step.get("flag"))]
            if objects:
                return self._nearest([w.world.cell_to_feet(tuple(e["pos"])) for e in objects])
            for name in wanted:
                found = _maps_index().get(("object", name))
                if found:
                    return found
            return None
        if kind == "open_chests":
            chests = [w.world.cell_to_feet(tuple(e["pos"])) for e in w.objects.values()
                      if e.get("kind") == "chest" and not w.has_flag(f"opened:{e['id']}")]
            return self._nearest(chests) if chests else None
        if kind in ("win_battles", "capture_species", "capture"):
            wanted = step.get("species")
            spots = [(r.x, r.y) for r in w.roamers if not wanted or r.species_id == wanted]
            if not spots:
                spots = [w.world.cell_to_feet(c) for zone in w.zones for c in zone["cells"][::7]]
            return self._nearest(spots) if spots else None
        return None

    def _nearest(self, points):
        ax, ay = self.world.avatar.x, self.world.avatar.y
        return min(points, key=lambda p: (p[0] - ax) ** 2 + (p[1] - ay) ** 2)

    def next_destination(self):
        """Between chapters no main quest is active (the next one starts when its guide meets you in the
        next world), so point at the portal to the next unfinished world: (title, text, distance) or None."""
        w = self.world
        quests = w.quests
        if quests and any(quests.definition(q).get("category") == "main" for q in quests.active()):
            return None
        for index, region in enumerate(WORLD_ORDER[1:], start=1):
            done = w.has_flag(f"region:{region}_complete") or (region == "chronos_dimension" and w.has_flag("game:complete"))
            if done:
                continue
            if not w.has_flag(f"region:{WORLD_ORDER[index - 1]}_complete") or w.world.map_id == region:
                return None                              # the current world's story is still going
            options = [(m, name, e) for m, name, e in _progress_portals().get(region, []) if w.has_flag(e["requires"])]
            if not options:
                return None
            from game.world_map import load_map
            target = load_map(region).name
            here = next((o for o in options if o[0] == w.world.map_id), None)
            map_id, map_name, portal = here or options[0]
            portal_name = portal.get("title", "portal").title()
            if portal_name.lower() in target.lower() or target.lower() in portal_name.lower():
                text_ = f"Travel to the {target}."          # the entrance is named after the place itself
            else:
                text_ = f"Travel to the {target} through the {portal_name}."
            if here:
                x, y = w.world.cell_to_feet(tuple(portal["pos"]))
                dx, dy = x - w.avatar.x, y - w.avatar.y
                metres = round(math.hypot(dx, dy) / TILE)
                distance = "You're here!" if metres <= 1 else f"{metres} m {direction(dx, dy)}"
            else:
                distance = f"In {map_name}"
            return ("NEXT DESTINATION", text_, distance)
        return None

    def entries(self, limit=2):
        """[(title, step text, distance text)]: where to go next between chapters, then the active quests
        (this map's story first)."""
        quests = self.world.quests
        if not quests:
            return []
        upcoming = self.next_destination()
        if upcoming:
            limit -= 1
        active = quests.active()
        active.sort(key=lambda q: quests.definition(q).get("category") != "main")
        out = [upcoming] if upcoming else []
        for quest_id in active[:limit]:
            step = quests.current_step(quest_id) or {}
            where = self.target(step)
            if isinstance(where, tuple):
                dx, dy = where[0] - self.world.avatar.x, where[1] - self.world.avatar.y
                metres = round(math.hypot(dx, dy) / TILE)
                distance = "You're here!" if metres <= 1 else f"{metres} m {direction(dx, dy)}"
            elif isinstance(where, str):
                distance = f"In {where}"
            else:
                distance = ""
            out.append((quests.definition(quest_id)["title"], quests.step_text(quest_id), distance))
        return out

    # ------------------------------------------------------------------ drawing
    def draw(self, surface, frame):
        visible = self.visible
        panel(surface, TAB, PALETTE["night"], PALETTE["gold"])
        text(surface, ("QUESTS " + ("v" if visible else "<")) + "  J", TAB.center, 7, PALETTE["gold"], center=True)
        if not visible:
            return
        entries = self.entries()
        if not entries:
            return
        x = VIRTUAL_WIDTH - WIDTH - 4
        lines = []
        for title, step, distance in entries:
            lines.append(("title", title))
            lines += [("step", line) for line in wrap_lines(step, WIDTH - 10, 7)[:3]]
            if distance:
                lines.append(("distance", distance))
        height = 6 + sum(9 if kind == "title" else 8 for kind, _ in lines)
        shade = pygame.Surface((WIDTH, height), pygame.SRCALPHA)
        shade.fill((19, 26, 42, 205))
        surface.blit(shade, (x, TAB.bottom + 2))
        pygame.draw.rect(surface, PALETTE["gold"], (x, TAB.bottom + 2, WIDTH, height), 1)
        y = TAB.bottom + 5
        for kind, value in lines:
            if kind == "title":
                text(surface, value[:24], (x + 5, y), 8, PALETTE["gold"])
                y += 9
            elif kind == "step":
                text(surface, value, (x + 5, y), 7, PALETTE["white"])
                y += 8
            else:
                pulse = PALETTE["mint"] if frame % 60 < 45 else PALETTE["cream"]
                text(surface, "> " + value, (x + 5, y), 7, pulse)
                y += 8

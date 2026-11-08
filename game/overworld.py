"""NUMBER FOREST overworld: free-roaming avatar, routine NPCs and data-driven interactables.

The map, NPCs and objects come from ``data/maps/number_forest.json``. Movement is smooth
(pixel based, with collision), the avatar faces what it will interact with, and an
``[E]`` prompt says what pressing the key will do before the player commits.
"""
import math
import random

import pygame

from config import PALETTE, ROOT, VIRTUAL_WIDTH
from game.actors import NPC, Avatar
from game.creatures import draw_creature
from game.sprites import frame_for
from monsters.monster_data import challenges, species
from world.encounter_manager import EncounterManager
from game.ui import heart, menu, meter, panel, text, wrap_lines, wrapped
from game.world_map import TILE, load_map

VIEW_TOP, VIEW_HEIGHT = 24, 192
INTERACT_RANGE = 13
MAP_VERSION_FLAG = "map:painted-v1"
SHRINE_COLORS = {"sequence": (110, 177, 206), "balance": (137, 199, 124), "target": (242, 187, 82),
                 "magic": (235, 112, 92), "starchart": (190, 150, 255)}
  # saves from the old tile map restart at the new spawn
_backgrounds = {}


def painted_background(world, name=None, alpha=False):
    """The world art at game size (cached; it is large). ``name`` selects another layer, e.g. the canopy."""
    name = name or world.background
    key = (name, world.background_scale)
    if key not in _backgrounds:
        image = pygame.image.load(str(ROOT / "assets" / "backgrounds" / name))
        if pygame.display.get_surface():
            image = image.convert_alpha() if alpha else image.convert()
        scale = world.background_scale
        if scale != 1:
            image = pygame.transform.scale(image, (image.get_width() * scale, image.get_height() * scale))
        _backgrounds[key] = image
    return _backgrounds[key]


class Dialogue:
    """A paged message box. Choices (label, action) appear on the final page."""
    REVEAL_SPEED = 2  # characters per frame

    def __init__(self, title, pages, subtitle="", choices=None, speaker=None, kind="message"):
        self.title = title
        self.subtitle = subtitle
        self.pages = [p for p in (pages if isinstance(pages, (list, tuple)) else [pages]) if p] or [""]
        self.page = 0
        self.choices = list(choices or [])
        self.selected = 0
        self.speaker = speaker
        self.kind = kind
        self.age = 0

    @property
    def on_last_page(self):
        return self.page >= len(self.pages) - 1

    @property
    def revealed(self):
        return self.age * self.REVEAL_SPEED >= len(self.pages[self.page])


class Roamer:
    """A wild MATHMON wandering its patch of tall grass. Touching it starts a battle."""
    SPEED = 0.45
    NOTICE_RANGE = 52
    TOUCH_RANGE = 11

    def __init__(self, species_id, zone, world, rng, avoid=None, level=1):
        self.species_id = species_id
        self.spec, self.zone, self.world, self.rng = species(species_id), zone, world, rng
        self.level = level
        cells = zone["cells"]
        if avoid is not None:
            far = [c for c in cells if abs(c[0] - avoid[0]) + abs(c[1] - avoid[1]) >= 6]
            cells = far or cells
        self.x, self.y = world.cell_to_feet(rng.choice(cells))
        self.target = None
        self.wait = rng.randint(20, 120)
        self.facing = rng.choice((-1, 1))
        self.alert = 0
        self.moving = False
        self.age = rng.randint(0, 200)

    def update(self, avatar):
        self.age += 1
        distance = math.hypot(avatar.x - self.x, avatar.y - self.y)
        if distance < self.NOTICE_RANGE:
            if not self.alert:
                self.alert = 45
            self.facing = 1 if avatar.x > self.x else -1
        elif self.alert:
            self.alert -= 1
        if self.target:
            tx, ty = self.target
            dx, dy = tx - self.x, ty - self.y
            step = math.hypot(dx, dy)
            if step <= self.SPEED:
                self.x, self.y, self.target, self.moving = tx, ty, None, False
                self.wait = self.rng.randint(60, 200)
            else:
                self.x += dx / step * self.SPEED
                self.y += dy / step * self.SPEED
                self.moving = True
                if abs(dx) > 0.5:
                    self.facing = 1 if dx > 0 else -1
        else:
            self.wait -= 1
            if self.wait <= 0:
                cx, cy = self.world.to_cell(self.x, self.y - 2)
                nearby = [c for c in self.zone["cells"] if 0 < abs(c[0] - cx) + abs(c[1] - cy) <= 3]
                if nearby:
                    self.target = self.world.cell_to_feet(self.rng.choice(nearby))
                self.wait = self.rng.randint(40, 120)
        return distance <= self.TOUCH_RANGE


class Overworld:
    CHUNK = 8            # fog-of-war granularity in tiles
    REVEAL_RADIUS = 1    # chunks revealed around the player in each direction
    MAX_ROAMERS_PER_ZONE = 2
    RESPAWN_FRAMES = (60 * 25, 60 * 50)

    def __init__(self, player, rng=None, repository=None, map_id="number_forest", party=None, quests=None,
                 on_event=None):
        self.player = player
        self.rng = rng or random.Random()
        self.repository = repository
        self.party = party
        self.quests = quests            # world.quest_manager.QuestManager (read: statuses)
        self.on_event = on_event        # callback(kind, **data) for quest/discovery hooks
        self.encounters = EncounterManager(self.rng)
        self.world = load_map(map_id)
        # The forest keeps its original flag names; other maps prefix theirs (fog chunks are per map).
        self.chunk_prefix = "chunk:" if map_id == "number_forest" else f"chunk@{map_id}:"
        self.flags = set(repository.world_flags(player.player_id)) if repository and player.player_id else set()
        self.world.apply_flags(self.flags)
        self.records = repository.capture_records(player.player_id) if repository and player.player_id and \
            hasattr(repository, "capture_records") else {}
        saved = (player.x, player.y)
        if self.world.map_id == "number_forest" and self.world.background and MAP_VERSION_FLAG not in self.flags:
            saved = self.world.spawn  # an old tile-map position means nothing on the painted world
        start = self.world.nearest_walkable(saved)
        if self.world.barriers and not self.world.reachable_from_spawn(start):
            start = self.world.nearest_walkable(self.world.safe_spot)  # stuck behind a closed barrier
        self.avatar = Avatar(*self.world.cell_to_feet(start))
        self.avatar.sheet = self.avatar_sheet()
        self.player.x, self.player.y = start
        self.npcs = [NPC(spec, self.world, self.rng) for spec in self.world.data.get("npcs", [])]
        self.objects = {entry["id"]: entry for entry in self.world.data.get("interactables", [])}
        self.target = None
        self.dialogue = None
        self.message = ""
        self.message_frames = 0
        self.area_id, self.area_name = "", self.world.name
        self.banner_frames = 0
        self.grass_distance = 0.0
        self.steps = 0
        self.encounter_grace = 90
        self.boss_ready = False
        self.dirty = False
        self.cam_x, self.cam_y = self._camera_goal()
        self.age = 0
        self.encounter_spec = None
        self.encounter_level = None
        self.duel_spec = None
        self.duel_name = ""
        import datetime
        self.today = datetime.date.today().isoformat()  # shrines offer a fresh puzzle each day
        self.zones = self._encounter_zones()
        self.roamers = []
        self.respawns = []
        for zone in self.zones:
            if self._zone_open(zone):
                for _ in range(zone["quota"]):
                    self._spawn_roamer(zone)
        self._update_area()
        self._reveal_around()
        if self.world.background:
            self.set_flag(MAP_VERSION_FLAG)
            self.dirty = True

    # ------------------------------------------------------------- flags/state
    def has_flag(self, flag):
        return flag in self.flags

    def set_flag(self, flag):
        if flag in self.flags:
            return
        self.flags.add(flag)
        if self.repository and self.player.player_id:
            self.repository.set_world_flag(self.player.player_id, flag)
        self.world.apply_flags(self.flags)

    def refresh_flags(self):
        if self.repository and self.player.player_id:
            self.flags = set(self.repository.world_flags(self.player.player_id))
            if hasattr(self.repository, "capture_records"):
                self.records = self.repository.capture_records(self.player.player_id)
        self.world.apply_flags(self.flags)

    def _emit(self, kind, **data):
        if self.on_event:
            self.on_event(kind, **data)

    @property
    def team(self):
        """The GDD party (kept under the old name for older callers)."""
        return self.party

    AVATARS = ("ALEX", "LUNA")

    def avatar_sheet(self):
        chosen = [f.split(":", 1)[1] for f in self.flags if f.startswith("avatar:")]
        name = chosen[0] if chosen and chosen[0] in self.AVATARS else "ALEX"
        return f"characters/{name}"

    def companion_spec(self):
        """Your lead monster follows you around."""
        lead = self.party.lead if self.party else None
        return lead.spec if lead else species("FRACTELLA")

    def set_message(self, message, frames=210):
        self.message = str(message)
        self.message_frames = frames

    def resume(self):
        """Called after a battle: short grace period before the next wild encounter."""
        self.encounter_grace = 150
        self.grass_distance = 0.0
        self.encounters.after_battle()   # GDD 10.3: a 7-step cooldown after every battle

    # ----------------------------------------------------------- wild roamers
    def _encounter_zones(self):
        zones = []
        for entry in self.world.data.get("encounters", []):
            x0, y0, w, h = entry["rect"] if isinstance(entry, dict) else entry
            cells = [(x, y) for y in range(y0, y0 + h) for x in range(x0, x0 + w) if self.world.is_encounter((x, y))]
            if not cells:
                continue
            area_id, _ = self.world.area_at((x0 + w // 2, y0 + h // 2))
            extra = entry if isinstance(entry, dict) else {}
            quota = extra.get("quota") or max(1, min(self.MAX_ROAMERS_PER_ZONE, round(len(cells) / 50)))
            zones.append({"rect": (x0, y0, w, h), "cells": cells, "area": area_id, "quota": quota,
                          "species": extra.get("species"), "requires": extra.get("requires")})
        return zones

    def _zone_open(self, zone):
        return not zone.get("requires") or self.has_flag(zone["requires"])

    def _wake_special_zones(self):
        """A secret zone opens the moment its flag is earned (e.g. finishing the Star Chart)."""
        for zone in self.zones:
            if zone.get("requires") and self._zone_open(zone):
                live = sum(1 for r in self.roamers if r.zone is zone) + sum(1 for _, z in self.respawns if z is zone)
                for _ in range(zone["quota"] - live):
                    self._spawn_roamer(zone)

    def _spawn_roamer(self, zone, avoid=None):
        """Visible roamers come from the same region encounter table; rare species never roam."""
        species_id, level = self.encounters.pick(zone["area"], exclude_rare=True)
        if zone.get("species"):
            species_id = zone["species"]
        self.roamers.append(Roamer(species_id, zone, self.world, self.rng, avoid, level))

    def _update_roamers(self):
        if self.age % 30 == 0:
            self._wake_special_zones()
        touched = None
        for roamer in self.roamers:
            if roamer.update(self.avatar) and not self.encounter_grace and not self.dialogue and touched is None:
                touched = roamer
        for item in self.respawns:
            item[0] -= 1
        for _, zone in [r for r in self.respawns if r[0] <= 0]:
            self._spawn_roamer(zone, avoid=self.avatar.cell())
        self.respawns = [r for r in self.respawns if r[0] > 0]
        if touched:
            self.roamers.remove(touched)
            self.respawns.append([self.rng.randint(*self.RESPAWN_FRAMES), touched.zone])
            self.encounter_spec = touched.species_id
            self.encounter_level = touched.level
            return "encounter"
        return None

    def chunk_of(self, cell):
        return cell[0] // self.CHUNK, cell[1] // self.CHUNK

    def explored(self, cell):
        cx, cy = self.chunk_of(cell)
        return f"{self.chunk_prefix}{cx},{cy}" in self.flags

    def _reveal_around(self):
        """Fog of war: reveal the map chunks around the player (saved with the game)."""
        cx, cy = self.chunk_of((self.player.x, self.player.y))
        r = self.REVEAL_RADIUS
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if 0 <= x * self.CHUNK < self.world.width and 0 <= y * self.CHUNK < self.world.height:
                    self.set_flag(f"{self.chunk_prefix}{x},{y}")

    def teleport(self, cell):
        """Fast travel: jump to ``cell`` (or the nearest walkable tile) and snap the camera."""
        cell = self.world.nearest_walkable(tuple(cell))
        self.avatar.x, self.avatar.y = self.world.cell_to_feet(cell)
        self.avatar.facing = (0, 1)
        self.avatar.reset_trail()
        self.player.x, self.player.y = cell
        self.dirty = True
        self.encounter_grace = 120
        self._update_area()
        self._reveal_around()
        self.cam_x, self.cam_y = self._camera_goal()

    # ------------------------------------------------------------------ update
    def update(self, dx=0, dy=0):
        """Advance one frame. Returns "encounter" when a wild MATHMON appears."""
        self.age += 1
        if self.message_frames:
            self.message_frames -= 1
        if self.banner_frames:
            self.banner_frames -= 1
        if self.encounter_grace:
            self.encounter_grace -= 1
        if self.dialogue:
            self.dialogue.age += 1
            dx = dy = 0
        moved = self.avatar.walk(dx, dy, self.world, self.npcs)
        fx, fy, _ = self.avatar.follower_spot()
        if math.hypot(fx - self.avatar.x, fy - self.avatar.y) > 48:
            self.avatar.reset_trail()
        for npc in self.npcs:
            npc.update(self.avatar)
        cell = self.avatar.cell()
        if cell != (self.player.x, self.player.y):
            self.player.x, self.player.y = cell
            self.dirty = True
            self._update_area()
            self._reveal_around()
        self.target = None if self.dialogue else self._find_target()
        self._camera_follow()
        if self._update_roamers():
            return "encounter"
        if moved:
            self.grass_distance += moved
            if self.grass_distance >= TILE:   # one movement step = one tile walked
                self.grass_distance = 0.0
                self.steps += 1
                if self.encounters.step(self.area_id, self.world.is_encounter(cell), bool(self.dialogue)):
                    self.encounter_spec, self.encounter_level = self.encounters.pick(self.area_id)
                    return "encounter"
        return None

    def tick(self):
        """Backwards-compatible single frame with no movement."""
        return self.update()

    def _update_area(self):
        area_id, name = self.world.area_at((self.player.x, self.player.y))
        if area_id and area_id != self.area_id:
            self.area_id, self.area_name = area_id, name
            self.banner_frames = 150
            first = f"visited:{area_id}" not in self.flags
            self.set_flag(f"visited:{area_id}")
            self._emit("visit", area=area_id, first=first, name=name)

    def _find_target(self):
        px, py = self.avatar.probe()
        best, best_distance = None, INTERACT_RANGE
        for npc in self.npcs:
            cx, cy = npc.center()
            distance = math.hypot(px - cx, py - cy)
            if distance < best_distance:
                best, best_distance = npc, distance
        for entry in self.objects.values():
            for cell in [entry["pos"]] + entry.get("solid", []):
                cx, cy = cell[0] * TILE + TILE / 2, cell[1] * TILE + TILE / 2
                distance = math.hypot(px - cx, py - cy)
                if distance < best_distance:
                    best, best_distance = entry, distance
        return best

    def target_id(self):
        if self.target is None:
            return None
        return self.target.id if isinstance(self.target, NPC) else self.target["id"]

    # ----------------------------------------------------------- interaction
    def handle_key(self, key):
        """Keyboard input that is not movement. Returns "battle", "boss" or None."""
        confirm = key in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER)
        if self.dialogue:
            dialogue = self.dialogue
            if confirm and not dialogue.revealed:
                dialogue.age = 10 ** 6  # first press finishes the typewriter text
                return None
            if dialogue.choices and dialogue.on_last_page:
                if key in (pygame.K_UP, pygame.K_w):
                    dialogue.selected = (dialogue.selected - 1) % len(dialogue.choices)
                elif key in (pygame.K_DOWN, pygame.K_s):
                    dialogue.selected = (dialogue.selected + 1) % len(dialogue.choices)
                elif confirm:
                    return self._choose(dialogue.choices[dialogue.selected][1])
                elif key == pygame.K_ESCAPE:
                    return self._choose("close")
                return None
            if confirm or key == pygame.K_ESCAPE:
                if dialogue.on_last_page or key == pygame.K_ESCAPE:
                    self.close_dialogue()
                else:
                    dialogue.page += 1
                    dialogue.age = 0
            return None
        if confirm:
            return self.interact()
        return None

    def open_dialogue(self, title, pages, subtitle="", choices=None, speaker=None, kind="message"):
        self.dialogue = Dialogue(title, pages, subtitle, choices, speaker, kind)
        self.target = None

    def close_dialogue(self):
        if self.dialogue and self.dialogue.speaker:
            self.dialogue.speaker.end_talk()
        self.dialogue = None

    def interact(self):
        target = self.target if self.target is not None else self._find_target()
        if target is None:
            return None
        if isinstance(target, NPC):
            return self._talk(target)
        return self._use_object(target)

    def quest_status(self, quest_id):
        return self.quests.status(quest_id) if self.quests and quest_id else "not_started"

    def _npc_pages(self, npc, key, fallback):
        dialogue = npc.spec.get("dialogue", {})
        return list(dialogue.get(key) or dialogue.get("any") or fallback)

    def _talk(self, npc):
        """NPC dialogue comes from structured map data (GDD 10.4); quest NPCs pick their lines by quest state."""
        npc.begin_talk(self.avatar)
        first_meeting = not self.has_flag(f"met:{npc.id}")
        self.set_flag(f"met:{npc.id}")
        title, subtitle = npc.name.upper(), npc.role
        if npc.kind == "quest":
            quest_id = npc.spec.get("quest")
            pages = self._npc_pages(npc, self.quest_status(quest_id), ["Hello!"])
            self._emit("talk", npc=npc.id)
            choices = None
            challenge = npc.spec.get("challenge")
            if challenge and self.quest_status(quest_id) == "active" and not self.has_flag(f"challenge:{challenge}"):
                choices = [("Help with the sums!", ("challenge", challenge)), ("Later", "close")]
            self.open_dialogue(title, pages, subtitle, choices, npc, "npc")
        elif npc.kind == "shop":
            pages = self._npc_pages(npc, "any", ["Welcome!"])
            self.open_dialogue(title, pages, subtitle, [("Browse the shop", "shop"), ("Goodbye", "close")], npc, "npc")
        elif npc.kind == "sanctuary":
            pages = self._npc_pages(npc, "any", ["Welcome to the Sanctuary."])
            self.open_dialogue(title, pages, subtitle, [("Heal my party", "heal"), ("Manage monsters", "sanctuary"),
                                                        ("Goodbye", "close")], npc, "npc")
        elif npc.kind in ("duel", "tutorial"):
            greetings = npc.spec.get("greeting", ["Ready for a practice battle?"])
            if npc.kind == "tutorial":
                pages = list(greetings) if first_meeting else [npc.next_line() or greetings[-1]]
            else:
                pages = [greetings[0] if first_meeting else greetings[-1]]
            self.duel_spec = npc.spec.get("battle_with")
            self.duel_name = npc.name
            self._emit("talk", npc=npc.id)
            self.open_dialogue(title, pages, subtitle, [("Practice battle!", "battle"), ("Not now", "close")], npc, "npc")
        elif npc.kind == "riddle" and not self.has_flag(f"riddle:{npc.id}"):
            riddle = npc.spec["riddle"]
            choices = [(choice, ("riddle", npc.id, choice)) for choice in riddle["choices"]]
            self.open_dialogue(title, [riddle["question"]], subtitle, choices, npc, "npc")
        else:
            self._emit("talk", npc=npc.id)
            self.open_dialogue(title, [npc.next_line() or "Hello there!"], subtitle, speaker=npc, kind="npc")
        return None

    def _choose(self, action):
        speaker = self.dialogue.speaker if self.dialogue else None
        if isinstance(action, tuple) and action[0] == "riddle":
            _, npc_id, picked = action
            npc = next(n for n in self.npcs if n.id == npc_id)
            riddle = npc.spec["riddle"]
            self.dialogue = None
            if picked == riddle["answer"]:
                self.set_flag(f"riddle:{npc_id}")
                self._grant(riddle["reward"], riddle.get("count", 1))
                reward = f"You received {riddle['reward']} x{riddle.get('count', 1)}!"
                self.open_dialogue(npc.name.upper(), [riddle["correct"], reward], npc.role, speaker=speaker, kind="npc")
            else:
                self.open_dialogue(npc.name.upper(), [riddle["wrong"]], npc.role, speaker=speaker, kind="npc")
            return None
        self.close_dialogue()
        return None if action == "close" else action

    def shrine_done(self, object_id):
        return self.has_flag(f"shrine:{object_id}:{self.today}")

    def _grant(self, item, count):
        if self.repository and self.player.player_id:
            self.repository.add_item(self.player.player_id, item, count)

    def _use_object(self, entry):
        kind, object_id = entry.get("kind", "flavour"), entry["id"]
        title = entry.get("title", entry.get("name", "").upper())
        if kind == "chest":
            if self.has_flag(f"opened:{object_id}"):
                self.open_dialogue(title, ["The chest is empty now. Something else may be hidden elsewhere."])
            else:
                self.set_flag(f"opened:{object_id}")
                self._grant(entry["item"], entry.get("count", 1))
                self.open_dialogue(title, [f"The lid creaks open... You found {entry['item']} x{entry.get('count', 1)}!"],
                                   kind="reward")
                self._emit("chest", object=object_id)
            return None
        if kind == "spring":
            healed = self.party.heal_all(1.0) if self.party else 0
            if self.party:
                self._emit("healed")
            extra = f"Your party recovers {healed} HP." if healed else "Your party is already full of energy."
            self.open_dialogue(title, list(entry.get("text", [])) + [extra])
            return None
        if kind == "challenge":
            challenge = entry["challenge"]
            self._emit("interact", object=object_id)
            if self.has_flag(f"challenge:{challenge}"):
                done = "The stone is safely in your bag." if object_id.startswith("stone") else "It glows steadily - already solved."
                self.open_dialogue(title, [done])
                return None
            needed = entry.get("requires_quest")
            if needed and self.quest_status(needed) != "active":
                self.open_dialogue(title, list(entry.get("text", [])) + ["It doesn't respond to you yet. Maybe someone is looking for it?"])
                return None
            spec = challenges()[challenge]
            self.open_dialogue(title, list(entry.get("text", [])) + [spec.get("intro", "")],
                               choices=[("Solve it!", ("challenge", challenge)), ("Later", "close")])
            return None
        if kind == "evolution":
            self.open_dialogue(title, entry.get("text", []), choices=[("Approach the shrine", "evolution"), ("Later", "close")])
            return None
        if kind == "boss_gate":
            return "boss"
        if kind == "arena":
            return "arena"
        if kind == "portal":
            needed = entry.get("requires")
            if needed and not self.has_flag(needed):
                locked = entry.get("locked_text", "The portal is dark and silent.")
                self.open_dialogue(title, locked if isinstance(locked, list) else [locked])
                return None
            if entry.get("door"):
                return ("travel_map", entry["destination"], tuple(entry["arrive"]))
            self.open_dialogue(title, entry.get("text", ["The portal shimmers."]),
                               choices=[("Step through", ("travel_map", entry["destination"], tuple(entry["arrive"]))),
                                        ("Not yet", "close")])
            return None
        if kind == "shrine":
            if self.shrine_done(object_id):
                self.open_dialogue(title, ["The shrine is resting. Come back tomorrow for a brand-new puzzle!"])
            else:
                self.open_dialogue(title, entry.get("text", ["An old stone shrine hums softly."]),
                                   choices=[("Solve it!", ("puzzle", object_id)), ("Later", "close")])
            return None
        self.set_flag(f"seen:{object_id}")
        self.open_dialogue(title, entry.get("text", ["Nothing unusual."]))
        return None

    def prompt(self):
        target = self.target
        if target is None:
            return ""
        if isinstance(target, NPC):
            suffix = {"duel": "  - practice battle", "tutorial": "  - tutorial", "riddle": "  - answer a riddle",
                      "shop": "  - shop", "sanctuary": "  - heal & storage"}.get(target.kind, "")
            if target.kind == "quest":
                status = self.quest_status(target.spec.get("quest"))
                suffix = {"not_started": "  - needs help!", "active": "  - quest"}.get(status, "")
            if target.kind == "riddle" and self.has_flag(f"riddle:{target.id}"):
                suffix = ""
            return f"[E] Talk to {target.name}{suffix}"
        kind = target.get("kind")
        base = f"[E] {target.get('verb', 'Inspect')} {target.get('name', 'object')}"
        if kind == "chest" and self.has_flag(f"opened:{target['id']}"):
            return base + "  (empty)"
        if kind == "spring":
            return base + "  - restores HP"
        if kind == "challenge":
            return base + ("  - solved" if self.has_flag(f"challenge:{target['challenge']}") else "  - maths challenge")
        if kind == "evolution":
            return base + "  - evolve monsters"
        if kind == "shrine":
            return base + ("  - solved today" if self.shrine_done(target["id"]) else "  - new puzzle!")
        if kind == "portal":
            needed = target.get("requires")
            if target.get("door"):
                return base
            return base + ("  - dormant" if needed and not self.has_flag(needed) else "  - travel")
        if kind == "arena":
            return base + "  - race AI rivals!"
        if kind == "boss_gate":
            return base + ("  - the boss awaits!" if self.boss_ready else "  - sealed")
        return base

    # ------------------------------------------------------------------ camera
    def _camera_goal(self):
        width, height = self.world.pixel_size()
        gx = self.avatar.x - VIRTUAL_WIDTH / 2
        gy = self.avatar.y - 8 - VIEW_HEIGHT / 2
        return max(0, min(width - VIRTUAL_WIDTH, gx)), max(0, min(height - VIEW_HEIGHT, gy))

    def _camera_follow(self):
        gx, gy = self._camera_goal()
        self.cam_x += (gx - self.cam_x) * 0.14
        self.cam_y += (gy - self.cam_y) * 0.14
        if abs(gx - self.cam_x) < 0.3:
            self.cam_x = gx
        if abs(gy - self.cam_y) < 0.3:
            self.cam_y = gy

    def to_screen(self, x, y):
        return int(round(x - self.cam_x)), int(round(y - self.cam_y)) + VIEW_TOP

    # -------------------------------------------------------------------- draw
    def draw(self, surface, frame=0):
        surface.fill(PALETTE["ink"])
        surface.set_clip((0, VIEW_TOP, VIRTUAL_WIDTH, VIEW_HEIGHT))
        cam_x, cam_y = int(round(self.cam_x)), int(round(self.cam_y))
        first_x, first_y = cam_x // TILE, cam_y // TILE
        player_cell = (self.player.x, self.player.y)
        painted = bool(self.world.background)
        if painted:
            surface.blit(painted_background(self.world), (0, VIEW_TOP), (cam_x, cam_y, VIRTUAL_WIDTH, VIEW_HEIGHT))
        for my in range(first_y, first_y + VIEW_HEIGHT // TILE + 2):
            for mx in range(first_x, first_x + VIRTUAL_WIDTH // TILE + 2):
                sx, sy = mx * TILE - cam_x, my * TILE - cam_y + VIEW_TOP
                rustle = (mx, my) == player_cell and self.avatar.moving
                if painted:
                    self._draw_painted_extra(surface, sx, sy, mx, my, frame, rustle)
                else:
                    self._draw_tile(surface, sx, sy, mx, my, frame, rustle)

        # Depth-sorted entities: objects, NPCs, companion and avatar.
        drawables = []
        for entry in self.objects.values():
            drawables.append(((entry["pos"][1] + 1) * TILE - 1, "object", entry))
        for npc in self.npcs:
            drawables.append((npc.y, "npc", npc))
        for roamer in self.roamers:
            drawables.append((roamer.y, "roamer", roamer))
        fx, fy, ffacing = self.avatar.follower_spot()
        drawables.append((fy - 0.5, "companion", (fx, fy, ffacing)))
        drawables.append((self.avatar.y, "avatar", self.avatar))
        for _, kind, item in sorted(drawables, key=lambda d: d[0]):
            if kind == "object":
                self._draw_object(surface, item, frame)
            elif kind == "roamer":
                self._draw_roamer(surface, item, frame)
            elif kind == "companion":
                self._draw_companion(surface, *item, frame)
            else:
                self._draw_actor(surface, item)

        if painted and self.world.canopy:
            # Tree tops in front of anyone standing just north of the forest edge.
            canopy = painted_background(self.world, self.world.canopy, alpha=True)
            surface.blit(canopy, (0, VIEW_TOP), (cam_x, cam_y, VIRTUAL_WIDTH, VIEW_HEIGHT))
        self._draw_barriers(surface, frame)
        self._draw_markers(surface, frame)
        if self.target is not None:
            self._draw_target(surface, frame)
        for npc in self.npcs:
            if npc.bubble:
                self._draw_bubble(surface, npc)
        surface.set_clip(None)
        self._draw_hud(surface, frame)

    # ---- tiles
    def _draw_painted_extra(self, surface, x, y, mx, my, frame, rustle):
        """On painted maps only hand-added features need drawing: trails, plank bridges and grass."""
        code = self.world.tile_at(mx, my)
        seed = (mx * 7349 + my * 1931) % 97
        if self.world.baked_features:
            # The art already contains paths, bridges and grass: only animate.
            if code == "w" and (seed + frame // 24) % 13 == 0:
                sx = x + (seed * 3 + frame // 6) % 11
                pygame.draw.line(surface, (190, 232, 248), (sx, y + 4 + seed % 8), (sx + 3, y + 4 + seed % 8))
            elif code == "G":
                sway = ((frame // 16 + mx) % 3) - 1
                pygame.draw.rect(surface, (122, 196, 96), (x + 5 + sway, y + 4, 2, 2))
                if rustle:
                    for i in range(3):
                        wiggle = ((frame // 3 + i) % 3) - 1
                        pygame.draw.rect(surface, (140, 210, 110), (x + 3 + i * 4 + wiggle, y + 5, 2, 7))
            return
        if code == "p":
            pygame.draw.rect(surface, (209, 171, 110), (x, y, TILE, TILE))
            pygame.draw.rect(surface, (226, 192, 130), (x + seed % 10 + 2, y + seed % 9 + 2, 3, 2))
            pygame.draw.rect(surface, (180, 142, 92), (x + (seed * 3) % 12, y + (seed * 7) % 13, 2, 1))
            for nx, ny, edge in ((0, -1, (x, y, TILE, 1)), (0, 1, (x, y + TILE - 1, TILE, 1)),
                                 (-1, 0, (x, y, 1, TILE)), (1, 0, (x + TILE - 1, y, 1, TILE))):
                if self.world.tile_at(mx + nx, my + ny) not in ("p", "b"):
                    pygame.draw.rect(surface, (150, 118, 78), edge)
        elif code == "b":
            pygame.draw.rect(surface, (118, 82, 52), (x, y, TILE, TILE))
            rail = (70, 46, 30)
            if (mx, my) in self.world.vertical_bridges:
                # Planks run east-west; rails only on the bridge's outer edges.
                for i in range(1, TILE, 4):
                    pygame.draw.line(surface, (160, 116, 72), (x, y + i), (x + TILE - 1, y + i), 3)
                if self.world.tile_at(mx - 1, my) != "b":
                    pygame.draw.rect(surface, rail, (x, y, 2, TILE))
                if self.world.tile_at(mx + 1, my) != "b":
                    pygame.draw.rect(surface, rail, (x + TILE - 2, y, 2, TILE))
            else:
                for i in range(1, TILE, 4):
                    pygame.draw.line(surface, (160, 116, 72), (x + i, y), (x + i, y + TILE - 1), 3)
                if self.world.tile_at(mx, my - 1) != "b":
                    pygame.draw.rect(surface, rail, (x, y, TILE, 2))
                if self.world.tile_at(mx, my + 1) != "b":
                    pygame.draw.rect(surface, rail, (x, y + TILE - 2, TILE, 2))
        elif code == "G":
            painted_grass = any(x0 <= mx < x0 + w and y0 <= my < y0 + h for x0, y0, w, h in self.world.paint_encounters)
            if painted_grass:
                for i in range(4):
                    sway = ((frame // 14 + i + mx) % 3) - 1
                    bx = x + 1 + i * 4 + sway
                    pygame.draw.rect(surface, (60, 124, 66), (bx, y + 5 + (i % 2) * 2, 2, 9 - (i % 2) * 2))
                    pygame.draw.rect(surface, (122, 186, 98), (bx, y + 5 + (i % 2) * 2, 2, 2))
            if rustle:
                for i in range(3):
                    sway = ((frame // 3 + i) % 3) - 1
                    pygame.draw.rect(surface, (140, 200, 110), (x + 3 + i * 4 + sway, y + 6, 2, 6))

    def _draw_tile(self, surface, x, y, mx, my, frame, rustle):
        code = self.world.tile_at(mx, my)
        seed = (mx * 7349 + my * 1931) % 97
        grass, grass_hi = (88, 154, 92), (108, 176, 104)
        if code in ("g", "f", "r", "R", "T", "G"):
            pygame.draw.rect(surface, grass, (x, y, TILE, TILE))
            if code in ("T", "R") and any(self.world.tile_at(mx + ox, my + oy) == "G"
                                          for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                pygame.draw.rect(surface, (55, 116, 72), (x, y, TILE, TILE))
            if code == "g" and seed % 3 == 0:
                pygame.draw.rect(surface, grass_hi, (x + seed % 11, y + seed % 13, 2, 2))
                pygame.draw.rect(surface, grass_hi, (x + (seed * 3) % 12, y + (seed * 5) % 12, 1, 3))
        if code == "G":
            pygame.draw.rect(surface, (55, 116, 72), (x, y, TILE, TILE))
            for i in range(4):
                sway = ((frame // 14 + i + mx) % 3) - 1
                if rustle:
                    sway = ((frame // 3 + i) % 3) - 1
                bx = x + 1 + i * 4 + sway
                pygame.draw.rect(surface, (78, 150, 86), (bx, y + 4 + (i % 2) * 2, 2, 10 - (i % 2) * 2))
                pygame.draw.rect(surface, (118, 184, 104), (bx, y + 4 + (i % 2) * 2, 2, 2))
        elif code == "f":
            for i, color in enumerate(((242, 187, 82), (235, 112, 92), (255, 247, 220))):
                fx, fy = x + 2 + (seed + i * 5) % 12, y + 2 + (seed * (i + 2)) % 12
                pygame.draw.rect(surface, color, (fx, fy, 2, 2))
        elif code == "p":
            pygame.draw.rect(surface, (190, 155, 98), (x, y, TILE, TILE))
            pygame.draw.rect(surface, (210, 178, 116), (x + seed % 10 + 2, y + seed % 9 + 2, 3, 2))
            pygame.draw.rect(surface, (164, 130, 86), (x + (seed * 3) % 12, y + (seed * 7) % 13, 2, 1))
        elif code == "w":
            pygame.draw.rect(surface, (67, 144, 181), (x, y, TILE, TILE))
            if self.world.tile_at(mx, my - 1) != "w":
                pygame.draw.rect(surface, (140, 202, 214), (x, y, TILE, 2))
            pygame.draw.rect(surface, (112, 188, 205), (x + 3 + ((frame // 15 + seed) % 6), y + 6, 5, 1))
            pygame.draw.rect(surface, (52, 122, 166), (x + 8 - ((frame // 20 + seed) % 4), y + 12, 6, 1))
        elif code == "r":
            for i in range(4):
                sway = ((frame // 12 + i) % 3) - 1
                pygame.draw.rect(surface, (172, 195, 116), (x + 2 + i * 3 + sway, y + 3, 2, 11))
                pygame.draw.rect(surface, (120, 86, 56), (x + 2 + i * 3 + sway, y + 3, 2, 3))
        elif code == "R":
            pygame.draw.ellipse(surface, (70, 120, 80), (x + 1, y + 11, 14, 5))
            pygame.draw.rect(surface, (128, 132, 128), (x + 2, y + 5, 12, 9))
            pygame.draw.rect(surface, (160, 166, 158), (x + 4, y + 4, 8, 4))
            pygame.draw.rect(surface, (96, 100, 98), (x + 2, y + 12, 12, 2))
        elif code == "T":
            pygame.draw.ellipse(surface, (60, 116, 74), (x + 1, y + 12, 14, 4))
            pygame.draw.rect(surface, (102, 69, 48), (x + 7, y + 10, 3, 6))
            pygame.draw.rect(surface, (39, 90, 62), (x + 1, y + 3, 14, 9))
            pygame.draw.rect(surface, (54, 112, 71), (x + 3, y, 10, 9))
            pygame.draw.rect(surface, (79, 145, 83), (x + 5, y + 2, 4, 3))
        elif code in ("F", "C", "S", "P"):
            pygame.draw.rect(surface, (166, 118, 74), (x, y, TILE, TILE))
            pygame.draw.line(surface, (140, 96, 58), (x, y + 7), (x + TILE, y + 7))
            pygame.draw.line(surface, (140, 96, 58), (x + (8 if my % 2 else 3), y), (x + (8 if my % 2 else 3), y + 7))
            if code == "C":
                pygame.draw.rect(surface, (110, 70, 44), (x, y + 2, TILE, 12))
                pygame.draw.rect(surface, (196, 150, 96), (x, y + 2, TILE, 4))
            elif code == "S":
                pygame.draw.rect(surface, (96, 62, 40), (x + 1, y, 14, 15))
                for i, color in enumerate(((235, 112, 92), (110, 177, 206), (137, 199, 124))):
                    pygame.draw.rect(surface, color, (x + 3 + i * 4, y + 3, 3, 4))
                    pygame.draw.rect(surface, color, (x + 3 + i * 4, y + 9, 3, 4))
            elif code == "P":
                pygame.draw.rect(surface, (150, 90, 60), (x + 4, y + 9, 8, 6))
                pygame.draw.circle(surface, (70, 140, 80), (x + 8, y + 6), 5)
        elif code == "W":
            pygame.draw.rect(surface, (92, 70, 90), (x, y, TILE, TILE))
            pygame.draw.rect(surface, (120, 96, 118), (x, y, TILE, 3))
            if (mx + my) % 3 == 0:
                pygame.draw.rect(surface, (110, 84, 106), (x + 4, y + 7, 7, 4))
        elif code in ("B", "D"):
            roof = self.world.tile_at(mx, my - 1) not in ("B", "D")
            if roof:
                pygame.draw.rect(surface, (122, 58, 52), (x, y, TILE, TILE))
                for i in range(0, TILE, 4):
                    pygame.draw.line(surface, (150, 76, 64), (x, y + i + 2), (x + TILE, y + i + 2))
                pygame.draw.rect(surface, (91, 42, 40), (x, y + 14, TILE, 2))
            else:
                pygame.draw.rect(surface, (217, 184, 125), (x, y, TILE, TILE))
                pygame.draw.line(surface, (190, 154, 98), (x, y + 7), (x + TILE, y + 7))
                pygame.draw.rect(surface, (170, 132, 84), (x, y + 14, TILE, 2))
                if code == "D":
                    pygame.draw.rect(surface, (92, 65, 56), (x + 4, y + 3, 8, 13))
                    pygame.draw.rect(surface, PALETTE["gold"], (x + 10, y + 10, 1, 2))
                elif (mx + my) % 2 == 0:
                    pygame.draw.rect(surface, (64, 98, 128), (x + 4, y + 3, 8, 6))
                    pygame.draw.rect(surface, (160, 214, 230), (x + 5, y + 4, 3, 2))

    # ---- objects and actors
    def _draw_object(self, surface, entry, frame):
        cx, cy = entry["pos"]
        x, y = self.to_screen(cx * TILE, cy * TILE)
        kind, object_id = entry.get("kind"), entry["id"]
        if object_id == "hut_door" or entry.get("painted"):
            return  # already part of the hut / the world painting
        shadow = (60, 116, 74)
        if kind == "sign":
            pygame.draw.ellipse(surface, shadow, (x + 3, y + 12, 10, 4))
            pygame.draw.rect(surface, (123, 77, 47), (x + 7, y + 7, 2, 8))
            pygame.draw.rect(surface, (92, 60, 40), (x + 2, y + 1, 12, 8))
            pygame.draw.rect(surface, (214, 170, 104), (x + 3, y + 2, 10, 6))
            pygame.draw.line(surface, (150, 110, 70), (x + 5, y + 4), (x + 10, y + 4))
            pygame.draw.line(surface, (150, 110, 70), (x + 5, y + 6), (x + 9, y + 6))
        elif kind == "chest":
            opened = self.has_flag(f"opened:{object_id}")
            pygame.draw.ellipse(surface, shadow, (x + 1, y + 12, 14, 4))
            pygame.draw.rect(surface, (84, 52, 38), (x + 2, y + 6, 12, 9))
            pygame.draw.rect(surface, (146, 94, 56), (x + 3, y + 7, 10, 7))
            if opened:
                pygame.draw.rect(surface, (40, 26, 22), (x + 3, y + 5, 10, 3))
                pygame.draw.rect(surface, (120, 76, 48), (x + 2, y + 1, 12, 4))
            else:
                pygame.draw.rect(surface, (120, 76, 48), (x + 2, y + 3, 12, 4))
                pygame.draw.rect(surface, PALETTE["gold"], (x + 7, y + 6, 2, 3))
                if frame % 90 < 8:
                    pygame.draw.rect(surface, PALETTE["white"], (x + 11, y + 3, 1, 1))
        elif kind == "spring":
            pygame.draw.ellipse(surface, (120, 124, 120), (x, y + 3, 16, 12))
            pygame.draw.ellipse(surface, (98, 180, 206), (x + 2, y + 5, 12, 8))
            glint = (frame // 10) % 8
            pygame.draw.rect(surface, PALETTE["white"], (x + 4 + glint, y + 7, 2, 1))
            if frame % 60 < 30:
                pygame.draw.rect(surface, (200, 240, 240), (x + 9, y + 9, 1, 1))
        elif kind == "boss_gate":
            pulse = (math.sin(frame / 20) + 1) / 2
            glow_strength = 0.55 + 0.45 * pulse if self.boss_ready else 0.15 + 0.15 * pulse
            glow = tuple(int(a + (b - a) * glow_strength) for a, b in zip((40, 65, 82), (190, 120, 220)))
            left = x - TILE
            pygame.draw.rect(surface, glow, (left + 12, y - 8, 24, 24))
            for px in (left, left + 2 * TILE):
                pygame.draw.rect(surface, (96, 88, 110), (px + 2, y - 10, 12, 26))
                pygame.draw.rect(surface, (130, 120, 146), (px + 4, y - 8, 8, 22))
                pygame.draw.line(surface, (80, 72, 94), (px + 4, y), (px + 12, y))
            pygame.draw.rect(surface, (96, 88, 110), (left, y - 16, 3 * TILE, 8))
            pygame.draw.rect(surface, (130, 120, 146), (left + 2, y - 14, 3 * TILE - 4, 4))
            pygame.draw.rect(surface, PALETTE["gold"], (left + 22, y - 15, 4, 6))
        elif kind == "arena":
            # A small stadium, 3 tiles wide and 2 tall, entrance facing south.
            left, top = x - TILE, y - TILE - 8
            pygame.draw.ellipse(surface, shadow, (left - 2, y + 10, 3 * TILE + 4, 8))
            pygame.draw.rect(surface, (120, 104, 160), (left, top + 10, 3 * TILE, TILE + 14))
            pygame.draw.rect(surface, (150, 134, 196), (left + 2, top + 12, 3 * TILE - 4, 6))
            for col in range(left + 4, left + 3 * TILE - 2, 6):
                pygame.draw.rect(surface, (96, 82, 130), (col, top + 20, 3, TILE + 2))
            pygame.draw.ellipse(surface, (196, 70, 70), (left - 3, top, 3 * TILE + 6, 16))
            pygame.draw.ellipse(surface, (226, 106, 92), (left, top + 2, 3 * TILE, 9))
            for i, color in enumerate(((242, 187, 82), (110, 177, 206), (137, 199, 124))):
                fx = left + 8 + i * 15
                pygame.draw.line(surface, (60, 50, 60), (fx, top - 8), (fx, top + 2))
                wave = (frame // 8 + i) % 2
                pygame.draw.rect(surface, color, (fx + 1, top - 8 + wave, 6, 4))
            pygame.draw.rect(surface, (40, 30, 50), (x + 3, y - 2, 10, 18))
            pygame.draw.rect(surface, (242, 187, 82), (x + 2, y - 4, 12, 3))
        elif kind == "portal":
            needed = entry.get("requires")
            awake = not needed or self.has_flag(needed)
            pygame.draw.ellipse(surface, shadow, (x - 2, y + 11, 20, 6))
            pygame.draw.rect(surface, (90, 92, 110), (x, y - 6, 3, 21))
            pygame.draw.rect(surface, (90, 92, 110), (x + 13, y - 6, 3, 21))
            pygame.draw.rect(surface, (120, 124, 140), (x - 1, y - 9, 18, 4))
            if awake:
                for ring in range(3):
                    phase = (frame // 4 + ring * 5) % 15
                    color = [(120, 230, 240), (190, 150, 255), (240, 140, 220)][ring]
                    pygame.draw.ellipse(surface, color, (x + 3 + phase // 5, y - 5 + phase // 3,
                                                         10 - 2 * (phase // 5), 18 - 2 * (phase // 3)), 1)
                if frame % 20 < 10:
                    pygame.draw.rect(surface, (230, 250, 255), (x + 7, y + 3, 2, 2))
            else:
                pygame.draw.rect(surface, (40, 44, 60), (x + 3, y - 5, 10, 18))
        elif kind == "challenge" and object_id.startswith("stone"):
            if self.has_flag(f"challenge:{entry['challenge']}"):
                return
            pygame.draw.ellipse(surface, shadow, (x + 2, y + 11, 12, 4))
            pygame.draw.ellipse(surface, (150, 156, 150), (x + 3, y + 5, 10, 9))
            pygame.draw.ellipse(surface, (190, 196, 188), (x + 4, y + 6, 6, 4))
            numeral = {"stone_1": "I", "stone_2": "II", "stone_3": "III"}.get(object_id, "")
            from game.ui import text as draw_text
            draw_text(surface, numeral, (x + 8, y + 9), 7, PALETTE["ink"], center=True)
        elif kind == "challenge":
            done = self.has_flag(f"challenge:{entry['challenge']}")
            crystal = object_id == "crystal_seal"
            pulse = (math.sin(frame / 12) + 1) / 2
            glow = (120, 230, 240) if done else tuple(int(60 + 120 * pulse) for _ in range(3))
            pygame.draw.ellipse(surface, shadow, (x - 1, y + 11, 18, 5))
            if crystal:
                color = (240, 150, 230) if done else (150, 110, 160)
                pygame.draw.polygon(surface, color, [(x + 8, y - 6), (x + 14, y + 6), (x + 8, y + 14), (x + 2, y + 6)])
                pygame.draw.polygon(surface, PALETTE["white"], [(x + 8, y - 4), (x + 10, y + 4), (x + 8, y + 2)])
            else:
                pygame.draw.circle(surface, (96, 98, 104), (x + 8, y + 7), 8)
                pygame.draw.circle(surface, (140, 144, 150), (x + 8, y + 7), 6)
                pygame.draw.circle(surface, glow, (x + 8, y + 7), 3)
        elif kind == "evolution":
            pulse = (frame // 10) % 6
            pygame.draw.ellipse(surface, shadow, (x - 1, y + 11, 18, 5))
            pygame.draw.rect(surface, (110, 120, 150), (x + 3, y + 6, 10, 9))
            pygame.draw.polygon(surface, (120, 220, 240), [(x + 8, y - 14 + pulse // 3), (x + 13, y + 6), (x + 3, y + 6)])
            pygame.draw.polygon(surface, PALETTE["white"], [(x + 8, y - 11), (x + 10, y + 2), (x + 8, y)])
        elif kind == "shrine":
            rune = SHRINE_COLORS.get(entry.get("puzzle"), PALETTE["gold"])
            done = self.shrine_done(object_id)
            pygame.draw.ellipse(surface, shadow, (x, y + 12, 16, 5))
            pygame.draw.rect(surface, (96, 98, 104), (x + 2, y + 9, 12, 6))
            pygame.draw.rect(surface, (128, 132, 136), (x + 3, y + 1, 10, 10))
            pygame.draw.rect(surface, (160, 164, 168), (x + 4, y + 2, 8, 2))
            glow = rune if not done else (90, 96, 100)
            pulse = 0 if done else (frame // 12) % 2
            pygame.draw.rect(surface, glow, (x + 6, y + 4 - pulse, 4, 5))
            if not done and frame % 50 < 6:
                pygame.draw.rect(surface, PALETTE["white"], (x + 7, y + 1, 1, 1))
        elif object_id == "campfire":
            pygame.draw.rect(surface, (110, 112, 108), (x + 2, y + 10, 12, 4))
            pygame.draw.rect(surface, (102, 69, 48), (x + 3, y + 9, 10, 3))
            flicker = (frame // 5) % 3
            pygame.draw.rect(surface, PALETTE["coral"], (x + 5, y + 3 + flicker, 6, 7 - flicker))
            pygame.draw.rect(surface, PALETTE["gold"], (x + 6 + (flicker % 2), y + 5 + flicker, 3, 4 - flicker // 2))
            if frame % 40 < 20:
                pygame.draw.rect(surface, PALETTE["gold"], (x + 8 + flicker, y + flicker, 1, 1))
        else:  # tablet and other stone markers
            pygame.draw.ellipse(surface, shadow, (x + 2, y + 12, 12, 4))
            pygame.draw.rect(surface, (110, 114, 112), (x + 3, y + 2, 10, 12))
            pygame.draw.rect(surface, (150, 156, 150), (x + 4, y + 3, 8, 10))
            for row in range(3):
                pygame.draw.line(surface, (100, 104, 102), (x + 5, y + 5 + row * 3), (x + 10, y + 5 + row * 3))

    CHARACTER_HEIGHT = 26

    def _draw_actor(self, surface, actor):
        from game import monster_sprites
        sx, sy = self.to_screen(actor.x, actor.y)
        pygame.draw.ellipse(surface, (50, 96, 62), (sx - 6, sy - 2, 12, 4))
        if actor.sheet and monster_sprites.available(actor.sheet):
            if actor.moving:
                pose = (1, 0, 2, 0)[int(actor.walk_time * 8) % 4]
            elif getattr(actor, "state", "") == "talking":
                pose = 4  # wave while chatting
            else:
                pose = 0
            monster_sprites.draw(surface, actor.sheet, (sx, sy + 1), self.CHARACTER_HEIGHT, pose,
                                 flip=actor.facing == (-1, 0))
            return
        image = frame_for(actor.frames, actor.facing, actor.walk_time, actor.moving)
        bob = 1 if actor.moving and int(actor.walk_time * 8) % 2 else 0
        surface.blit(image, (sx - 8, sy - 15 - bob))

    def _draw_companion(self, surface, x, y, facing, frame):
        sx, sy = self.to_screen(x, y)
        spec = self.companion_spec()
        hop = 1 if self.avatar.moving and (frame // 6) % 2 else 0
        pygame.draw.ellipse(surface, (50, 96, 62), (sx - 6, sy - 2, 12, 4))
        pose = ("idle", "idle2", "idle3", "idle2")[(frame // 8) % 4] if self.avatar.moving else "idle"
        draw_creature(surface, spec, (sx, sy - hop), 20, pose, flip=facing == (-1, 0))

    def _draw_roamer(self, surface, roamer, frame):
        sx, sy = self.to_screen(roamer.x, roamer.y)
        if not (-24 <= sx <= VIRTUAL_WIDTH + 24 and VIEW_TOP - 8 <= sy <= VIEW_TOP + VIEW_HEIGHT + 24):
            return
        hop = 1 if roamer.moving and (roamer.age // 6) % 2 else 0
        cycle = ("idle", "idle2", "idle3", "idle2")[(roamer.age // (8 if roamer.moving else 18)) % 4]
        pygame.draw.ellipse(surface, (40, 96, 52), (sx - 7, sy - 2, 14, 4))
        draw_creature(surface, roamer.spec, (sx, sy - hop), 20, cycle, flip=roamer.facing < 0)
        # Grass blades in front of its feet: it is standing *in* the tall grass.
        for i in range(4):
            sway = ((frame // 12 + i) % 3) - 1
            pygame.draw.rect(surface, (62, 140, 66), (sx - 7 + i * 4 + sway, sy - 4, 2, 4))
            pygame.draw.rect(surface, (122, 196, 96), (sx - 7 + i * 4 + sway, sy - 4, 2, 1))
        bob = 1 if frame % 40 < 20 else 0
        name = roamer.spec.name
        head = sy - round(20 * roamer.spec.size) - hop  # top of the sprite
        record = self.records.get(roamer.species_id, {})
        if record.get("captured"):
            heart(surface, sx - 4, head - 10 - bob, PALETTE["mint"])
        elif not record.get("seen"):
            # Never seen: a gold sparkle says "new for your MathDex".
            pygame.draw.rect(surface, PALETTE["gold"], (sx - 1, head - 9 - bob, 2, 6))
            pygame.draw.rect(surface, PALETTE["gold"], (sx - 3, head - 7 - bob, 6, 2))
        if roamer.alert and not record.get("captured"):
            pygame.draw.rect(surface, PALETTE["coral"], (sx + 9, head - 2, 2, 5))
            pygame.draw.rect(surface, PALETTE["coral"], (sx + 9, head + 4, 2, 2))

    def _draw_markers(self, surface, frame):
        bob = 1 if frame % 40 < 20 else 0
        for entry in self.objects.values():
            kind, object_id = entry.get("kind"), entry["id"]
            fresh = (kind == "chest" and not self.has_flag(f"opened:{object_id}")) or \
                    (kind == "shrine" and not self.shrine_done(object_id)) or \
                    (kind in ("sign", "flavour") and not self.has_flag(f"seen:{object_id}")) or \
                    (kind == "challenge" and not self.has_flag(f"challenge:{entry['challenge']}") and
                     (not entry.get("requires_quest") or self.quest_status(entry["requires_quest"]) == "active"))
            if fresh:
                x, y = self.to_screen(entry["pos"][0] * TILE + 8, entry["pos"][1] * TILE)
                self._diamond(surface, x, y - 5 - bob, PALETTE["gold"])
        for npc in self.npcs:
            if npc.state == "talking":
                continue
            x, y = self.to_screen(npc.x, npc.y)
            if npc.kind == "duel" and not self.has_flag(f"met:{npc.id}"):
                pygame.draw.rect(surface, PALETTE["gold"], (x - 1, y - 26 - bob, 2, 5))
                pygame.draw.rect(surface, PALETTE["gold"], (x - 1, y - 20 - bob, 2, 2))
            elif npc.kind == "riddle" and not self.has_flag(f"riddle:{npc.id}"):
                self._diamond(surface, x, y - 22 - bob, PALETTE["sky"])
            elif npc.kind == "quest" and self.quest_status(npc.spec.get("quest")) != "completed":
                color = PALETTE["gold"] if self.quest_status(npc.spec.get("quest")) == "not_started" else PALETTE["sky"]
                pygame.draw.rect(surface, color, (x - 1, y - 28 - bob, 2, 5))
                pygame.draw.rect(surface, color, (x - 1, y - 22 - bob, 2, 2))

    @staticmethod
    def _diamond(surface, x, y, color):
        pygame.draw.rect(surface, color, (x - 1, y - 1, 2, 1))
        pygame.draw.rect(surface, color, (x - 2, y, 4, 2))
        pygame.draw.rect(surface, color, (x - 1, y + 2, 2, 1))

    def _draw_target(self, surface, frame):
        target = self.target
        if isinstance(target, NPC):
            x, y = self.to_screen(target.x - 8, target.y - 16)
            w = h = 18
        else:
            cx, cy = target["pos"]
            x, y = self.to_screen(cx * TILE, cy * TILE)
            w = h = TILE
            if target.get("kind") == "boss_gate":
                x, y, w, h = x - TILE, y - 16, 3 * TILE, TILE + 16
        pad = 1 + (frame // 15) % 2
        x, y, w, h = x - pad, y - pad, w + pad * 2, h + pad * 2
        color = PALETTE["white"]
        for cx, cy, sx, sy in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
            pygame.draw.line(surface, color, (cx, cy), (cx + 3 * sx, cy))
            pygame.draw.line(surface, color, (cx, cy), (cx, cy + 3 * sy))

    def _draw_bubble(self, surface, npc):
        message, frames_left = npc.bubble
        sx, _ = self.to_screen(npc.x, npc.y)
        if not -8 <= sx <= VIRTUAL_WIDTH + 8:
            return
        lines = wrap_lines(message, 110, 9)[:3]
        width = max(text_width for text_width in (self._measure(line) for line in lines)) + 8
        height = len(lines) * 9 + 5
        sx, sy = self.to_screen(npc.x, npc.y - 22)
        left = max(2, min(VIRTUAL_WIDTH - width - 2, sx - width // 2))
        top = max(VIEW_TOP + 2, sy - height)
        pygame.draw.rect(surface, PALETTE["ink"], (left - 1, top - 1, width + 2, height + 2))
        pygame.draw.rect(surface, (244, 239, 224), (left, top, width, height))
        tail_x = max(left + 3, min(left + width - 4, sx))
        pygame.draw.polygon(surface, (244, 239, 224), [(tail_x - 2, top + height), (tail_x + 2, top + height), (tail_x, top + height + 3)])
        for i, line in enumerate(lines):
            text(surface, line, (left + 4, top + 3 + i * 9), 9, PALETTE["ink"])

    @staticmethod
    def _measure(line):
        from game.ui import measure
        return measure(line, 9)[0]

    def quest_hint(self):
        """The main quest's current step, shown under the controls."""
        for quest_id in self.quests.active():
            if self.quests.definition(quest_id)["category"] == "main":
                return "QUEST: " + self.quests.step_text(quest_id)
        active = self.quests.active()
        return ("QUEST: " + self.quests.step_text(active[0])) if active else ""

    def _draw_barriers(self, surface, frame):
        """The broken plank bridge: a gap with dangling planks until Bram's quest is done."""
        for barrier in self.world.barriers:
            if barrier.get("open"):
                continue
            x0, y0, w, h = barrier["rect"]
            for cx in range(x0 + w // 2 - 2, x0 + w // 2 + 3):
                for cy in range(y0, y0 + h):
                    sx, sy = self.to_screen(cx * TILE, cy * TILE)
                    pygame.draw.rect(surface, (52, 112, 150), (sx, sy, TILE, TILE))
                    if (cx + cy + frame // 20) % 3 == 0:
                        pygame.draw.line(surface, (150, 210, 230), (sx + 3, sy + 8), (sx + 9, sy + 8))
            for cx in (x0 + w // 2 - 3, x0 + w // 2 + 3):
                sx, sy = self.to_screen(cx * TILE, y0 * TILE)
                pygame.draw.line(surface, (120, 82, 50), (sx + 8, sy), (sx + 4, sy + 2 * TILE - 2), 3)

    # ---- HUD, banner, prompt, dialogue
    def _draw_hud(self, surface, frame):
        if self.banner_frames:
            elapsed = 150 - self.banner_frames
            slide = min(elapsed, self.banner_frames, 12)
            top = VIEW_TOP - 18 + slide * 2
            panel(surface, (90, top, 140, 18), PALETTE["night"], PALETTE["gold"])
            if top >= VIEW_TOP - 4:
                text(surface, self.area_name, (160, top + 9), 12, PALETTE["cream"], center=True)
        pygame.draw.rect(surface, PALETTE["ink"], (0, 0, VIRTUAL_WIDTH, VIEW_TOP))
        pygame.draw.line(surface, PALETTE["night"], (0, VIEW_TOP - 1), (VIRTUAL_WIDTH, VIEW_TOP - 1), 2)
        text(surface, self.area_name.upper(), (7, 5), 14, PALETTE["gold"])
        leader = self.party.lead if self.party and self.party.party else self.player
        leader_name = leader.name if self.party and self.party.party else self.player.name
        text(surface, f"{leader_name[:12]}  Lv {leader.level}", (196, 3), 10, PALETTE["white"])
        meter(surface, 196, 14, 82, 6, leader.hp, leader.max_hp, PALETTE["mint"], warn=True)
        text(surface, f"{leader.hp}/{leader.max_hp}", (313, 13), 9, PALETTE["cream"], align="right")


        bottom = VIEW_TOP + VIEW_HEIGHT
        pygame.draw.rect(surface, PALETTE["night"], (0, bottom, VIRTUAL_WIDTH, 240 - bottom))
        prompt = self.prompt()
        if self.dialogue:
            footer = "UP/DOWN: CHOOSE     E / ENTER: SELECT" if self.dialogue.choices and self.dialogue.on_last_page                 else "E / ENTER: CONTINUE     ESC: CLOSE"
            text(surface, footer, (160, bottom + 12), 9, PALETTE["cream"], center=True)
        elif prompt:
            text(surface, prompt, (160, bottom + 7), 11, PALETTE["gold"], center=True)
            text(surface, "WASD: WALK   TAB: MENU   N: MAP   T: TRIALS   ESC: PAUSE", (160, bottom + 18), 8, PALETTE["muted"], center=True)
        else:
            text(surface, "WASD: WALK  E: TALK/USE  TAB: MENU  N: MAP  T: TRIALS  ESC: PAUSE", (160, bottom + 7), 9,
                 PALETTE["cream"], center=True)
            hint = self.quest_hint() if self.quests else ""
            text(surface, hint or "Tall grass hides wild MATHMON.", (160, bottom + 18), 8, PALETTE["muted"], center=True)

        if self.message_frames and not self.dialogue:
            panel(surface, (8, bottom - 40, 304, 34), PALETTE["night"], PALETTE["gold"])
            wrapped(surface, self.message, (16, bottom - 34, 288, 24), 11, PALETTE["white"], 12, 2)
        if self.dialogue:
            self._draw_dialogue(surface, frame)

    def _draw_dialogue(self, surface, frame):
        d = self.dialogue
        rect = pygame.Rect(6, 138, 308, 74)
        border = PALETTE["gold"] if d.kind == "reward" else PALETTE["cream"]
        panel(surface, rect, PALETTE["night"], border)
        left = rect.x + 8
        if d.speaker is not None:
            pygame.draw.rect(surface, PALETTE["deep"], (rect.x + 6, rect.y + 8, 36, 36))
            from game import monster_sprites
            if d.speaker.sheet and monster_sprites.available(d.speaker.sheet):
                surface.set_clip((rect.x + 6, rect.y + 8, 36, 36))
                monster_sprites.draw(surface, d.speaker.sheet, (rect.x + 24, rect.y + 66), 56, 0)
                surface.set_clip(None)
            else:
                portrait = pygame.transform.scale(d.speaker.frames["down"][0], (32, 32))
                surface.blit(portrait, (rect.x + 8, rect.y + 10))
            left = rect.x + 48
        title_rect = text(surface, d.title, (left, rect.y + 6), 12, PALETTE["gold"])
        if d.subtitle:
            text(surface, d.subtitle, (title_rect.right + 6, rect.y + 8), 9, PALETTE["muted"])
        has_choices = d.choices and d.on_last_page and d.revealed
        text_width = rect.right - left - (96 if d.choices and d.on_last_page else 10)
        # Typewriter reveal; the first confirm press shows the whole page.
        message = d.pages[d.page]
        shown = message[:max(1, d.age * d.REVEAL_SPEED)]
        wrapped(surface, shown, (left, rect.y + 21, text_width, 48), 11, PALETTE["white"], 12, 4)
        if has_choices:
            labels = [label for label, _ in d.choices]
            height = 12 + 15 * len(labels)
            menu(surface, (rect.right - 92, rect.bottom - height - 4, 86, height), labels, d.selected, 10, frame)
        elif d.revealed and frame % 40 < 26:
            x, y = rect.right - 12, rect.bottom - 10
            pygame.draw.polygon(surface, PALETTE["gold"], [(x, y), (x + 6, y), (x + 3, y + 4)])

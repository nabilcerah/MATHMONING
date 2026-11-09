"""NUMBER FOREST overworld: free-roaming avatar, routine NPCs and data-driven interactables.

The map, NPCs and objects come from ``data/maps/number_forest.json``. Movement is smooth
(pixel based, with collision), the avatar faces what it will interact with, and an
``[E]`` prompt says what pressing the key will do before the player commits.
"""
import math
import random

import pygame

from config import PALETTE, ROOT, VIRTUAL_WIDTH
from game.actors import FOLLOW_GAP, NPC, Avatar
from game.trial_roamers import spawn_for as spawn_trials
from game.quest_tracker import QuestTracker
from game.creatures import draw_creature
from game.sprites import frame_for
from monsters.monster_data import challenges, species
from world.encounter_manager import EncounterManager
from game.ui import heart, menu, meter, panel, text, wrap_lines, wrapped
from game.world_map import TILE, load_map, vanish_flag

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
        _clear_replaced_buildings(world, name, image)
        _backgrounds[key] = image
    return _backgrounds[key]


def _clear_replaced_buildings(world, name, image):
    """A decor building that replaces a painted house ("clear_with": a plain grass cell) first
    paints grass over the old house - otherwise the old roof shows above the new building."""
    for decor in world.data.get("decor", []):
        source = decor.get("clear_with")
        if not source:
            continue
        x0, y0, w, h = (v * TILE for v in decor["rect"])
        pad = 3                                    # the old house's outline and shadow reach a few px out
        area = pygame.Rect(x0 - pad, y0 - pad, w + 2 * pad, h + 2 * pad)
        if name == world.background:
            tile = image.subsurface((source[0] * TILE, source[1] * TILE, TILE, TILE)).copy()
            image.set_clip(area)
            for y in range(area.y, area.bottom, TILE):
                for x in range(area.x, area.right, TILE):
                    image.blit(tile, (x, y))
            image.set_clip(None)
        elif name == getattr(world, "canopy", None):
            image.fill((0, 0, 0, 0), area)


class PaintedActor:
    """Someone painted into the background art: they breathe and now and then say something."""

    def __init__(self, spec, index):
        self.rect = spec["rect"]                  # background pixels: x, y, w, h
        self.remarks = spec.get("remarks", [])
        self.phase = index * 37
        # Speech bubbles sit above the painted head (x, y are the 'feet' the bubble code expects).
        self.x = self.rect[0] + self.rect[2] / 2
        self.y = self.rect[1] + 20
        self.bubble = None
        self.timer = 200 + index * 170

    def update(self, avatar, rng):
        if self.bubble:
            message, frames = self.bubble
            self.bubble = (message, frames - 1) if frames > 1 else None
        self.timer -= 1
        if self.timer <= 0:
            self.timer = rng.randint(420, 720)
            if self.remarks and math.hypot(avatar.x - self.x, avatar.y - self.y) < 160:
                self.bubble = (rng.choice(self.remarks), 200)


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
        self.scene_for = None           # story hook: callable(event, **info) -> scene id or None
        self.npcs = [NPC(spec, self.world, self.rng) for spec in self.world.data.get("npcs", [])
                     if self._npc_visible(spec)]
        self.objects = {entry["id"]: entry for entry in self.world.data.get("interactables", [])}
        self.painted_actors = [PaintedActor(spec, i) for i, spec in enumerate(self.world.data.get("painted_actors", []))]
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
        # Monster Trials bosses that roam this map (data/trial_spawns.json).
        self.encounter_trial = None
        trial_records = repository.monster_records(player.player_id) if repository and player.player_id and             hasattr(repository, "monster_records") else {}
        self.trial_roamers = spawn_trials(self.world, trial_records, self.rng)
        self.tracker = QuestTracker(self)
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
        if hasattr(self, "npcs"):
            self._refresh_npcs()

    def _npc_visible(self, spec):
        """Story NPCs can appear or leave as the story moves on (visible_if / hidden_if flags)."""
        return all(flag in self.flags for flag in spec.get("visible_if", [])) and \
            not any(flag in self.flags for flag in spec.get("hidden_if", []))

    def _refresh_npcs(self):
        wanted = [spec for spec in self.world.data.get("npcs", []) if self._npc_visible(spec)]
        if [n.id for n in self.npcs] != [spec["id"] for spec in wanted]:
            current = {n.id: n for n in self.npcs}
            self.npcs = [current.get(spec["id"]) or NPC(spec, self.world, self.rng) for spec in wanted]

    def refresh_flags(self):
        if self.repository and self.player.player_id:
            self.flags = set(self.repository.world_flags(self.player.player_id))
            if hasattr(self.repository, "capture_records"):
                self.records = self.repository.capture_records(self.player.player_id)
        self.world.apply_flags(self.flags)
        self._refresh_npcs()

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
        """The first companion (your lead, unless it stays in its Numeris Core)."""
        followers = self.followers()
        if followers:
            return followers[0].spec
        lead = self.party.lead if self.party else None
        return lead.spec if lead else species("FRACTELLA")

    @staticmethod
    def stay_flag(monster):
        return f"stay:{monster.instance_id};"

    def followers(self):
        """Up to three party MathMon walk behind you; the Party screen (F) lets one stay in its ball."""
        party = self.party.party if self.party else []
        return [m for m in party if self.stay_flag(m) not in self.flags][:3]

    def clear_flag(self, flag):
        if flag not in self.flags:
            return
        self.flags.discard(flag)
        if self.repository and self.player.player_id:
            self.repository.clear_world_flags(self.player.player_id, flag)

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
        for painted in self.painted_actors:
            painted.update(self.avatar, self.rng)
        # The player can always walk through people (bug report: NPCs standing in narrow paths blocked the way).
        moved = self.avatar.walk(dx, dy, self.world, ())
        if (dx or dy) and not moved:
            self._explain_blocked(dx, dy)
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
        for trial in list(self.trial_roamers):
            if trial.update(self.avatar) and not self.encounter_grace and not self.dialogue:
                self.trial_roamers.remove(trial)          # it leaves after the battle until you return
                self.encounter_trial, self.encounter_trial_roamer = trial.id, trial
                return "trial"
        if moved:
            self.grass_distance += moved
            if self.grass_distance >= TILE:   # one movement step = one tile walked
                self.grass_distance = 0.0
                self.steps += 1
                if self.encounters.step(self.area_id, self.world.is_encounter(cell), bool(self.dialogue)):
                    self.encounter_spec, self.encounter_level = self.encounters.pick(self.area_id)
                    return "encounter"
        return None

    def _explain_blocked(self, dx, dy):
        """Bumping into a closed barrier says why it's closed and how to open it."""
        cx, cy = self.avatar.cell()
        ahead = (cx + (dx > 0) - (dx < 0), cy + (dy > 0) - (dy < 0))
        for barrier in self.world.barriers:
            if not barrier.get("open") and ahead in barrier["cells"] and not self.message_frames:
                self.set_message(barrier.get("blocked_text", "The way is blocked for now."), 150)

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
            gone = vanish_flag(entry)
            if gone and gone in self.flags:
                continue                     # picked up already: nothing there to interact with
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

    def _story_lines(self, npc):
        """The last 'story_lines' entry whose flags are all held: NPCs react to the story."""
        lines = None
        for entry in npc.spec.get("story_lines", []):
            if all(flag in self.flags for flag in entry.get("requires", [])):
                lines = entry["lines"]
        return lines

    def _talk(self, npc):
        """NPC dialogue comes from structured map data (GDD 10.4); quest NPCs pick their lines by quest state."""
        npc.begin_talk(self.avatar)
        first_meeting = not self.has_flag(f"met:{npc.id}")
        scene = self.scene_for("talk", npc=npc.id) if self.scene_for else None
        self.set_flag(f"met:{npc.id}")
        title, subtitle = npc.name.upper(), npc.role
        if scene:
            # A story scene takes over the conversation (shown by the game's scene screen).
            self._emit("talk", npc=npc.id)
            self.talking_to = npc
            return ("scene", scene, npc.id)
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
        elif npc.kind == "clinic":
            pages = self._npc_pages(npc, "any", ["How are your MathMon feeling today?"])
            self.open_dialogue(title, pages, subtitle, [("Use the Recovery Capsule", "clinic"),
                                                        ("Goodbye", "close")], npc, "npc")
        elif npc.kind == "sanctuary":
            pages = self._npc_pages(npc, "any", ["Welcome to the Sanctuary."])
            self.open_dialogue(title, pages, subtitle, [("Manage monsters", "sanctuary"),
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
            lines = self._story_lines(npc) or [npc.next_line() or "Hello there!"]
            self.open_dialogue(title, lines, subtitle, speaker=npc, kind="npc")
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
        if kind == "clinic":
            return "clinic"
        if kind == "record":
            needed = entry.get("requires")
            if needed and not self.has_flag(needed):
                self.open_dialogue(title, entry.get("locked_text", ["It won't open."]))
                return None
            self._emit("interact", object=object_id)
            return ("record", entry["record"])
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
        if kind == "clinic":
            return base + "  - heal with maths"
        if kind == "record":
            if target.get("requires") and not self.has_flag(target["requires"]):
                return base + "  - locked"
            return base + ("  - read" if self.has_flag(f"record:{target['record']}") else "  - historical record")
        if kind == "shrine":
            return base + ("  - solved today" if self.shrine_done(target["id"]) else "  - new puzzle!")
        if kind == "portal":
            needed = target.get("requires")
            if target.get("door"):
                return base
            if needed and not self.has_flag(needed):
                reason = self.quests.unlocked_by(needed) if self.quests else ""
                return base + (f"  - LOCKED: {reason}" if reason else "  - locked")
            return base + "  - travel"
        if kind == "arena":
            return base + "  - race AI rivals!"
        if kind == "boss_gate":
            return base + ("  - the boss awaits!" if self.boss_ready else "  - sealed")
        return base

    # ------------------------------------------------------------------ camera
    def _camera_goal(self):
        width, height = self.world.pixel_size()
        fx, fy = getattr(self, "camera_focus", None) or (self.avatar.x, self.avatar.y)   # cutscenes may pan
        gx = fx - VIRTUAL_WIDTH / 2
        gy = fy - 8 - VIEW_HEIGHT / 2
        # Rooms smaller than the screen (shop, clinic) sit in the middle instead of the top-left corner.
        gx = (width - VIRTUAL_WIDTH) / 2 if width <= VIRTUAL_WIDTH else max(0, min(width - VIRTUAL_WIDTH, gx))
        gy = (height - VIEW_HEIGHT) / 2 if height <= VIEW_HEIGHT else max(0, min(height - VIEW_HEIGHT, gy))
        return gx, gy

    def _camera_follow(self):
        gx, gy = self._camera_goal()
        self.cam_x += (gx - self.cam_x) * 0.14
        self.cam_y += (gy - self.cam_y) * 0.14
        if abs(gx - self.cam_x) < 0.3:
            self.cam_x = gx
        if abs(gy - self.cam_y) < 0.3:
            self.cam_y = gy

    def camera_settled(self):
        gx, gy = self._camera_goal()
        return abs(gx - self.cam_x) < 1 and abs(gy - self.cam_y) < 1

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
            # Negative camera values centre a small room: shift the destination instead of the source.
            dest = (max(0, -cam_x), VIEW_TOP + max(0, -cam_y))
            surface.blit(painted_background(self.world), dest, (max(0, cam_x), max(0, cam_y), VIRTUAL_WIDTH, VIEW_HEIGHT))
            self._draw_decor(surface)
        for my in range(first_y, first_y + VIEW_HEIGHT // TILE + 2):
            for mx in range(first_x, first_x + VIRTUAL_WIDTH // TILE + 2):
                sx, sy = mx * TILE - cam_x, my * TILE - cam_y + VIEW_TOP
                rustle = (mx, my) == player_cell and self.avatar.moving
                if painted:
                    self._draw_painted_extra(surface, sx, sy, mx, my, frame, rustle)
                else:
                    self._draw_tile(surface, sx, sy, mx, my, frame, rustle)

        self._draw_painted_actors(surface, frame)
        # Depth-sorted entities: objects, NPCs, companion and avatar.
        drawables = []
        for entry in self.objects.values():
            drawables.append(((entry["pos"][1] + 1) * TILE - 1, "object", entry))
        for npc in self.npcs:
            drawables.append((npc.y, "npc", npc))
        for roamer in self.roamers:
            drawables.append((roamer.y, "roamer", roamer))
        for trial in self.trial_roamers:
            drawables.append((trial.y, "trial", trial))
        for index, capsule in enumerate(self.world.data.get("capsules", [])):
            drawables.append(((capsule["pos"][1] + 1) * TILE - 1, "capsule", (index, capsule)))
        for place, monster in enumerate(self.followers()):
            fx, fy, ffacing = self.avatar.follower_spot(FOLLOW_GAP * (place + 1))
            drawables.append((fy - 0.5, "companion", (fx, fy, ffacing, monster.spec)))
        drawables.append((self.avatar.y, "avatar", self.avatar))
        for _, kind, item in sorted(drawables, key=lambda d: d[0]):
            if kind == "object":
                self._draw_object(surface, item, frame)
                if self.quest_locked(item):
                    lx, ly = self.to_screen(item["pos"][0] * TILE + TILE / 2, item["pos"][1] * TILE)
                    self._draw_padlock(surface, lx, ly - 14, frame)
            elif kind == "roamer":
                self._draw_roamer(surface, item, frame)
            elif kind == "capsule":
                self._draw_capsule(surface, *item, frame)
            elif kind == "trial":
                item.draw_cave(surface, self.to_screen)
                if item.visible_from(self.avatar):
                    item.draw(surface, self.to_screen(item.x, item.y), frame, f"trial_seen:{item.id}" in self.flags)
            elif kind == "companion":
                self._draw_companion(surface, *item, frame)
            else:
                self._draw_actor(surface, item)

        if painted and self.world.canopy:
            # Tree tops in front of anyone standing just north of the forest edge.
            canopy = painted_background(self.world, self.world.canopy, alpha=True)
            surface.blit(canopy, (max(0, -cam_x), VIEW_TOP + max(0, -cam_y)),
                         (max(0, cam_x), max(0, cam_y), VIRTUAL_WIDTH, VIEW_HEIGHT))
        self._draw_barriers(surface, frame)
        self._draw_markers(surface, frame)
        if self.target is not None:
            self._draw_target(surface, frame)
        for npc in self.npcs:
            if npc.bubble:
                self._draw_bubble(surface, npc)
        for painted in self.painted_actors:
            if painted.bubble:
                self._draw_bubble(surface, painted)
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
            if done:
                self._blessing(surface, x + 8, y + 7, (240, 150, 230) if crystal else (120, 230, 240), frame,
                               index=object_id)
        elif kind == "record":
            read = self.has_flag(f"record:{entry['record']}")
            pygame.draw.ellipse(surface, shadow, (x + 1, y + 11, 14, 5))
            pygame.draw.rect(surface, (120, 104, 84), (x + 3, y + 1, 10, 13))
            pygame.draw.rect(surface, (170, 150, 120), (x + 4, y + 2, 8, 11))
            glow = (120, 100, 70) if read else ((242, 187, 82) if (frame // 20) % 2 else (200, 160, 90))
            for row in range(3):
                pygame.draw.line(surface, glow, (x + 5, y + 4 + row * 3), (x + 10, y + 4 + row * 3))
        elif kind == "clinic":
            pulse = (frame // 8) % 6
            pygame.draw.ellipse(surface, shadow, (x - 1, y + 11, 18, 5))
            pygame.draw.rect(surface, (60, 64, 76), (x + 1, y + 9, 14, 6))
            pygame.draw.rect(surface, (40, 44, 56), (x + 3, y - 10, 10, 20))
            pygame.draw.rect(surface, (110, 230, 150), (x + 4, y - 9 + pulse // 2, 8, 17 - pulse // 2))
            pygame.draw.rect(surface, (200, 255, 210), (x + 5, y - 8, 2, 14))
            pygame.draw.rect(surface, (235, 112, 92), (x + 6, y - 15, 4, 4))
            pygame.draw.rect(surface, PALETTE["white"], (x + 7, y - 14, 2, 2))
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
            if done:
                # Solved: the shrine is blessed - calm light, a floating crystal and spirit motes.
                self._blessing(surface, x + 8, y + 8, rune, frame, index=object_id)
                pygame.draw.rect(surface, rune, (x + 6, y + 4, 4, 5))
                pygame.draw.rect(surface, PALETTE["white"], (x + 7, y + 5, 2, 2))
            else:
                pulse = (frame // 12) % 2
                pygame.draw.rect(surface, rune, (x + 6, y + 4 - pulse, 4, 5))
                if frame % 50 < 6:
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

    def quest_locked(self, entry):
        """Is this object shut until a quest is done (a portal, a sealed boss gate, a locked record)?"""
        kind = entry.get("kind")
        if kind == "boss_gate":
            gate_flag = entry.get("flag")
            seals = entry.get("seals", [])
            return not self.has_flag(gate_flag) and not all(self.has_flag(s) for s in seals)
        needed = entry.get("requires")
        return bool(needed) and kind in ("portal", "record") and not self.has_flag(needed)

    def _draw_padlock(self, surface, cx, top, frame):
        """A floating padlock: this way is locked by a quest."""
        bob = 1 if frame % 50 < 25 else 0
        y = top - bob
        pygame.draw.rect(surface, PALETTE["ink"], (cx - 5, y - 1, 11, 10))
        pygame.draw.rect(surface, PALETTE["gold"], (cx - 4, y, 9, 8))
        pygame.draw.rect(surface, PALETTE["ink"], (cx - 3, y - 6, 7, 7), 1)
        pygame.draw.rect(surface, PALETTE["gold"], (cx - 2, y - 5, 5, 5), 1)
        pygame.draw.rect(surface, PALETTE["ink"], (cx, y + 3, 1, 3))

    def _blessing(self, surface, cx, cy, color, frame, index=""):
        """The living glow of a solved shrine or seal: a soft light pool, a breathing halo, spirit
        motes orbiting and rising, a tiny floating crystal and the odd twinkle."""
        seed = sum(map(ord, str(index))) % 97
        t = (frame + seed * 7) / 60
        breath = 0.5 + 0.5 * math.sin(t * 1.6)
        glow = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*color, int(40 + 35 * breath)), (4, 22, 32, 12))         # light pool
        pygame.draw.circle(glow, (*color, int(30 + 30 * breath)), (20, 20), int(11 + 3 * breath), 1)  # halo
        surface.blit(glow, (cx - 20, cy - 16))
        for i in range(4):                                                                 # orbiting motes
            angle = t * 1.3 + i * math.pi / 2
            mx = cx + int(math.cos(angle) * 11)
            my = cy - 4 + int(math.sin(angle) * 4) - int(((t * 12 + i * 9) % 18))
            pygame.draw.rect(surface, color if i % 2 else PALETTE["white"], (mx, my, 1 + i % 2, 1 + i % 2))
        bob = int(2 * math.sin(t * 2.2))                                                   # floating crystal
        top = cy - 20 + bob
        pygame.draw.polygon(surface, color, [(cx, top), (cx + 3, top + 4), (cx, top + 8), (cx - 3, top + 4)])
        pygame.draw.line(surface, PALETTE["white"], (cx, top + 1), (cx + 1, top + 4))
        if (frame + seed * 13) % 140 < 10:                                                 # twinkle
            sx, sy = cx + 7, top - 2
            pygame.draw.line(surface, PALETTE["white"], (sx - 2, sy), (sx + 2, sy))
            pygame.draw.line(surface, PALETTE["white"], (sx, sy - 2), (sx, sy + 2))

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
            elif getattr(actor, "state", "") == "working" and getattr(actor, "spec", {}).get("task_poses"):
                # Busy at their spot: the fisherman casts and catches, Nurse Hana checks capsules...
                poses = actor.spec["task_poses"]
                pose = poses[(self.age // 45 + len(actor.id)) % len(poses)]
            else:
                pose = 0
            monster_sprites.draw(surface, actor.sheet, (sx, sy + 1), self.CHARACTER_HEIGHT, pose,
                                 flip=actor.facing == (-1, 0))
            return
        image = frame_for(actor.frames, actor.facing, actor.walk_time, actor.moving)
        bob = 1 if actor.moving and int(actor.walk_time * 8) % 2 else 0
        surface.blit(image, (sx - 8, sy - 15 - bob))

    def _draw_companion(self, surface, x, y, facing, spec, frame):
        sx, sy = self.to_screen(x, y)
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
                    (kind == "record" and not self.has_flag(f"record:{entry['record']}")) or \
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

    def _draw_capsule(self, surface, index, capsule, frame):
        """A wall recovery capsule with a resting MathMon (the same art as the Recovery Center screen)."""
        from types import SimpleNamespace
        from states.clinic_state import draw_capsule
        cache = self.__dict__.setdefault("_capsule_art", {})
        stage = 3 + int(5 * (0.5 + 0.5 * math.sin(frame / 120 + index * 2)))
        key = (index, stage, frame // 4 % 30)
        if key not in cache:
            if len(cache) > 300:
                cache.clear()
            big = pygame.Surface((92, 136), pygame.SRCALPHA)
            patient = SimpleNamespace(spec=species(capsule["species"]), fainted=False)
            draw_capsule(big, (0, 0, 92, 136), patient, stage, frame // 4 * 4)
            cache[key] = pygame.transform.smoothscale(big, (20, 30))
        x, y = capsule["pos"]
        sx, sy = self.to_screen(x * TILE + TILE / 2, (y + 1) * TILE)
        surface.blit(cache[key], (sx - 10, sy - 30))

    def _draw_painted_actors(self, surface, frame):
        """People painted into an interior (the nurse, the receptionist) breathe: their part of the
        painting lifts by a pixel now and then, so the room never looks like a still photo."""
        if not self.painted_actors:
            return
        background = painted_background(self.world)
        scale = self.world.background_scale
        for index, painted in enumerate(self.painted_actors):
            if (frame + painted.phase) % 100 >= 50:
                continue
            x, y, w, h = (v * scale for v in painted.rect)
            sx, sy = self.to_screen(x, y)
            surface.blit(background, (sx, sy - 1), (x, y, w, h))

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
        local = {npc.id for npc in self.npcs} | set(self.objects)
        mains = [q for q in self.quests.active() if self.quests.definition(q)["category"] == "main"]
        mains.sort(key=lambda q: self.quests.definition(q).get("giver") not in local)   # this world's story first
        for quest_id in mains:
            return "QUEST: " + self.quests.step_text(quest_id)
        upcoming = self.tracker.next_destination() if hasattr(self, "tracker") else None
        if upcoming:
            return "NEXT: " + upcoming[1]
        active = self.quests.active()
        return ("QUEST: " + self.quests.step_text(active[0])) if active else ""

    def _draw_decor(self, surface):
        """Building art painted over the map (the Mathmart and Recovery Center exteriors)."""
        for decor in self.world.data.get("decor", []):
            image = painted_background(self.world, decor["image"], alpha=True)
            x0, y0, w, h = decor["rect"]
            bottom_x, bottom_y = self.to_screen((x0 + w / 2) * TILE, (y0 + h) * TILE)
            surface.blit(image, (round(bottom_x - image.get_width() / 2), bottom_y - image.get_height()))

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
        if getattr(self, "cinematic", False):
            return          # cutscenes hide the HUD (states/cutscene.py draws letterbox bars instead)
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
            hint = self.quest_hint() if self.quests and not self.tracker.visible else ""
            text(surface, hint or "J: show / hide quests   Tall grass hides wild MATHMON.", (160, bottom + 18), 8,
                 PALETTE["muted"], center=True)

        if self.quests and not self.dialogue and not self.world.interior:
            self.tracker.draw(surface, frame)
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

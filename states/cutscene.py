"""Cutscenes: characters walk, react and the camera moves before (or between) dialogue lines.

A scene in data/story/scenes.json may have a ``"cutscene"`` list that plays before its first line,
and any dialogue line may have a ``"cut"`` list that plays before that line appears. Each step:

    {"do": "walk",   "who": "rowan", "to": "player"}       walk next to the player (pathfinding)
    {"do": "walk",   "who": "player", "to": [16, 58]}       ...or to a map cell / a waypoint name
    {"do": "face",   "who": "player", "to": "rowan"}        turn toward someone (or up/down/left/right)
    {"do": "emote",  "who": "rowan", "emote": "!"}          a pop-up bubble: ! ? ... ♪ heart sweat
    {"do": "camera", "to": "door_lab"}                      pan to an object, character, cell or "player"
    {"do": "wait",   "t": 0.5}                              pause (seconds)
    {"do": "fade",   "to": "black" | "clear"}               fade the screen out / back in
    {"do": "shake",  "t": 0.6}                              shake the screen
    {"do": "flash"}                                         a white flash
    {"do": "place",  "who": "rowan", "at": "village_north"} put someone somewhere (no walking)

Steps that name someone who is not on the current map are skipped, so a scene never gets stuck.
Pressing ENTER / ESC skips the rest of a cutscene: walkers jump to where they were going.
"""
import math

import pygame

from config import PALETTE, VIRTUAL_HEIGHT, VIRTUAL_WIDTH
from game.actors import DIRECTIONS, cardinal

WALK_SPEED = 1.0          # pixels per frame
WALK_TIMEOUT = 8 * 60     # frames before a stuck walker is placed at its goal
BAR_HEIGHT = 18
EMOTE_FRAMES = 50
FADE_FRAMES = 20
EMOTES = ("!", "?", "...", "♪", "heart", "sweat")


class Cutscene:
    def __init__(self, world, steps):
        self.world = world
        self.steps = list(steps or [])
        self.step = None
        self.timer = 0
        self.frames = 0
        self.emotes = []               # [actor, emote, frames_left]
        self.fade = 0.0                # 0 clear .. 1 black
        self.fade_goal = 0.0
        self.shake = 0
        self.flash = 0
        self.walkers = []              # [actor, path(cells), goal_cell, frames]
        self.finished = not self.steps
        self.bars = 0.0
        self.follow = None             # the walker the camera tracks
        world.cinematic = True
        world.message_frames = 0       # clear any leftover world message box
        self._start_next()

    # ------------------------------------------------------------------ lookup
    def actor(self, who):
        if who in (None, "player"):
            return self.world.avatar
        return next((npc for npc in self.world.npcs if npc.id == who), None)

    def _point(self, target):
        """World pixel position (feet) for a character id, object id, waypoint name or [x, y] cell."""
        if target in (None, "player"):
            return self.world.avatar.x, self.world.avatar.y
        if isinstance(target, (list, tuple)):
            return self.world.world.cell_to_feet(tuple(target))
        actor = self.actor(target)
        if actor is not None:
            return actor.x, actor.y
        entry = self.world.objects.get(target) if hasattr(self.world, "objects") else None
        if entry and "pos" in entry:
            return self.world.world.cell_to_feet(tuple(entry["pos"]))
        cell = self.world.world.waypoints.get(target)
        if cell:
            return self.world.world.cell_to_feet(tuple(cell))
        return None

    def _goal_cell(self, actor, target):
        world = self.world.world
        if target == "player" or (isinstance(target, str) and self.actor(target) is not None
                                  and self.actor(target) is not actor):
            other = self.actor(target)
            ox, oy = other.cell()
            ax, ay = actor.cell()
            # Stand on the side of the other character that faces where we came from.
            sides = sorted(((0, 1), (0, -1), (1, 0), (-1, 0)),
                           key=lambda d: math.hypot(ox + d[0] - ax, oy + d[1] - ay))
            for dx, dy in sides:
                if world.is_walkable((ox + dx, oy + dy)):
                    return ox + dx, oy + dy
            return world.nearest_walkable((ox, oy + 1))
        point = self._point(target)
        if point is None:
            return None
        return world.nearest_walkable((int(point[0] // 16), int((point[1] - 2) // 16)))

    # ------------------------------------------------------------------ steps
    def _start_next(self):
        while self.steps:
            self.step = self.steps.pop(0)
            self.timer = 0
            if self._begin(self.step):
                return
        self.step = None
        if not self.walkers:
            self.finished = True

    def _begin(self, step):
        """Start a step. Returns True if it takes time (the director waits for it)."""
        kind = step.get("do")
        if kind == "walk":
            actor = self.actor(step.get("who"))
            if actor is None:
                return False
            goal = self._goal_cell(actor, step.get("to", "player"))
            if goal is None:
                return False
            start = self.world.world.nearest_walkable(actor.cell())
            path = self.world.world.find_path(start, goal) or [goal]
            if hasattr(actor, "state"):
                actor.state, actor.path = "cutscene", []
            self.walkers = [w for w in self.walkers if w[0] is not actor] + [[actor, list(path), goal, 0]]
            if actor is not self.world.avatar and step.get("follow", True):
                self.follow = actor
            return not step.get("async", False)
        if kind == "place":
            actor = self.actor(step.get("who"))
            point = self._point(step.get("at"))
            if actor is not None and point is not None:
                cell = self.world.world.nearest_walkable((int(point[0] // 16), int((point[1] - 2) // 16)))
                actor.x, actor.y = self.world.world.cell_to_feet(cell)
                if hasattr(actor, "state"):
                    actor.state, actor.path = "cutscene", []
            return False
        if kind == "face":
            actor = self.actor(step.get("who"))
            if actor is not None:
                target = step.get("to")
                if target in DIRECTIONS:
                    actor.facing = DIRECTIONS[target]
                else:
                    point = self._point(target)
                    if point:
                        actor.facing = cardinal(point[0] - actor.x, point[1] - actor.y)
            return False
        if kind == "emote":
            actor = self.actor(step.get("who"))
            if actor is not None:
                self.emotes = [e for e in self.emotes if e[0] is not actor]
                self.emotes.append([actor, step.get("emote", "!"), EMOTE_FRAMES])
                return step.get("wait", True)
            return False
        if kind == "camera":
            target = step.get("to", "player")
            self.follow = None
            self.world.camera_focus = None if target == "player" else self._point(target)
            return True
        if kind == "wait":
            return True
        if kind == "fade":
            self.fade_goal = 1.0 if step.get("to", "black") == "black" else 0.0
            return True
        if kind == "shake":
            self.shake = int(float(step.get("t", 0.6)) * 60)
            return False
        if kind == "flash":
            self.flash = 12
            return False
        return False

    def _step_done(self):
        step, kind = self.step, self.step.get("do")
        if kind == "walk":
            actor = self.actor(step.get("who"))
            return actor is None or all(w[0] is not actor for w in self.walkers)
        if kind == "emote":
            return self.timer >= EMOTE_FRAMES - 10
        if kind == "camera":
            return self.world.camera_settled() or self.timer > 90
        if kind == "wait":
            return self.timer >= int(float(step.get("t", 0.5)) * 60)
        if kind == "fade":
            return abs(self.fade - self.fade_goal) < 0.01
        return True

    # ------------------------------------------------------------------ frame
    def update(self):
        self.frames += 1
        self.bars = min(1.0, self.bars + 0.1)
        self._move_walkers()
        for emote in self.emotes:
            emote[2] -= 1
        self.emotes = [e for e in self.emotes if e[2] > 0]
        if self.fade != self.fade_goal:
            delta = 1 / FADE_FRAMES
            self.fade = min(self.fade_goal, self.fade + delta) if self.fade < self.fade_goal \
                else max(self.fade_goal, self.fade - delta)
        self.shake = max(0, self.shake - 1)
        self.flash = max(0, self.flash - 1)
        self._track()
        self.world._camera_follow()
        if self.step is not None:
            self.timer += 1
            if self._step_done():
                self._start_next()
        elif not self.walkers:
            self.finished = True

    def _track(self):
        """Keep a walking character on screen: follow them, then frame them with the player."""
        actor, avatar = self.follow, self.world.avatar
        if actor is None:
            return
        if math.hypot(actor.x - avatar.x, actor.y - avatar.y) > 110:
            self.world.camera_focus = (actor.x, actor.y)
        else:
            self.world.camera_focus = ((actor.x + avatar.x) / 2, (actor.y + avatar.y) / 2)

    def _move_walkers(self):
        world = self.world.world
        for walker in list(self.walkers):
            actor, path, goal, frames = walker
            walker[3] += 1
            if not path or walker[3] > WALK_TIMEOUT:
                self._arrive(walker)
                continue
            tx, ty = world.cell_to_feet(path[0])
            dx, dy = tx - actor.x, ty - actor.y
            distance = math.hypot(dx, dy)
            actor.moving = True
            actor.walk_time += 1 / 60
            if distance <= WALK_SPEED:
                actor.x, actor.y = tx, ty
                path.pop(0)
                if not path:
                    self._arrive(walker)
                continue
            actor.facing = cardinal(dx, dy)
            actor.x += dx / distance * WALK_SPEED
            actor.y += dy / distance * WALK_SPEED
            if actor is self.world.avatar:
                actor.trail.append((actor.x, actor.y, actor.facing))

    def _arrive(self, walker):
        actor, _, goal, _ = walker
        actor.x, actor.y = self.world.world.cell_to_feet(goal)
        actor.moving, actor.walk_time = False, 0.0
        self.walkers.remove(walker)
        if actor is not self.world.avatar:
            actor.face_toward(self.world.avatar.x, self.world.avatar.y)

    def skip(self):
        """Jump to the end: walkers arrive, the camera returns, the screen clears."""
        for walker in list(self.walkers):
            self._arrive(walker)
        for step in ([self.step] if self.step else []) + self.steps:
            if step.get("do") == "walk":
                actor = self.actor(step.get("who"))
                goal = self._goal_cell(actor, step.get("to", "player")) if actor else None
                if goal:
                    actor.x, actor.y = self.world.world.cell_to_feet(goal)
            elif step.get("do") == "face":
                self._begin(step)
            elif step.get("do") == "camera":
                target = step.get("to", "player")
                self.world.camera_focus = None if target == "player" else self._point(target)
        self.steps, self.step = [], None
        self.fade = self.fade_goal = 0.0
        self.emotes, self.shake, self.flash = [], 0, 0
        self.finished = True

    def release(self):
        """Give the characters back to the world once the scene is over."""
        self.world.camera_focus = None
        self.world.cinematic = False
        self.follow = None
        for npc in self.world.npcs:
            if getattr(npc, "state", "") == "cutscene":
                npc.state, npc.wait = "working", 240
                npc.face_toward(self.world.avatar.x, self.world.avatar.y)

    # ------------------------------------------------------------------ drawing
    def offset(self):
        if not self.shake:
            return 0, 0
        return (self.shake % 4) - 2, ((self.shake // 2) % 3) - 1

    def draw(self, surface, frame, bars=True):
        for actor, emote, left in self.emotes:
            self._draw_emote(surface, actor, emote, left)
        if self.fade > 0:
            shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            shade.fill((*PALETTE["ink"], int(255 * self.fade)))
            surface.blit(shade, (0, 0))
        if self.flash:
            glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            glow.fill((255, 255, 255, int(255 * self.flash / 12)))
            surface.blit(glow, (0, 0))
        if bars:
            draw_bars(surface, self.bars)

    def _draw_emote(self, surface, actor, emote, left):
        sx, sy = self.world.to_screen(actor.x, actor.y)
        rise = min(4, (EMOTE_FRAMES - left))
        x, y = sx, sy - 38 - rise
        pop = 1.0 if EMOTE_FRAMES - left > 4 else (EMOTE_FRAMES - left) / 4
        w, h = int(16 * pop) or 1, int(13 * pop) or 1
        bubble = pygame.Rect(0, 0, w, h)
        bubble.center = (x, y)
        pygame.draw.rect(surface, PALETTE["white"], bubble, border_radius=3)
        pygame.draw.rect(surface, PALETTE["ink"], bubble, 1, border_radius=3)
        pygame.draw.polygon(surface, PALETTE["white"], [(x - 2, bubble.bottom - 1), (x + 2, bubble.bottom - 1),
                                                         (x, bubble.bottom + 3)])
        if pop < 1:
            return
        red, ink, pink, blue = (220, 50, 50), PALETTE["ink"], (230, 80, 120), (90, 160, 230)
        if emote == "!":
            pygame.draw.rect(surface, red, (x - 1, y - 4, 3, 5))
            pygame.draw.rect(surface, red, (x - 1, y + 2, 3, 2))
        elif emote == "?":
            pygame.draw.lines(surface, ink, False, [(x - 2, y - 2), (x - 1, y - 4), (x + 2, y - 4), (x + 2, y - 1),
                                                    (x, y), (x, y + 1)], 2)
            pygame.draw.rect(surface, ink, (x - 1, y + 3, 2, 2))
        elif emote == "...":
            for i in (-4, 0, 4):
                if (EMOTE_FRAMES - left) // 8 >= (i + 4) // 4:
                    pygame.draw.rect(surface, ink, (x + i - 1, y, 2, 2))
        elif emote == "♪":
            pygame.draw.circle(surface, blue, (x - 1, y + 2), 2)
            pygame.draw.line(surface, blue, (x + 1, y + 2), (x + 1, y - 4), 1)
            pygame.draw.line(surface, blue, (x + 1, y - 4), (x + 4, y - 2), 2)
        elif emote == "heart":
            pygame.draw.circle(surface, pink, (x - 2, y - 1), 2)
            pygame.draw.circle(surface, pink, (x + 2, y - 1), 2)
            pygame.draw.polygon(surface, pink, [(x - 4, y), (x + 4, y), (x, y + 4)])
        elif emote == "sweat":
            pygame.draw.circle(surface, blue, (x + 1, y + 1), 2)
            pygame.draw.polygon(surface, blue, [(x - 1, y + 1), (x + 3, y + 1), (x + 1, y - 4)])


def draw_bars(surface, amount):
    """Cinematic black bars sliding in from the top and bottom."""
    height = int(BAR_HEIGHT * max(0.0, min(1.0, amount)))
    if height:
        pygame.draw.rect(surface, (0, 0, 0), (0, 0, VIRTUAL_WIDTH, height))
        pygame.draw.rect(surface, (0, 0, 0), (0, VIRTUAL_HEIGHT - height, VIRTUAL_WIDTH, height))

"""Overworld actors: the player's avatar, routine-driven NPCs and the companion follower."""
import math
from collections import deque

from game.sprites import PLAYER_LOOK, character_frames
from game.world_map import TILE

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def cardinal(dx, dy):
    if abs(dx) > abs(dy):
        return (1, 0) if dx > 0 else (-1, 0)
    return (0, 1) if dy > 0 else (0, -1)


class Actor:
    """A character standing at a feet position (x, y) in world pixels."""
    HALF_W, HEIGHT = 5, 6

    def __init__(self, x, y, look=None, sheet=None):
        self.x, self.y = float(x), float(y)
        self.facing = (0, 1)
        self.walk_time = 0.0
        self.moving = False
        self.frames = character_frames(look)
        self.sheet = sheet  # e.g. "characters/ALEX": drawn from processed sprite art when present

    def box(self, x=None, y=None):
        x = self.x if x is None else x
        y = self.y if y is None else y
        return x - self.HALF_W, y - self.HEIGHT + 1, x + self.HALF_W, y + 1

    def cell(self):
        return int(self.x // TILE), int((self.y - 2) // TILE)

    def center(self):
        return self.x, self.y - 7

    def face_toward(self, x, y):
        dx, dy = x - self.x, y - self.y
        if abs(dx) + abs(dy) > 1:
            self.facing = cardinal(dx, dy)


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class Avatar(Actor):
    SPEED = 1.15  # pixels per frame at 60 FPS

    def __init__(self, x, y):
        super().__init__(x, y, PLAYER_LOOK)
        self.trail = deque(maxlen=40)
        self.reset_trail()

    def reset_trail(self):
        """Put the companion one step behind the avatar (used on spawn and after long jumps)."""
        fx, fy = self.facing
        spot = (self.x - fx * 14, self.y - fy * 10 if fy else self.y)
        self.trail.clear()
        for _ in range(self.trail.maxlen):
            self.trail.append((spot[0], spot[1], self.facing))

    def walk(self, dx, dy, world, others=()):
        """Move with axis-separated collision and gentle corner sliding. Returns distance moved."""
        if dx == 0 and dy == 0:
            self.moving = False
            self.walk_time = 0.0
            return 0.0
        if dx and dy:
            # Keep the current facing on diagonals when it still applies, so the sprite does not flicker.
            if self.facing not in ((dx, 0), (0, dy)):
                self.facing = (dx, 0)
        else:
            self.facing = (dx, 0) if dx else (0, dy)
        length = math.hypot(dx, dy)
        step_x, step_y = dx / length * self.SPEED, dy / length * self.SPEED
        start = (self.x, self.y)
        self._try_axis(step_x, 0, world, others)
        self._try_axis(0, step_y, world, others)
        moved = math.hypot(self.x - start[0], self.y - start[1])
        self.moving = moved > 0.01
        self.walk_time = self.walk_time + 1 / 60 if self.moving else 0.0
        if self.moving:
            self.trail.append((self.x, self.y, self.facing))
        return moved

    def _free(self, x, y, world, others):
        box = self.box(x, y)
        if world.box_blocked(*box):
            return False
        return not any(_overlaps(box, other.box()) for other in others)

    def _try_axis(self, sx, sy, world, others):
        if sx == 0 and sy == 0:
            return
        nx, ny = self.x + sx, self.y + sy
        if self._free(nx, ny, world, others):
            self.x, self.y = nx, ny
            return
        # Corner assist: slide around a tile edge when only a few pixels overlap.
        for nudge in (1, 2, 3, 4, 5, 6):
            for sign in (1, -1):
                ox, oy = (0, sign * nudge) if sx else (sign * nudge, 0)
                if self._free(nx + ox, ny + oy, world, others) and self._free(self.x + ox, self.y + oy, world, others):
                    self.x += (0 if sx else sign * min(1, nudge))
                    self.y += (sign * min(1, nudge) if sx else 0)
                    return

    def probe(self):
        cx, cy = self.center()
        return cx + self.facing[0] * 12, cy + self.facing[1] * 12 + (3 if self.facing[1] > 0 else 0)

    def follower_spot(self, lag=14):
        return self.trail[-lag] if len(self.trail) >= lag else self.trail[0]


class NPC(Actor):
    SPEED = 0.55

    def __init__(self, spec, world, rng):
        self.spec = spec
        self.id = spec["id"]
        self.name = spec.get("name", self.id)
        self.role = spec.get("role", "")
        self.kind = spec.get("kind", "talker")
        self.world = world
        self.rng = rng
        self.routine = spec.get("routine", [])
        self.routine_index = 0
        start = world.waypoints.get(self.routine[0]["waypoint"], world.spawn) if self.routine else world.spawn
        super().__init__(*world.cell_to_feet(start), spec.get("look"), spec.get("sheet"))
        self.state = "working"
        self.wait = 0
        self.path = []
        self.bubble = None  # (text, frames_left)
        self.remark_timer = rng.randint(240, 480)
        self.line_index = 0
        self._arrive()

    # ------------------------------------------------------------- behaviour
    def _arrive(self):
        step = self.routine[self.routine_index] if self.routine else {}
        self.state = "working"
        self.moving = False
        self.wait = int(float(step.get("wait", 5)) * 60)
        if step.get("face") in DIRECTIONS:
            self.facing = DIRECTIONS[step["face"]]

    def _advance(self):
        if not self.routine:
            self.wait = 300
            return
        self.routine_index = (self.routine_index + 1) % len(self.routine)
        goal = self.world.waypoints.get(self.routine[self.routine_index]["waypoint"])
        start = self.world.nearest_walkable(self.cell())
        self.path = self.world.find_path(start, goal) if goal else []
        self.state = "walking" if self.path else "working"
        if not self.path:
            self._arrive()

    def update(self, player):
        if self.bubble:
            text, frames = self.bubble
            self.bubble = (text, frames - 1) if frames > 1 else None
        if self.state == "talking":
            self.face_toward(player.x, player.y)
            self.moving = False
            return
        if self.state == "working":
            self.moving = False
            self.wait -= 1
            if self.wait <= 0:
                self._advance()
        elif self.state == "walking":
            self._follow_path(player)
        self.walk_time = self.walk_time + 1 / 60 if self.moving else 0.0
        self.remark_timer -= 1
        if self.remark_timer <= 0:
            self.remark_timer = self.rng.randint(360, 600)
            remarks = self.spec.get("remarks", [])
            if remarks and math.hypot(player.x - self.x, player.y - self.y) < 72 and not self.bubble:
                self.say(self.rng.choice(remarks))

    def _follow_path(self, player):
        if not self.path:
            self._arrive()
            return
        tx, ty = self.world.cell_to_feet(self.path[0])
        dx, dy = tx - self.x, ty - self.y
        distance = math.hypot(dx, dy)
        if distance <= self.SPEED:
            self.x, self.y = tx, ty
            self.path.pop(0)
            if not self.path:
                self._arrive()
            return
        nx, ny = self.x + dx / distance * self.SPEED, self.y + dy / distance * self.SPEED
        self.facing = cardinal(dx, dy)
        if _overlaps(self.box(nx, ny), player.box()):
            # Politely wait for the player to step aside.
            self.moving = False
            return
        self.x, self.y = nx, ny
        self.moving = True

    def say(self, text, seconds=3.0):
        self.bubble = (str(text), int(seconds * 60))

    def begin_talk(self, player):
        self.saved_state = self.state
        self.state = "talking"
        self.bubble = None
        self.face_toward(player.x, player.y)

    def end_talk(self):
        if self.state != "talking":
            return
        if getattr(self, "saved_state", "working") == "walking" and self.path:
            self.state = "walking"
        else:
            self.state = "working"
            self.wait = max(self.wait, 120)

    def next_line(self):
        lines = self.spec.get("lines", [])
        if not lines:
            return ""
        line = lines[self.line_index % len(lines)]
        self.line_index += 1
        return line

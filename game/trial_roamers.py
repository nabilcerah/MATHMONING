"""Monster Trials creatures hiding in the world (data/trial_spawns.json).

The Trials page is only a catalogue: a Trial monster is fought by FINDING it. Each one hides in
the most remote nook of its area - the dead end furthest (by walking) from where you arrive -
inside a small rocky cave. The cave can be spotted from afar; the monster itself only shows when
you come close. Walking into it starts the advanced battle; afterwards it is gone until you
return. The story Trials (the stone arch, the guardian, the Time Spire) are fought at their gates.
"""
from collections import deque
import json
import math

import pygame

from battle_engine.monster_data import load_all
from battle_engine.progression import is_unlocked
from config import PALETTE, ROOT
from game.animation import SpriteAnimator
from game.ui import text


def spawns():
    data = json.loads((ROOT / "data" / "trial_spawns.json").read_text(encoding="utf-8"))
    return data["spawns"]


def gates():
    data = json.loads((ROOT / "data" / "trial_spawns.json").read_text(encoding="utf-8"))
    return data.get("gates", {})


def home_of(monster_id):
    """(map id, area id) where a Trial monster hides (area None for a story gate boss), or None."""
    spec = spawns().get(monster_id)
    if spec:
        return spec["map"], spec["area"]
    gate_map = gates().get(monster_id)
    return (gate_map, None) if gate_map else None


def walking_distances(world_map):
    """Steps from the arrival point to every reachable cell (breadth-first)."""
    start = world_map.nearest_walkable(world_map.spawn)
    seen, queue = {start: 0}, deque([start])
    while queue:
        x, y = queue.popleft()
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nxt not in seen and world_map.is_walkable(nxt):
                seen[nxt] = seen[(x, y)] + 1
                queue.append(nxt)
    return seen


class TrialRoamer:
    SPEED = 0.25
    TOUCH_RANGE = 12
    NOTICE_RANGE = 70
    SHOW_RANGE = 7 * 16          # the monster only shows within ~7 tiles: it must be found

    def __init__(self, defn, cells, world, rng):
        self.defn, self.id, self.world, self.rng = defn, defn.id, world, rng
        self.cells = cells
        self.home = cells[0]
        self.x, self.y = world.cell_to_feet(self.home)
        self.target, self.wait = None, rng.randint(30, 120)
        self.facing, self.moving, self.alert, self.age = 1, False, 0, rng.randint(0, 300)
        self.animator = SpriteAnimator(defn.sprite)

    def update(self, avatar):
        self.age += 1
        distance = math.hypot(avatar.x - self.x, avatar.y - self.y)
        self.alert = max(0, self.alert - 1)
        if distance < self.NOTICE_RANGE:
            self.alert = 30
            self.facing = 1 if avatar.x > self.x else -1
        if self.target:
            tx, ty = self.target
            dx, dy = tx - self.x, ty - self.y
            step = math.hypot(dx, dy)
            if step <= self.SPEED:
                self.x, self.y, self.target, self.moving = tx, ty, None, False
                self.wait = self.rng.randint(90, 240)
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
                nearby = [c for c in self.cells if 0 < abs(c[0] - cx) + abs(c[1] - cy) <= 3]
                if nearby:
                    self.target = self.world.cell_to_feet(self.rng.choice(nearby))
                self.wait = self.rng.randint(60, 160)
        want = "walk" if self.moving else "idle"
        if self.animator.animation != want:
            self.animator.play(want, loop=True)
        self.animator.update()
        return distance <= self.TOUCH_RANGE

    def draw_cave(self, surface, to_screen):
        """The rocky nook it hides in (always drawn: a hint that something lives there)."""
        hx, hy = self.world.cell_to_feet(self.home)
        sx, sy = to_screen(hx, hy)
        rock, dark, light = (92, 88, 96), (24, 22, 34), (128, 124, 132)
        pygame.draw.ellipse(surface, rock, (sx - 22, sy - 30, 44, 36))
        pygame.draw.ellipse(surface, light, (sx - 20, sy - 30, 40, 10))
        pygame.draw.ellipse(surface, dark, (sx - 14, sy - 22, 28, 26))
        for dx, dy, r in ((-20, -2, 6), (19, -3, 5), (-12, 2, 4), (13, 1, 4)):
            pygame.draw.circle(surface, rock, (sx + dx, sy + dy), r)
            pygame.draw.circle(surface, light, (sx + dx - 1, sy + dy - 2), max(1, r // 3))

    def visible_from(self, avatar):
        return math.hypot(avatar.x - self.x, avatar.y - self.y) <= self.SHOW_RANGE

    def draw(self, surface, screen_pos, frame, seen):
        sx, sy = screen_pos
        # A slow, pulsing aura in the monster's colour: something powerful is here.
        color = tuple(self.defn.color) if getattr(self.defn, "color", None) else (170, 110, 230)
        pulse = 0.5 + 0.5 * math.sin(frame / 15)
        aura = pygame.Surface((44, 20), pygame.SRCALPHA)
        pygame.draw.ellipse(aura, (*color, int(60 + 60 * pulse)), (0, 0, 44, 20))
        surface.blit(aura, (sx - 22, sy - 12))
        for i in range(3):   # motes rising around it
            angle = frame / 20 + i * 2.1
            px = sx + int(math.cos(angle) * 14)
            py = sy - 10 - ((frame + i * 25) % 40) // 2
            pygame.draw.rect(surface, color, (px, py, 2, 2))
        if self.animator.available:
            tint = None if seen else (30, 30, 50)
            self.animator.draw(surface, (sx, sy), 30, flip=self.facing < 0, tint=tint)
        head = sy - 36
        label = self.defn.name.upper() if seen else "???"
        text(surface, f"TRIAL: {label}", (sx, head - 6), 7, PALETTE["gold"], center=True, shadow=PALETTE["ink"])
        if self.alert and frame % 30 < 20:
            pygame.draw.rect(surface, PALETTE["coral"], (sx + 14, head + 4, 2, 5))
            pygame.draw.rect(surface, PALETTE["coral"], (sx + 14, head + 10, 2, 2))


def spawn_for(world_map, records, rng, gone=()):
    """TrialRoamers for this map: every Trial monster hiding here that is unlocked and not ``gone``."""
    monsters = load_all()
    roamers = []
    distances = None
    for monster_id, spec in spawns().items():
        defn = monsters.get(monster_id)
        if defn is None or spec["map"] != world_map.map_id or monster_id in gone:
            continue
        if not is_unlocked(defn, records):
            continue
        area = next((a for a in world_map.areas if a[0] == spec["area"]), None)
        if area is None:
            continue
        ax, ay, aw, ah = area[2]
        if distances is None:
            distances = walking_distances(world_map)
        cells = [(x, y) for y in range(ay + 1, ay + ah - 1) for x in range(ax + 1, ax + aw - 1)
                 if (x, y) in distances and world_map.area_at((x, y))[0] == spec["area"]]
        if not cells:
            continue

        def remoteness(cell):
            x, y = cell
            open_sides = sum(1 for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if n in distances)
            return distances[cell], -open_sides      # the furthest walk first; dead ends win ties
        ranked = sorted(cells, key=remoteness, reverse=True)
        home = rng.choice(ranked[:max(1, len(ranked) // 25)])   # one of the most hidden spots
        # It barely moves: a step or two around its nook.
        local = [home] + [c for c in cells if 0 < abs(c[0] - home[0]) + abs(c[1] - home[1]) <= 2]
        roamers.append(TrialRoamer(defn, local, world_map, rng))
    return roamers

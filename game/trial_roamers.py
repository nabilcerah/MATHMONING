"""Monster Trials bosses roaming the world (data/trial_spawns.json).

The Trials page is only a catalogue now: a Trial boss is fought by FINDING it. Each one wanders
its home area of a map with a dark aura and a TRIAL tag; walking into it starts the advanced
battle (game/monster_battle.py). After a battle it leaves until you come back to that map.
A boss whose unlock rule is not met yet (Infinity Zero) does not appear at all.
"""
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


def home_of(monster_id):
    """(map id, area id) where a Trial boss roams, or None."""
    spec = spawns().get(monster_id)
    return (spec["map"], spec["area"]) if spec else None


class TrialRoamer:
    SPEED = 0.35
    TOUCH_RANGE = 12
    NOTICE_RANGE = 70

    def __init__(self, defn, cells, world, rng):
        self.defn, self.id, self.world, self.rng = defn, defn.id, world, rng
        self.cells = cells
        self.x, self.y = world.cell_to_feet(rng.choice(cells))
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
    """TrialRoamers for this map: every Trial boss that lives here, is unlocked and not ``gone``."""
    monsters = load_all()
    roamers = []
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
        cells = [(x, y) for y in range(ay + 1, ay + ah - 1) for x in range(ax + 1, ax + aw - 1)
                 if world_map.is_walkable((x, y)) and world_map.area_at((x, y))[0] == spec["area"]]
        start = world_map.nearest_walkable(world_map.spawn)
        rng.shuffle(cells)
        home = next((c for c in cells[:40] if world_map.find_path(start, c)), None)
        if home is None:
            continue
        # Wander only near home, so the boss stays in its part of the area.
        local = [c for c in cells if abs(c[0] - home[0]) + abs(c[1] - home[1]) <= 6] or [home]
        roamers.append(TrialRoamer(defn, local, world_map, rng))
    return roamers

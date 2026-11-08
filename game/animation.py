"""Sprite-sheet animation playback and placeholder battle effects.

``SpriteAnimator`` plays the real frames sliced from a monster's 3x3 sheet (row 1 idle, row 2 walk,
row 3 attack - see tools/process_monster_sprites.py). Poses the sheet doesn't have (hurt, defeat,
special) are *not* invented: the animator keeps showing a real frame and ``Effects`` draws a
temporary effect on top (flash, shake, knock-back, fade, rings, sparks, a shield bubble...).

Speeds come from ``BALANCE["animation"]`` (frames per second per animation, plus ``speed_scale``).
"""
import math

import pygame

from battle_engine.balance import BALANCE
from config import FPS
from game import monster_sprites


def animation_fps(name):
    settings = BALANCE.get("animation", {})
    return settings.get(f"{name}_fps", 6) * settings.get("speed_scale", 1.0)


class SpriteAnimator:
    """Plays idle/walk/attack from a processed sheet. ``play`` runs a one-shot then returns to idle."""

    def __init__(self, sprite, fps_override=None):
        self.sprite = sprite
        self.fps_override = fps_override or {}
        self.animation = "idle"
        self.loop = True
        self.ticks = 0
        self.then = "idle"
        self.hold_last = False

    @property
    def available(self):
        return monster_sprites.available(self.sprite)

    def frames(self, name=None):
        return monster_sprites.animations(self.sprite).get(name or self.animation, [0])

    def play(self, name, loop=False, then="idle", hold_last=False):
        if name not in monster_sprites.animations(self.sprite):
            name = "idle"
        self.animation, self.loop, self.then, self.hold_last = name, loop, then, hold_last
        self.ticks = 0

    def fps(self):
        return self.fps_override.get(self.animation, animation_fps(self.animation))

    @property
    def finished(self):
        return not self.loop and self.ticks * self.fps() / FPS >= len(self.frames())

    def update(self, steps=1):
        self.ticks += steps
        if self.finished and not self.hold_last:
            self.play(self.then, loop=True)

    def index(self):
        frames = self.frames()
        step = int(self.ticks * self.fps() / FPS)
        if self.loop:
            return frames[step % len(frames)]
        return frames[min(step, len(frames) - 1)]

    def draw(self, surface, anchor, height, flip=False, tint=None, alpha=None):
        return self.draw_frame(surface, self.index(), anchor, height, flip, tint, alpha)

    def draw_frame(self, surface, index, anchor, height, flip=False, tint=None, alpha=None):
        if not self.available:
            return None
        image, (dx, dy) = monster_sprites.frame(self.sprite, index, height, flip, tint)
        if alpha is not None and alpha < 255:
            image = image.copy()
            image.set_alpha(max(0, int(alpha)))
        return surface.blit(image, (round(anchor[0] + dx), round(anchor[1] + dy)))


class Effects:
    """Short-lived placeholder effects: everything here is drawn, nothing is a fake sprite frame."""

    def __init__(self):
        self.items = []

    def add(self, kind, x, y, color=(255, 255, 255), life=30, **extra):
        self.items.append({"kind": kind, "x": x, "y": y, "color": color, "age": 0, "life": life, **extra})

    def burst(self, x, y, color, count=10, life=28, speed=1.6, rng=None):
        for i in range(count):
            angle = (i / count) * math.tau + (rng.random() * 0.4 if rng else 0)
            self.add("spark", x, y, color, life, vx=math.cos(angle) * speed, vy=math.sin(angle) * speed)

    def update(self):
        for item in self.items:
            item["age"] += 1
            if item["kind"] == "spark":
                item["x"] += item["vx"]
                item["y"] += item["vy"]
                item["vy"] += 0.05
        self.items = [i for i in self.items if i["age"] < i["life"]]

    def draw(self, surface):
        for item in self.items:
            t = item["age"] / item["life"]
            x, y, color = int(item["x"]), int(item["y"]), item["color"]
            if item["kind"] == "spark":
                size = 2 if t < 0.6 else 1
                pygame.draw.rect(surface, color, (x, y, size, size))
            elif item["kind"] == "ring":
                radius = int(item.get("start", 6) + t * item.get("grow", 26))
                if radius > 0:
                    pygame.draw.circle(surface, color, (x, y), radius, 1)
            elif item["kind"] == "slash":
                length = 18
                offset = int(t * 10)
                pygame.draw.line(surface, color, (x - length + offset, y - length + offset), (x + offset, y + offset), 2)
            elif item["kind"] == "beam":
                width = max(1, int(5 * (1 - t)))
                pygame.draw.line(surface, color, (x, y), (item["tx"], item["ty"]), width)


def draw_shield_bubble(surface, center, radius, color, strength, frame):
    """A hexagonal bubble whose outline thickness shows how much shield HP is left."""
    cx, cy = center
    wobble = math.sin(frame / 9) * 1.5
    points = [(cx + math.cos(math.pi / 3 * i + math.pi / 6) * (radius + wobble),
               cy + math.sin(math.pi / 3 * i + math.pi / 6) * (radius * 0.9 + wobble)) for i in range(6)]
    layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(layer, (*color, 40 + int(40 * strength)), points)
    pygame.draw.polygon(layer, (*color, 200), points, 1 + int(strength * 2))
    surface.blit(layer, (0, 0))


def draw_lock(surface, x, y, color, opened=False):
    """A tiny padlock icon for Sphynox's puzzle barrier."""
    pygame.draw.rect(surface, color, (x, y + 4, 7, 6))
    if opened:
        pygame.draw.arc(surface, color, (x + 3, y - 1, 6, 8), 0, math.pi, 1)
    else:
        pygame.draw.arc(surface, color, (x + 1, y, 5, 8), 0, math.pi, 1)


def warning_glow(surface, center, radius, color, frame):
    """A pulsing glow behind a monster that is charging a big attack."""
    pulse = (math.sin(frame / 5) + 1) / 2
    layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(layer, (*color, int(40 + 60 * pulse)), center, int(radius + 4 * pulse))
    surface.blit(layer, (0, 0))

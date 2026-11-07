"""Tile-based NUMBER FOREST map with original primitive pixel art."""
import random

import pygame

from config import PALETTE, VIRTUAL_HEIGHT, VIRTUAL_WIDTH
from game.creatures import pixel_monster
from game.ui import text, panel, wrapped

TILE = 16
MAP_WIDTH, MAP_HEIGHT = 30, 22


class Overworld:
    def __init__(self, player, rng=None):
        self.player = player
        self.rng = rng or random.Random()
        self.tiles = self._build_map()
        self.guide = (7, 5)
        self.sign = (17, 8)
        self.arch = (25, 17)
        self.grass_steps = 0
        self.message = "The Number Forest hums with quiet energy."
        self.message_frames = 0
        self.awaiting_duel = False

    def set_message(self, message, frames=210):
        self.message = str(message)
        self.message_frames = frames

    def tick(self):
        if self.message_frames:
            self.message_frames -= 1

    @staticmethod
    def _build_map():
        grid = [["g" for _ in range(MAP_WIDTH)] for _ in range(MAP_HEIGHT)]
        for x in range(MAP_WIDTH):
            grid[0][x] = grid[-1][x] = "T"
        for y in range(MAP_HEIGHT):
            grid[y][0] = grid[y][-1] = "T"
        # Crossroads and winding paths connect a clearing, a pond, and the old arch.
        for x in range(1, 27):
            grid[7][x] = "p"
        for y in range(7, 20):
            grid[y][18] = "p"
        for x in range(18, 28):
            grid[17][x] = "p"
        for y in range(2, 8):
            grid[y][5] = "p"
        for x in range(3, 10):
            grid[3][x] = "p"
        # Pond with a short reed bank.
        for y in range(3, 7):
            for x in range(22, 26):
                grid[y][x] = "~"
        grid[6][24] = "r"
        # Small ranger hut.
        for y in range(1, 4):
            for x in range(2, 5):
                grid[y][x] = "B"
        # Scatter trees while preserving readable paths and the encounter meadow.
        trees = [(9, 2), (11, 4), (12, 3), (3, 9), (5, 10), (8, 11), (10, 9),
                 (14, 10), (15, 13), (20, 10), (22, 11), (23, 13), (27, 10),
                 (4, 16), (8, 17), (12, 18), (14, 20), (21, 20), (27, 19)]
        for x, y in trees:
            grid[y][x] = "T"
        return grid

    def tile_at(self, x, y):
        if x < 0 or y < 0 or x >= MAP_WIDTH or y >= MAP_HEIGHT:
            return "T"
        return self.tiles[y][x]

    def move(self, dx, dy):
        nx, ny = self.player.x + dx, self.player.y + dy
        if self.tile_at(nx, ny) in ("T", "~", "B"):
            return "blocked"
        if (nx, ny) in (self.guide, self.sign, self.arch):
            return "blocked"
        self.player.x, self.player.y = nx, ny
        if self.tile_at(nx, ny) == "g":
            self.grass_steps += 1
            if self.grass_steps >= 2:
                self.grass_steps = 0
                if self.rng.randrange(10) == 0:
                    return "encounter"
        return "moved"

    def interact(self):
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            point = (self.player.x + dx, self.player.y + dy)
            if point == self.guide:
                return "guide"
            if point == self.sign:
                return "sign"
            if point == self.arch:
                return "arch"
        return "nothing"

    def draw(self, surface, frame=0):
        surface.fill(PALETTE["deep"])
        cam_x = max(0, min(MAP_WIDTH - VIRTUAL_WIDTH // TILE, self.player.x - 10))
        cam_y = max(0, min(MAP_HEIGHT - 11, self.player.y - 5))
        # Map begins below its title ribbon and leaves a control strip below.
        for screen_y in range(11):
            for screen_x in range(20):
                mx, my = cam_x + screen_x, cam_y + screen_y
                x, y = screen_x * TILE, 25 + screen_y * TILE
                self._draw_tile(surface, x, y, self.tile_at(mx, my), mx, my, frame)
                if (mx, my) == self.guide:
                    self._draw_person(surface, x + 2, y + 1, (255, 217, 136), (80, 118, 93))
                    text(surface, "!", (x + 6, y - 8), 12, PALETTE["gold"])
                if (mx, my) == self.sign:
                    pygame.draw.rect(surface, (123, 77, 47), (x + 7, y + 8, 3, 8))
                    pygame.draw.rect(surface, PALETTE["gold"], (x + 3, y + 2, 11, 7))
                if (mx, my) == self.arch:
                    pygame.draw.rect(surface, (111, 77, 124), (x + 2, y + 2, 12, 13))
                    pygame.draw.rect(surface, PALETTE["deep"], (x + 5, y + 5, 6, 10))
        px = (self.player.x - cam_x) * TILE
        py = 25 + (self.player.y - cam_y) * TILE
        self._draw_person(surface, px + 3, py + 1, PALETTE["cream"], (78, 135, 181))
        # Top HUD and bottom trail legend.
        pygame.draw.rect(surface, PALETTE["ink"], (0, 0, VIRTUAL_WIDTH, 23))
        text(surface, "NUMBER FOREST", (7, 4), 14, PALETTE["gold"])
        text(surface, f"{self.player.name.upper()}  LV {self.player.level}", (206, 5), 10, PALETTE["white"])
        pygame.draw.rect(surface, PALETTE["night"], (0, 216, VIRTUAL_WIDTH, 24))
        text(surface, "WASD / ARROWS: WALK   E: TALK   B: PRACTICE", (7, 221), 9, PALETTE["cream"])
        if self.message_frames:
            panel(surface, (8, 174, 304, 38), PALETTE["night"], PALETTE["gold"])
            wrapped(surface, self.message, (16, 181, 286, 27), 12, PALETTE["white"], 12, 2)
        else:
            text(surface, "TALL GRASS: ENCOUNTERS", (7, 231), 9, PALETTE["muted"])

    @staticmethod
    def _draw_tile(surface, x, y, code, map_x, map_y, frame):
        if code in ("g", "r"):
            pygame.draw.rect(surface, (66, 128, 82), (x, y, TILE, TILE))
            pygame.draw.rect(surface, (76, 143, 88), (x + ((map_x * 7 + map_y * 3) % 11), y + ((map_x * 5 + map_y) % 13), 2, 2))
            if code == "r":
                for i in range(4):
                    sway = ((frame // 12 + i) % 3) - 1
                    pygame.draw.rect(surface, (172, 195, 116), (x + 3 + i * 3 + sway, y + 3, 2, 10))
            elif (map_x * 13 + map_y * 5) % 4 != 0:
                pygame.draw.rect(surface, (96, 177, 100), (x + 3, y + 6, 2, 7))
                pygame.draw.rect(surface, (115, 188, 103), (x + 10, y + 8, 2, 6))
        elif code == "p":
            pygame.draw.rect(surface, (183, 148, 92), (x, y, TILE, TILE))
            pygame.draw.rect(surface, (207, 174, 111), (x + 2, y + 3, 3, 2))
            pygame.draw.rect(surface, (157, 125, 83), (x + 10, y + 11, 2, 2))
        elif code == "~":
            pygame.draw.rect(surface, (67, 144, 181), (x, y, TILE, TILE))
            pygame.draw.rect(surface, (112, 188, 205), (x + 3 + ((frame // 15) % 4), y + 5, 5, 1))
            pygame.draw.rect(surface, (49, 119, 164), (x + 8, y + 12, 6, 1))
        elif code == "T":
            pygame.draw.rect(surface, (65, 124, 80), (x, y, TILE, TILE))
            pygame.draw.rect(surface, (102, 69, 48), (x + 7, y + 9, 4, 7))
            pygame.draw.rect(surface, (39, 90, 62), (x + 2, y + 4, 12, 8))
            pygame.draw.rect(surface, (54, 112, 71), (x + 4, y + 1, 9, 8))
            pygame.draw.rect(surface, (79, 145, 83), (x + 6, y + 3, 4, 3))
        elif code == "B":
            pygame.draw.rect(surface, (193, 145, 83), (x, y, TILE, TILE))
            pygame.draw.rect(surface, (91, 63, 56), (x + 2, y + 1, 12, 5))
            pygame.draw.rect(surface, (217, 184, 125), (x + 3, y + 6, 10, 10))
            pygame.draw.rect(surface, (92, 65, 56), (x + 7, y + 10, 4, 6))

    @staticmethod
    def _draw_person(surface, x, y, shirt, trousers):
        pygame.draw.rect(surface, (78, 51, 44), (x + 3, y, 7, 6))
        pygame.draw.rect(surface, (235, 184, 132), (x + 4, y + 2, 5, 5))
        pygame.draw.rect(surface, shirt, (x + 2, y + 7, 9, 6))
        pygame.draw.rect(surface, trousers, (x + 3, y + 13, 3, 3))
        pygame.draw.rect(surface, trousers, (x + 8, y + 13, 3, 3))

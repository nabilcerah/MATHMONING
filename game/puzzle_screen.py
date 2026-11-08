"""Full-screen puzzle shrine UI: Sequence Stones, Balance Scale, Target Number, Magic Square, Star Chart.

Gentle rules, like battles: unlimited tries, a hint after 2 misses, and after 4 the shrine shows
the solution (the puzzle still has to be entered, for half the reward).
"""
import pygame

from config import PALETTE
from game.ui import panel, text, wrapped
from mathematics import puzzles as P

HINT_AFTER, REVEAL_AFTER = 2, 4
STAR_ROUNDS = 3


class PuzzleScreen:
    def __init__(self, kind, tier, rng, title=None):
        self.kind, self.tier, self.rng = kind, tier, rng
        self.round = 0
        self.puzzle = self._new_puzzle()
        self.title = title or self.puzzle.title
        self.answer = ""
        self.wrong = 0
        self.revealed = False
        self.solved = False
        self.closed = False
        self.shake = 0
        self.message = ""
        self.age = 0

    def _new_puzzle(self):
        if self.kind == "starchart":
            puzzle = P.starchart(self.rng, self.tier, self.round)
            self.cursor = [0, 0]
        else:
            puzzle = P.GENERATORS[self.kind](self.rng, self.tier)
        if self.kind == "magic":
            self.grid = [row[:] for row in puzzle.data["given"]]
            self.locked = {(r, c) for r in range(3) for c in range(3) if self.grid[r][c] is not None}
            self.cell = next((r, c) for r in range(3) for c in range(3) if (r, c) not in self.locked)
        return puzzle

    # ---------------------------------------------------------------- input
    def handle_key(self, key, unicode=""):
        if self.solved:
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_e):
                self.closed = True
            return
        if key == pygame.K_ESCAPE:
            self.closed = True
            return
        if self.kind == "magic":
            self._magic_key(key, unicode)
        elif self.kind == "starchart":
            self._star_key(key)
        else:
            allowed = "0123456789" + ("+-*x()" if self.kind == "target" else "-")
            if key == pygame.K_BACKSPACE:
                self.answer = self.answer[:-1]
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.answer.strip():
                self._submit(self.answer)
            elif unicode and unicode in allowed and len(self.answer) < 18:
                self.answer += unicode

    def _magic_key(self, key, unicode):
        r, c = self.cell
        moves = {pygame.K_UP: (-1, 0), pygame.K_w: (-1, 0), pygame.K_DOWN: (1, 0), pygame.K_s: (1, 0),
                 pygame.K_LEFT: (0, -1), pygame.K_a: (0, -1), pygame.K_RIGHT: (0, 1), pygame.K_d: (0, 1)}
        if key in moves:
            dr, dc = moves[key]
            self.cell = ((r + dr) % 3, (c + dc) % 3)
        elif unicode and unicode in "123456789" and (r, c) not in self.locked:
            self.grid[r][c] = int(unicode)
        elif key in (pygame.K_BACKSPACE, pygame.K_DELETE) and (r, c) not in self.locked:
            self.grid[r][c] = None
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if any(v is None for row in self.grid for v in row):
                self.message = "Fill every empty square first."
                return
            self._submit(self.grid)

    def _star_key(self, key):
        size = self.puzzle.data["size"]
        moves = {pygame.K_UP: (0, 1), pygame.K_w: (0, 1), pygame.K_DOWN: (0, -1), pygame.K_s: (0, -1),
                 pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0)}
        if key in moves:
            dx, dy = moves[key]
            self.cursor[0] = max(0, min(size - 1, self.cursor[0] + dx))
            self.cursor[1] = max(0, min(size - 1, self.cursor[1] + dy))
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            self._submit(tuple(self.cursor))

    def _submit(self, answer):
        if P.check(self.puzzle, answer):
            if self.kind == "starchart" and self.round < STAR_ROUNDS - 1:
                self.round += 1
                self.puzzle = self._new_puzzle()
                self.wrong = 0
                self.message = f"Bullseye! Star {self.round} of {STAR_ROUNDS} placed. Next one..."
                return
            self.solved = True
            self.message = "Solved! The shrine glows." + (" (with the shrine's help)" if self.revealed else "")
            return
        self.wrong += 1
        self.shake = 14
        self.answer = ""
        if self.wrong >= REVEAL_AFTER:
            self.revealed = True
            self.message = self.puzzle.solution + " Now enter it to finish."
        elif self.wrong >= HINT_AFTER:
            self.message = "Hint: " + self.puzzle.hint
        else:
            self.message = "Not quite - have another look."

    def update(self):
        self.age += 1
        if self.shake:
            self.shake -= 1

    # ----------------------------------------------------------------- draw
    def draw(self, surface, frame=0):
        surface.fill(PALETTE["ink"])
        for i in range(24):  # a few quiet stars behind the shrine
            pygame.draw.rect(surface, PALETTE["night"], ((i * 53 + 11) % 320, (i * 37 + 7) % 240, 2, 2))
        title_color = (190, 150, 255) if self.kind == "starchart" else PALETTE["gold"]
        text(surface, self.title, (160, 12), 16, title_color, center=True)
        if self.kind == "starchart":
            text(surface, f"STAR {self.round + 1} / {STAR_ROUNDS}", (312, 6), 9, PALETTE["muted"], align="right")
        panel(surface, (8, 26, 304, 34), PALETTE["night"])
        wrapped(surface, self.puzzle.prompt, (16, 31, 288, 26), 11, PALETTE["white"], 12, 2)
        jiggle = ((self.shake % 4) - 1.5) * 2 if self.shake else 0
        getattr(self, f"_draw_{self.kind}")(surface, frame, jiggle)
        if self.message:
            color = PALETTE["mint"] if self.solved or "Bullseye" in self.message else (
                PALETTE["gold"] if self.message.startswith("Hint") else PALETTE["cream"])
            wrapped(surface, self.message, (12, 197, 296, 22), 10, color, 11, 2)
        footer = "ENTER: CONTINUE" if self.solved else {
            "magic": "ARROWS: MOVE   1-9: WRITE   ENTER: CHECK   ESC: LEAVE",
            "starchart": "ARROWS: MOVE THE STAR   ENTER: PLACE   ESC: LEAVE",
            "target": "TYPE e.g. 3x5+8   ENTER: CHECK   ESC: LEAVE",
        }.get(self.kind, "TYPE THE NUMBER   ENTER: CHECK   ESC: LEAVE")
        text(surface, footer, (160, 228), 9, PALETTE["cream"], center=True)

    def _input_box(self, surface, x, y, w, frame, jiggle, label="> "):
        border = PALETTE["coral"] if self.shake else PALETTE["gold"]
        pygame.draw.rect(surface, border, (x - 1 + jiggle, y - 1, w + 2, 20))
        pygame.draw.rect(surface, PALETTE["ink"], (x + jiggle, y, w, 18))
        caret = "_" if frame % 50 < 28 and not self.solved else ""
        shown = self.answer.replace("*", "×").replace("x", "×")
        text(surface, label + shown + caret, (x + 5 + jiggle, y + 3), 13, PALETTE["cream"])

    def _draw_sequence(self, surface, frame, jiggle):
        terms = self.puzzle.data["terms"] + ["?"]
        for i, value in enumerate(terms):
            cx, cy = 40 + i * 60, 108 + (6 if i % 2 else 0)
            last = i == len(terms) - 1
            pygame.draw.ellipse(surface, PALETTE["ink"], (cx - 24, cy + 14, 48, 10))
            pygame.draw.circle(surface, (120, 116, 112), (cx, cy), 23)
            pygame.draw.circle(surface, (176, 170, 160) if not last else (190, 150, 255), (cx, cy), 20)
            if last and frame % 40 < 20:
                pygame.draw.circle(surface, PALETTE["gold"], (cx, cy), 23, 1)
            shown = self.answer if last and self.answer else str(value)
            text(surface, shown, (cx, cy), 16, PALETTE["ink"], center=True)
        self._input_box(surface, 110, 160, 100, frame, jiggle)

    def _draw_balance(self, surface, frame, jiggle):
        left, right = self.puzzle.data["left"], self.puzzle.data["right"]
        tilt = 0 if self.solved else (4 if frame % 80 < 40 else 3)
        pygame.draw.rect(surface, (120, 86, 54), (156, 82, 8, 70))
        pygame.draw.polygon(surface, (150, 110, 70), [(140, 152), (180, 152), (160, 138)])
        pygame.draw.line(surface, PALETTE["cream"], (70, 84 + tilt), (250, 84 - tilt), 4)
        for x, y, label in ((70, 84 + tilt, left), (250, 84 - tilt, right)):
            pygame.draw.line(surface, PALETTE["muted"], (x, y), (x - 18, y + 26))
            pygame.draw.line(surface, PALETTE["muted"], (x, y), (x + 18, y + 26))
            pygame.draw.ellipse(surface, PALETTE["gold"], (x - 34, y + 22, 68, 16))
            panel(surface, (x - 36, y + 40, 72, 22), PALETTE["night"])
            text(surface, label.replace("?", self.answer or "?"), (x, y + 51), 13, PALETTE["white"], center=True)
        self._input_box(surface, 120, 160, 80, frame, jiggle, "? = ")

    def _draw_target(self, surface, frame, jiggle):
        numbers, goal = self.puzzle.data["numbers"], self.puzzle.data["target"]
        for i, n in enumerate(numbers):
            x = 52 + i * 52
            panel(surface, (x, 76, 40, 40), PALETTE["deep"], PALETTE["sky"])
            text(surface, str(n), (x + 20, 96), 20, PALETTE["white"], center=True)
        text(surface, "=", (228, 96), 20, PALETTE["muted"], center=True)
        pygame.draw.circle(surface, PALETTE["gold"], (272, 96), 26)
        pygame.draw.circle(surface, PALETTE["night"], (272, 96), 23)
        text(surface, str(goal), (272, 96), 20, PALETTE["gold"], center=True)
        value = P.evaluate_expression(self.answer, numbers) if self.answer else None
        self._input_box(surface, 52, 160, 156, frame, jiggle)
        if value is not None:
            text(surface, f"= {value}", (220, 163), 13, PALETTE["mint"] if value == goal else PALETTE["muted"])

    def _draw_magic(self, surface, frame, jiggle):
        size, left, top = 34, 109 + jiggle, 66
        for r in range(3):
            for c in range(3):
                x, y = left + c * size, top + r * size
                value = self.grid[r][c]
                locked = (r, c) in self.locked
                pygame.draw.rect(surface, PALETTE["deep"] if locked else PALETTE["night"], (x, y, size - 2, size - 2))
                if (r, c) == self.cell and not self.solved:
                    pygame.draw.rect(surface, PALETTE["gold"], (x, y, size - 2, size - 2), 2)
                if value is not None:
                    text(surface, str(value), (x + size // 2 - 1, y + size // 2 - 1), 18,
                         PALETTE["cream"] if locked else PALETTE["gold"], center=True)
        # Live sums: green when a full line makes 15.
        for r in range(3):
            row = self.grid[r]
            self._sum_label(surface, row, left + 3 * size + 8, top + r * size + 10)
        for c in range(3):
            col = [self.grid[r][c] for r in range(3)]
            self._sum_label(surface, col, left + c * size + 8, top + 3 * size + 2)

    def _sum_label(self, surface, values, x, y):
        if any(v is None for v in values):
            text(surface, "·", (x, y), 12, PALETTE["muted"])
        else:
            total = sum(values)
            text(surface, str(total), (x, y), 11, PALETTE["mint"] if total == 15 else PALETTE["coral"])

    def _draw_starchart(self, surface, frame, jiggle):
        size = self.puzzle.data["size"]
        cell, left, bottom = 17, 92, 186
        top = bottom - (size - 1) * cell
        for i in range(size):
            pygame.draw.line(surface, PALETTE["night"], (left + i * cell, top), (left + i * cell, bottom))
            pygame.draw.line(surface, PALETTE["night"], (left, bottom - i * cell), (left + (size - 1) * cell, bottom - i * cell))
            text(surface, str(i), (left + i * cell, bottom + 6), 8, PALETTE["muted"], center=True)
            text(surface, str(i), (left - 8, bottom - i * cell), 8, PALETTE["muted"], center=True)
        pygame.draw.line(surface, PALETTE["cream"], (left, top), (left, bottom), 1)
        pygame.draw.line(surface, PALETTE["cream"], (left, bottom), (left + (size - 1) * cell, bottom), 1)
        text(surface, "x", (left + (size - 1) * cell + 8, bottom), 9, PALETTE["cream"], center=True)
        text(surface, "y", (left, top - 7), 9, PALETTE["cream"], center=True)
        line = self.puzzle.data["line"]
        if line:
            m, c = line
            points = [(x, m * x + c) for x in range(size) if 0 <= m * x + c <= size - 1]
            if len(points) >= 2:
                (x0, y0), (x1, y1) = points[0], points[-1]
                pygame.draw.line(surface, (120, 90, 200), (left + x0 * cell, bottom - y0 * cell),
                                 (left + x1 * cell, bottom - y1 * cell), 2)
        sx, sy = left + self.cursor[0] * cell + jiggle, bottom - self.cursor[1] * cell
        glow = (190, 150, 255) if frame % 30 < 15 else PALETTE["gold"]
        pygame.draw.polygon(surface, glow, [(sx, sy - 6), (sx + 2, sy - 2), (sx + 6, sy), (sx + 2, sy + 2),
                                            (sx, sy + 6), (sx - 2, sy + 2), (sx - 6, sy), (sx - 2, sy - 2)])
        text(surface, f"({self.cursor[0]}, {self.cursor[1]})", (250, 120), 16, PALETTE["gold"], center=True)

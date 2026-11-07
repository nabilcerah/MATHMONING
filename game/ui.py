"""Tiny reusable pixel-RPG interface primitives.

Pixel art is drawn on the low-resolution canvas, but text is queued and drawn
afterwards at the real window resolution so it stays crisp and readable.
"""
import pygame

from config import PALETTE

_fonts = {}
_queue = []
_layer = {"canvas": None}


def font(size):
    """Return a cached default font; building fonts every frame is costly."""
    size = max(1, int(round(size)))
    if not pygame.font.get_init():
        # Fonts from an earlier pygame session are invalid after pygame.quit().
        pygame.font.init()
        _fonts.clear()
    cached = _fonts.get(size)
    if cached is None:
        cached = _fonts[size] = pygame.font.Font(None, size)
    return cached


MEASURE_SCALE = 4


def measure(message, size):
    """Width/height in canvas pixels, measured at high resolution to match the final render."""
    width, height = font(size * MEASURE_SCALE).size(str(message))
    return (width + MEASURE_SCALE - 1) // MEASURE_SCALE, (height + MEASURE_SCALE - 1) // MEASURE_SCALE


def set_text_layer(canvas):
    """Text drawn onto ``canvas`` is deferred and rendered at window resolution."""
    _fonts.clear()
    _queue.clear()
    _layer["canvas"] = canvas


def begin_frame():
    _queue.clear()


def flush_text(window, scale, offset=(0, 0)):
    ox, oy = offset
    for message, rect, size, color, shadow, anchor in _queue:
        f = font(size * scale)
        x = {"left": rect.left, "right": rect.right, "center": rect.centerx}[anchor]
        point = (ox + round(x * scale), oy + round(rect.centery * scale))
        if shadow:
            step = max(1, round(scale / 2))
            image = f.render(message, True, shadow)
            window.blit(image, image.get_rect(**{_ANCHORS[anchor]: (point[0] + step, point[1] + step)}))
        image = f.render(message, True, color)
        window.blit(image, image.get_rect(**{_ANCHORS[anchor]: point}))
    _queue.clear()


_ANCHORS = {"left": "midleft", "right": "midright", "center": "center"}


def panel(surface, rect, fill=None, border=None):
    rect = pygame.Rect(rect)
    fill = fill or PALETTE["night"]
    border = border or PALETTE["cream"]
    pygame.draw.rect(surface, PALETTE["ink"], rect.inflate(4, 4))
    pygame.draw.rect(surface, border, rect)
    pygame.draw.rect(surface, fill, rect.inflate(-4, -4))
    pygame.draw.line(surface, PALETTE["white"], (rect.left + 3, rect.top + 2), (rect.right - 3, rect.top + 2), 1)


def text(surface, message, pos, size=10, color=None, center=False, shadow=None, align="left"):
    message = str(message)
    color = color or PALETTE["white"]
    f = font(size)
    target = pygame.Rect((0, 0), measure(message, size))
    if center:
        target.center = pos
    elif align == "right":
        target.topright = pos
    else:
        target.topleft = pos
    if surface is _layer["canvas"]:
        anchor = "center" if center else align
        _queue.append((message, target, size, color, shadow, anchor))
    else:
        if shadow:
            surface.blit(f.render(message, False, shadow), target.move(1, 1))
        surface.blit(f.render(message, False, color), target)
    return target


def wrap_lines(message, width, size=10):
    lines, line = [], ""
    for word in str(message).split():
        candidate = (line + " " + word).strip()
        if measure(candidate, size)[0] > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def wrapped(surface, message, rect, size=10, color=None, line_height=None, max_lines=None):
    lines = wrap_lines(message, rect[2], size)
    line_height = line_height or size
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;:") + "…"
    for index, line in enumerate(lines):
        text(surface, line, (rect[0], rect[1] + index * line_height), size, color)
    return len(lines)


def meter(surface, x, y, width, height, value, maximum, color, label=None, warn=False):
    pygame.draw.rect(surface, PALETTE["ink"], (x, y, width, height))
    pygame.draw.rect(surface, PALETTE["cream"], (x + 1, y + 1, width - 2, height - 2))
    ratio = max(0, min(1, value / max(1, maximum)))
    inner = int(round((width - 4) * ratio))
    if inner:
        # Low health reads as a warning colour.
        if warn and ratio <= 0.25:
            color = PALETTE["coral"]
        elif warn and ratio <= 0.5:
            color = PALETTE["gold"]
        pygame.draw.rect(surface, color, (x + 2, y + 2, inner, height - 4))
        if height >= 6:
            highlight = tuple(min(255, c + 45) for c in color)
            pygame.draw.line(surface, highlight, (x + 2, y + 2), (x + 1 + inner, y + 2))
    if label:
        text(surface, label, (x, y - 9), 10, PALETTE["white"])


HEART_ROWS = ("011000110", "111101111", "111111111", "111111111", "011111110", "001111100", "000111000", "000010000")


def heart(surface, x, y, color, filled=True):
    """A 9x8 pixel heart, filled or as an outline."""
    for row_index, row in enumerate(HEART_ROWS):
        for col_index, cell in enumerate(row):
            if cell != "1":
                continue
            edge = row_index in (0, 7) or col_index in (0, 8) or row[col_index - 1] == "0" or                 row[min(8, col_index + 1)] == "0"
            if filled or edge:
                surface.set_at((x + col_index, y + row_index), color)


def cursor(surface, x, y, color=None, frame=0):
    """A small pixel arrow; the default font has no triangle glyph."""
    nudge = 1 if frame % 40 < 20 else 0
    x += nudge
    pygame.draw.polygon(surface, color or PALETTE["gold"], [(x, y), (x + 4, y + 3), (x, y + 6)])


def menu(surface, rect, choices, selected, size=11, frame=0, disabled=(), spacing=15, highlight=()):
    panel(surface, rect, PALETTE["night"], PALETTE["cream"])
    x, y, width, _ = rect
    for index, choice in enumerate(choices):
        row_y = y + 7 + index * spacing
        if index == selected:
            pygame.draw.rect(surface, PALETTE["deep"], (x + 5, row_y - 2, width - 10, 12))
            cursor(surface, x + 7, row_y + 1, PALETTE["gold"], frame)
            color = PALETTE["gold"]
        else:
            color = PALETTE["muted"] if index in disabled else (PALETTE["mint"] if index in highlight else PALETTE["white"])
        text(surface, choice, (x + 16, row_y), size, color)

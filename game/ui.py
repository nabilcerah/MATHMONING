"""Tiny reusable pixel-RPG interface primitives."""
import pygame

from config import PALETTE


def panel(surface, rect, fill=None, border=None):
    rect = pygame.Rect(rect)
    fill = fill or PALETTE["night"]
    border = border or PALETTE["cream"]
    pygame.draw.rect(surface, PALETTE["ink"], rect.inflate(4, 4))
    pygame.draw.rect(surface, border, rect)
    pygame.draw.rect(surface, fill, rect.inflate(-4, -4))
    pygame.draw.line(surface, PALETTE["white"], (rect.left + 3, rect.top + 2), (rect.right - 3, rect.top + 2), 1)


def text(surface, message, pos, size=10, color=None, font=None, center=False):
    font = font or pygame.font.Font(None, size)
    image = font.render(str(message), False, color or PALETTE["white"])
    target = image.get_rect()
    if center:
        target.center = pos
    else:
        target.topleft = pos
    surface.blit(image, target)
    return target


def wrapped(surface, message, rect, size=10, color=None, line_height=None, max_lines=None):
    font = pygame.font.Font(None, size)
    words = str(message).split()
    lines, line = [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if font.size(candidate)[0] > rect[2] and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    line_height = line_height or size
    if max_lines:
        lines = lines[:max_lines]
    for index, line in enumerate(lines):
        text(surface, line, (rect[0], rect[1] + index * line_height), size, color, font)
    return len(lines)


def meter(surface, x, y, width, height, value, maximum, color, label=None):
    pygame.draw.rect(surface, PALETTE["ink"], (x, y, width, height))
    pygame.draw.rect(surface, PALETTE["cream"], (x + 1, y + 1, width - 2, height - 2))
    ratio = max(0, min(1, value / max(1, maximum)))
    inner = int((width - 4) * ratio)
    if inner:
        pygame.draw.rect(surface, color, (x + 2, y + 2, inner, height - 4))
    if label:
        text(surface, label, (x, y - 9), 10, PALETTE["white"])


def menu(surface, rect, choices, selected, size=11):
    panel(surface, rect, PALETTE["night"], PALETTE["cream"])
    x, y, width, _ = rect
    for index, choice in enumerate(choices):
        color = PALETTE["gold"] if index == selected else PALETTE["white"]
        prefix = "▶ " if index == selected else "  "
        text(surface, prefix + choice, (x + 10, y + 7 + index * 15), size, color)

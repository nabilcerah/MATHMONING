"""The monster information card shared by the Party, Sanctuary, Evolution and Dex screens."""
import pygame

from config import PALETTE
from game.creatures import draw_creature
from game.ui import meter, panel, text, wrapped
from mathematics import curriculum
from monsters import elemental_system


def element_badge(surface, element, pos, width=40):
    rect = pygame.Rect(pos[0], pos[1], width, 9)
    pygame.draw.rect(surface, elemental_system.color(element), rect)
    text(surface, element.upper(), rect.center, 8, PALETTE["ink"], center=True)


def mastery_line(profile, topic):
    stats = profile.get(topic, {})
    if not stats:
        return f"{curriculum.label(topic)}: not started", 0
    return f"{curriculum.label(topic)}: {stats['mastery']} ({stats['label']})", stats["mastery"]


def draw_card(surface, monster, rect, profile, frame=0, show_moves=True):
    x, y, w, h = rect
    panel(surface, rect, PALETTE["night"])
    spec = monster.spec
    pygame.draw.rect(surface, PALETTE["deep"], (x + 6, y + 6, 54, 54))
    pose = ("idle", "idle2", "idle3", "idle2")[(frame // 18) % 4]
    surface.set_clip((x + 6, y + 6, 54, 54))
    draw_creature(surface, spec, (x + 33, y + 58), 44, "hurt" if monster.fainted else pose)
    surface.set_clip(None)
    text(surface, spec.name, (x + 66, y + 6), 12, PALETTE["gold"])
    element_badge(surface, spec.element, (x + 66, y + 20))
    text(surface, f"Lv {monster.level}", (x + 110, y + 20), 9, PALETTE["white"])
    wrapped(surface, spec.role, (x + 66, y + 31, w - 72, 10), 8, PALETTE["muted"], 9, 1)
    meter(surface, x + 66, y + 43, w - 74, 6, monster.hp, monster.max_hp, PALETTE["mint"], warn=True)
    text(surface, f"HP {monster.hp}/{monster.max_hp}" + ("  FAINTED" if monster.fainted else ""),
         (x + 66, y + 51), 8, PALETTE["coral"] if monster.fainted else PALETTE["cream"])
    yy = y + 64
    meter(surface, x + 6, yy, w - 12, 4, monster.exp, monster.next_level_exp, PALETTE["sky"])
    text(surface, f"EXP {monster.exp}/{monster.next_level_exp}", (x + 6, yy + 6), 8, PALETTE["sky"])
    text(surface, f"ATK {monster.attack}  DEF {monster.defence}  SPD {monster.speed}", (x + 6, yy + 16), 8,
         PALETTE["white"])
    line, value = mastery_line(profile, spec.mastery_topic)
    used = wrapped(surface, "MASTERY  " + line, (x + 6, yy + 27, w - 12, 20), 8, PALETTE["gold"], 9, 2)
    yy += 9 * (used - 1) + 10
    meter(surface, x + 6, yy + 27, w - 12, 4, value, 100, PALETTE["gold"])
    if show_moves:
        moves = ", ".join(m.name for m in monster.moves())
        wrapped(surface, "Moves: " + moves, (x + 6, yy + 35, w - 12, 20), 8, PALETTE["cream"], 9, 2)
        if spec.passive:
            wrapped(surface, f"{spec.passive.get('name', 'Passive')}: {spec.passive.get('text', '')}",
                    (x + 6, yy + 54, w - 12, 30), 8, PALETTE["muted"], 9, 3)

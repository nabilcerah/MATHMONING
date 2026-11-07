"""The MathDex: a collection journal of every wild MATHMON seen and captured."""
import pygame

from config import PALETTE
from game.creatures import TOPIC_COLORS, WILD, creature_spec, draw_creature, leader_spec
from game.ui import heart, panel, text, wrapped

COLUMNS = 5
CARD_W, CARD_H = 56, 112


class MathDex:
    def __init__(self, repository, player, area_names=None):
        self.repository = repository
        self.player = player
        self.area_names = area_names or {}
        self.selected = 0
        self.closed = False
        self.notice = ""
        self.refresh()

    def entries(self):
        """Your partner first (always on the team), then every wild species."""
        return [self.partner] + list(WILD)

    def refresh(self):
        self.partner = creature_spec(self.player.creature, self.player.level)
        flags = self.repository.world_flags(self.player.player_id)
        self.leader = leader_spec(self.player, flags).name
        self.seen = {f.split(":", 1)[1] for f in flags if f.startswith("dex_seen:")}
        self.friends = {f.split(":", 1)[1] for f in flags if f.startswith("dex_friend:")}
        self.seen |= self.friends
        companion = [f.split(":", 1)[1] for f in flags if f.startswith("companion:")]
        self.companion = companion[0] if companion else None

    @staticmethod
    def friend_count(flags):
        return sum(1 for f in flags if f.startswith("dex_friend:"))

    def handle_key(self, key):
        rows = (len(self.entries()) + COLUMNS - 1) // COLUMNS
        col, row = self.selected % COLUMNS, self.selected // COLUMNS
        if key in (pygame.K_ESCAPE, pygame.K_m, pygame.K_TAB):
            self.closed = True
        elif key in (pygame.K_LEFT, pygame.K_a):
            col = (col - 1) % COLUMNS
        elif key in (pygame.K_RIGHT, pygame.K_d):
            col = (col + 1) % COLUMNS
        elif key in (pygame.K_UP, pygame.K_w):
            row = (row - 1) % rows
        elif key in (pygame.K_DOWN, pygame.K_s):
            row = (row + 1) % rows
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e):
            self._toggle_companion()
            return
        self.selected = min(len(self.entries()) - 1, row * COLUMNS + col)

    def _toggle_companion(self):
        """Make the selected team member the leader: it battles for you and follows you."""
        spec = self.entries()[self.selected]
        pid = self.player.player_id
        if spec is not self.partner and spec.name not in self.friends:
            self.notice = "Capture it first, then it can join your team."
            return
        if spec.name == self.leader:
            self.notice = f"{spec.name} is already leading your team."
            return
        self.repository.clear_world_flags(pid, "companion:")
        if spec is not self.partner:
            self.repository.set_world_flag(pid, f"companion:{spec.name}")
        self.notice = f"{spec.name} now leads your team! Everyone else stays in your team."
        self.refresh()

    # -------------------------------------------------------------------- draw
    def draw(self, surface, frame=0):
        surface.fill(PALETTE["deep"])
        text(surface, "MATHDEX", (12, 6), 18, PALETTE["gold"])
        text(surface, f"CAPTURED {len(self.friends & {s.name for s in WILD})}/{len(WILD)}    "
                      f"SEEN {len(self.seen & {s.name for s in WILD})}/{len(WILD)}",
             (308, 9), 10, PALETTE["cream"], align="right")
        for index, spec in enumerate(self.entries()):
            col, row = index % COLUMNS, index // COLUMNS
            x, y = 12 + col * (CARD_W + 6), 30 + row * (CARD_H + 6)
            chosen = index == self.selected
            partner = spec is self.partner
            friend, seen = partner or spec.name in self.friends, partner or spec.name in self.seen
            border = PALETTE["gold"] if chosen else (PALETTE["mint"] if friend else PALETTE["night"])
            panel(surface, (x, y, CARD_W, CARD_H), PALETTE["night"] if friend else PALETTE["ink"], border)
            bob = (frame // 15) % 2 if chosen and friend else 0
            tint = None if friend else ((52, 66, 86) if seen else (32, 40, 58))
            pose = "happy" if chosen and friend and (frame // 40) % 3 == 2 else "idle"
            surface.set_clip((x + 2, y + 2, CARD_W - 4, CARD_H - 4))  # wide creatures stay inside their card
            draw_creature(surface, spec, (x + CARD_W // 2, y + 80 - bob), 44, pose, tint=tint)
            surface.set_clip(None)
            pygame.draw.rect(surface, TOPIC_COLORS.get(spec.topic, PALETTE["muted"]), (x + 5, y + CARD_H - 9, CARD_W - 10, 3))
            label = spec.name if seen else "???"
            text(surface, label, (x + CARD_W // 2, y + 92), 10, PALETTE["white"] if friend else PALETTE["muted"], center=True)
            if spec.name == self.leader:
                heart(surface, x + CARD_W - 14, y + 6, PALETTE["gold"])
            if partner:
                text(surface, "PARTNER", (x + CARD_W // 2, y + 5), 7, PALETTE["gold"], center=True)

        spec = self.entries()[self.selected]
        partner = spec is self.partner
        friend, seen = partner or spec.name in self.friends, partner or spec.name in self.seen
        panel(surface, (8, 152, 304, 62), PALETTE["night"], PALETTE["mint"] if friend else PALETTE["cream"])
        homes = ", ".join(self.area_names.get(area, area.title()) for area in spec.habitat)
        topic = spec.topic.upper() if spec.topic else "ALL SKILLS"
        if seen:
            text(surface, spec.name, (16, 157), 13, PALETTE["gold"])
            text(surface, f"{spec.element}  •  {topic}", (304, 159), 9, TOPIC_COLORS.get(spec.topic, PALETTE["muted"]),
                 align="right")
            wrapped(surface, spec.blurb, (16, 172, 288, 20), 10, PALETTE["white"], 11, 2)
        else:
            text(surface, "???", (16, 157), 13, PALETTE["muted"])
            wrapped(surface, f"Not seen yet. Search the tall grass of {homes}.", (16, 172, 288, 20), 10,
                    PALETTE["muted"], 11, 2)
        if friend:
            lead = "LEADER: battles and walks with you" if spec.name == self.leader else "ENTER: make leader"
            extra = "Your first partner" if partner else f"Boosts {spec.topic or 'every'} attacks"
            status, color = f"{lead}   •   {extra}", PALETTE["mint"]
        elif seen:
            status, color = f"Lives in {homes}. Weaken it to 40% HP, then CAPTURE.", PALETTE["cream"]
        else:
            status, color = f"Habitat: {homes}", PALETTE["muted"]
        text(surface, status, (16, 199), 9, color)
        footer = self.notice or "ARROWS: BROWSE     ENTER: CHOOSE LEADER (GOLD HEART)     ESC / M: BACK"
        text(surface, footer, (160, 226), 9, PALETTE["gold"] if self.notice else PALETTE["cream"], center=True)

"""The MathDex: a collection journal of every wild MATHMON seen and captured."""
import pygame

from config import PALETTE
from game import monster_sprites
from game.creatures import NEMESIS, TOPIC_COLORS, WILD, creature_spec, draw_creature, leader_spec, lineage, strong_against
from game.team import Team
from game.ui import heart, panel, text, wrapped

COLUMNS = 5
CARD_W, CARD_H = 56, 112
# The TRIALS page: the advanced monsters from data/monsters, recorded when you beat them (press T).
TRIAL_COLUMNS = 6
TRIAL_W, TRIAL_H = 46, 58
PAGES = ("MATHDEX", "TRIALS")


class MathDex:
    def __init__(self, repository, player, area_names=None):
        self.repository = repository
        self.player = player
        self.area_names = area_names or {}
        self.selected = 0
        self.page = 0
        self.trial_selected = 0
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
        self.team = Team(self.repository, self.player, flags)
        self.seen = {f.split(":", 1)[1] for f in flags if f.startswith("dex_seen:")}
        self.friends = {f.split(":", 1)[1] for f in flags if f.startswith("dex_friend:")}
        self.seen |= self.friends
        companion = [f.split(":", 1)[1] for f in flags if f.startswith("companion:")]
        self.companion = companion[0] if companion else None
        from battle_engine.monster_data import load_all
        self.trial_monsters = list(load_all().values())
        records = getattr(self.repository, "monster_records", None)
        self.trial_records = records(self.player.player_id) if records else {}

    @staticmethod
    def friend_count(flags):
        return sum(1 for f in flags if f.startswith("dex_friend:"))

    def handle_key(self, key):
        if key in (pygame.K_q, pygame.K_e, pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.page = (self.page + 1) % len(PAGES)
            self.notice = ""
            return
        if self.page == 1:
            self._trial_key(key)
            return
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

    def _trial_key(self, key):
        count = len(self.trial_monsters)
        rows = (count + TRIAL_COLUMNS - 1) // TRIAL_COLUMNS
        col, row = self.trial_selected % TRIAL_COLUMNS, self.trial_selected // TRIAL_COLUMNS
        if key in (pygame.K_ESCAPE, pygame.K_m, pygame.K_TAB):
            self.closed = True
            return
        if key in (pygame.K_LEFT, pygame.K_a):
            col = (col - 1) % TRIAL_COLUMNS
        elif key in (pygame.K_RIGHT, pygame.K_d):
            col = (col + 1) % TRIAL_COLUMNS
        elif key in (pygame.K_UP, pygame.K_w):
            row = (row - 1) % rows
        elif key in (pygame.K_DOWN, pygame.K_s):
            row = (row + 1) % rows
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self.notice = "Challenge Trials monsters in the Trials hall: press T in the overworld."
            return
        self.trial_selected = min(count - 1, row * TRIAL_COLUMNS + col)

    def trial_record(self, monster):
        return self.trial_records.get(monster.id) or {"rank": 0, "wins": 0, "losses": 0}

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
    def _draw_tabs(self, surface):
        x = 12
        for index, name in enumerate(PAGES):
            active = index == self.page
            width = 58 if index == 0 else 48
            pygame.draw.rect(surface, PALETTE["gold"] if active else PALETTE["night"], (x, 5, width, 15))
            text(surface, name, (x + width // 2, 12), 11 if active else 9,
                 PALETTE["ink"] if active else PALETTE["muted"], center=True)
            x += width + 4

    def draw(self, surface, frame=0):
        surface.fill(PALETTE["deep"])
        self._draw_tabs(surface)
        if self.page == 1:
            self._draw_trials(surface, frame)
            return
        text(surface, f"CAPTURED {len(self.friends & {s.name for s in WILD})}/{len(WILD)}  "
                      f"SEEN {len(self.seen & {s.name for s in WILD})}/{len(WILD)}",
             (308, 9), 10, PALETTE["cream"], align="right")
        entries = self.entries()
        rows = (len(entries) + COLUMNS - 1) // COLUMNS
        # One row of tall cards, or compact cards when the collection needs two rows.
        card_h = CARD_H if rows == 1 else 58
        sprite_h, sprite_y, name_y = (44, 80, 92) if rows == 1 else (30, 40, 47)
        for index, spec in enumerate(entries):
            col, row = index % COLUMNS, index // COLUMNS
            x, y = 12 + col * (CARD_W + 6), 28 + row * (card_h + 4)
            chosen = index == self.selected
            partner = spec is self.partner
            friend, seen = partner or spec.name in self.friends, partner or spec.name in self.seen
            border = PALETTE["gold"] if chosen else (PALETTE["mint"] if friend else PALETTE["night"])
            panel(surface, (x, y, CARD_W, card_h), PALETTE["night"] if friend else PALETTE["ink"], border)
            bob = (frame // 15) % 2 if chosen and friend else 0
            tint = None if friend else ((52, 66, 86) if seen else (32, 40, 58))
            pose = "happy" if chosen and friend and (frame // 40) % 3 == 2 else "idle"
            surface.set_clip((x + 2, y + 2, CARD_W - 4, card_h - 4))  # wide creatures stay inside their card
            draw_creature(surface, spec, (x + CARD_W // 2, y + sprite_y - bob), sprite_h, pose, tint=tint)
            surface.set_clip(None)
            pygame.draw.rect(surface, TOPIC_COLORS.get(spec.topic, PALETTE["muted"]), (x + 5, y + card_h - 6, CARD_W - 10, 2))
            member = self.player if partner else self.team.find(spec.name)
            label = (f"{spec.name[:9]} {member.level}" if member and rows > 1 else
                     f"{spec.name}  Lv {member.level}" if member else spec.name) if seen else "???"
            text(surface, label, (x + CARD_W // 2, y + name_y), 10 if rows == 1 else 8,
                 PALETTE["white"] if friend else PALETTE["muted"], center=True)
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
            wrapped(surface, spec.blurb, (16, 172, 288, 10), 10, PALETTE["white"], 11, 1)
            nemesis = NEMESIS.get(lineage(spec))
            beats = ", ".join(strong_against(spec.name)) or "-"
            text(surface, f"NEMESIS: {nemesis or '-'}", (16, 186), 9, PALETTE["coral"])
            text(surface, f"STRONG VS: {beats}", (304, 186), 9, PALETTE["mint"], align="right")
        elif spec.rarity == 0:
            text(surface, "??? - SECRET", (16, 157), 13, (190, 150, 255))
            wrapped(surface, "Something travels on straight lines among the stars. Finish the Star Chart in the "
                    "Crystal Realm...", (16, 172, 288, 20), 10, PALETTE["muted"], 11, 2)
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
        footer = self.notice or "ARROWS: BROWSE   ENTER: CHOOSE LEADER   Q/E: TRIALS PAGE   ESC: BACK"
        text(surface, footer, (160, 226), 9, PALETTE["gold"] if self.notice else PALETTE["cream"], center=True)

    # -------------------------------------------------------------- trials page
    def _draw_trials(self, surface, frame):
        from battle_engine.progression import RANK_NAMES, is_unlocked, unlock_text
        from battle_engine.tiers import tier_by_id
        from mathematics.question_engine import topic_label
        monsters, records = self.trial_monsters, self.trial_records
        beaten = sum(1 for m in monsters if self.trial_record(m)["wins"])
        mastered = sum(1 for m in monsters if self.trial_record(m)["rank"] >= 5)
        text(surface, f"DEFEATED {beaten}/{len(monsters)}  MASTERED {mastered}/{len(monsters)}", (308, 9), 10,
             PALETTE["cream"], align="right")
        for index, monster in enumerate(monsters):
            col, row = index % TRIAL_COLUMNS, index // TRIAL_COLUMNS
            x, y = 12 + col * (TRIAL_W + 4), 26 + row * (TRIAL_H + 4)
            record = self.trial_record(monster)
            chosen = index == self.trial_selected
            locked = not is_unlocked(monster, records)
            won = record["wins"] > 0
            home = tier_by_id(monster.rarity)
            border = PALETTE["gold"] if chosen else (home.color if won else PALETTE["night"])
            panel(surface, (x, y, TRIAL_W, TRIAL_H), PALETTE["night"] if won else PALETTE["ink"], border)
            if monster_sprites.available(monster.sprite):
                pose = ("idle", "idle2", "idle3", "idle2")[(frame // 15) % 4] if chosen and won else "idle"
                tint = None if won else ((32, 40, 58) if locked else (52, 66, 86))
                surface.set_clip((x + 2, y + 2, TRIAL_W - 4, TRIAL_H - 4))
                monster_sprites.draw(surface, monster.sprite, (x + TRIAL_W // 2, y + 44), 30, pose, tint=tint)
                surface.set_clip(None)
            label = "???" if locked else monster.name.upper()[:10]
            text(surface, label, (x + TRIAL_W // 2, y + 50), 7, PALETTE["white"] if won else PALETTE["muted"],
                 center=True)
            for star in range(5):
                pygame.draw.rect(surface, PALETTE["gold"] if star < record["rank"] else PALETTE["deep"],
                                 (x + 4 + star * 5, y + 4, 4, 4))
        monster = monsters[self.trial_selected]
        record = self.trial_record(monster)
        locked = not is_unlocked(monster, records)
        won = record["wins"] > 0
        home = tier_by_id(monster.rarity)
        panel(surface, (8, 152, 304, 62), PALETTE["night"], home.color if won else PALETTE["cream"])
        if locked:
            text(surface, "??? - SECRET BOSS", (16, 157), 13, (190, 150, 255))
            wrapped(surface, unlock_text(monster, records), (16, 172, 288, 20), 10, PALETTE["muted"], 11, 2)
        else:
            text(surface, monster.name.upper(), (16, 157), 13, tuple(monster.color) if won else PALETTE["muted"])
            text(surface, f"{home.name.upper()}  •  {topic_label(monster.math_speciality).upper()}", (304, 159), 9,
                 home.color, align="right")
            wrapped(surface, monster.special_ability, (16, 172, 288, 10), 9,
                    PALETTE["white"] if won else PALETTE["muted"], 10, 1)
            weak = ", ".join(topic_label(t) for t in monster.weakness)
            text(surface, f"WEAK: {weak}", (16, 186), 9, PALETTE["mint"])
            text(surface, "MASTERY: " + RANK_NAMES[record["rank"]].upper(), (304, 186), 9, PALETTE["gold"],
                 align="right")
            if won:
                best = record.get("best_turns") or "-"
                status = f"Wins {record['wins']}   Losses {record['losses']}   Best: {best} turns"
                if record["rank"] < 5:
                    status += "   Next: " + RANK_NAMES[record["rank"] + 1] + " tier"
                color = PALETTE["cream"]
            else:
                status, color = "Not defeated yet. Challenge it in the Trials hall (press T outside).", PALETTE["muted"]
            text(surface, status, (16, 199), 9, color)
        footer = self.notice or "ARROWS: BROWSE   Q/E: MATHDEX PAGE   ESC / M: BACK"
        text(surface, footer, (160, 226), 9, PALETTE["gold"] if self.notice else PALETTE["cream"], center=True)

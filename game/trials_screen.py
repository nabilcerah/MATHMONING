"""Monster Trials: the collection and challenge hall for the advanced monster battles.

Shows every data-driven monster with its live idle animation (the selected one walks), its
mastery rank (the stars), lock status, speciality, weakness and signature mechanic. Choose a
tier with Q/E and press ENTER to battle. Closing with a choice sets ``self.challenge``.
"""
import pygame

from battle_engine.monster_data import load_all
from battle_engine.progression import ProgressStore, RANK_NAMES, available_ranks, is_unlocked, unlock_text, xp_to_next
from battle_engine.skills import unlocked
from battle_engine.tiers import level_for_rank, tier_by_id, tiers
from config import PALETTE
from game.animation import SpriteAnimator
from game.team import Team
from game.ui import meter, panel, text, wrapped
from mathematics.question_engine import topic_label

COLUMNS = 4
CARD_W, CARD_H = 75, 46


class TrialsScreen:
    def __init__(self, repository, player, team=None):
        self.repository, self.player = repository, player
        self.team = team or Team(repository, player)
        self.store = ProgressStore(repository, player.player_id)
        self.monsters = list(load_all().values())
        self.animators = {m.id: SpriteAnimator(m.sprite) for m in self.monsters}
        self.selected = 0
        self.rank_choice = {}
        self.closed = False
        self.challenge = None
        self.notice = ""
        self.refresh()

    def refresh(self):
        self.trainer = self.store.trainer()
        self.records = self.store.records()
        self.fighter = self.team.leader()

    def record(self, monster):
        return self.records.get(monster.id) or {"rank": 0, "wins": 0, "losses": 0}

    def ranks(self, monster):
        return available_ranks(monster, self.record(monster))

    def chosen_rank(self, monster):
        ranks = self.ranks(monster)
        rank = self.rank_choice.get(monster.id, ranks[-1])
        return rank if rank in ranks else ranks[-1]

    def player_level(self):
        return max(self.fighter.level, self.trainer.level)

    # ------------------------------------------------------------------ input
    def handle_key(self, key):
        monster = self.monsters[self.selected]
        col, row = self.selected % COLUMNS, self.selected // COLUMNS
        rows = (len(self.monsters) + COLUMNS - 1) // COLUMNS
        if key in (pygame.K_ESCAPE, pygame.K_t):
            self.closed = True
            return
        if key in (pygame.K_LEFT, pygame.K_a):
            col = (col - 1) % COLUMNS
        elif key in (pygame.K_RIGHT, pygame.K_d):
            col = (col + 1) % COLUMNS
        elif key in (pygame.K_UP, pygame.K_w):
            row = (row - 1) % rows
        elif key in (pygame.K_DOWN, pygame.K_s):
            row = (row + 1) % rows
        elif key in (pygame.K_q, pygame.K_e, pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
            ranks = self.ranks(monster)
            index = ranks.index(self.chosen_rank(monster)) + (1 if key in (pygame.K_e, pygame.K_RIGHTBRACKET) else -1)
            self.rank_choice[monster.id] = ranks[index % len(ranks)]
            return
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            if not is_unlocked(monster, self.records):
                self.notice = unlock_text(monster, self.records)
                return
            self.challenge = (monster.id, self.chosen_rank(monster))
            self.closed = True
            return
        self.selected = min(len(self.monsters) - 1, row * COLUMNS + col)
        self.notice = ""

    def update(self):
        for monster_id, animator in self.animators.items():
            want = "walk" if monster_id == self.monsters[self.selected].id else "idle"
            if animator.animation != want:
                animator.play(want, loop=True)
            animator.update()

    # ------------------------------------------------------------------ draw
    def draw(self, surface, frame=0):
        surface.fill((22, 26, 46))
        text(surface, "MONSTER TRIALS", (8, 3), 13, PALETTE["gold"])
        trainer = self.trainer
        text(surface, f"TRAINER Lv {trainer.level}", (200, 4), 9, PALETTE["white"])
        meter(surface, 262, 5, 52, 6, trainer.xp, xp_to_next(trainer.level), PALETTE["sky"])
        for index, monster in enumerate(self.monsters):
            self._card(surface, monster, index, frame)
        self._details(surface, self.monsters[self.selected])
        footer = self.notice or "ARROWS: CHOOSE   Q/E: TIER   ENTER: BATTLE   T/ESC: BACK"
        text(surface, footer, (160, 233), 7, PALETTE["coral"] if self.notice else PALETTE["cream"], center=True)

    def _card(self, surface, monster, index, frame):
        col, row = index % COLUMNS, index // COLUMNS
        x, y = 6 + col * (CARD_W + 3), 16 + row * (CARD_H + 2)
        chosen = index == self.selected
        record = self.record(monster)
        home = tier_by_id(monster.rarity)
        locked = not is_unlocked(monster, self.records)
        panel(surface, (x, y, CARD_W, CARD_H), PALETTE["night"] if not locked else PALETTE["ink"],
              PALETTE["gold"] if chosen else home.color)
        surface.set_clip((x + 2, y + 2, CARD_W - 4, CARD_H - 4))
        tint = (40, 40, 60) if locked else (None if record["wins"] else (70, 80, 110) if not chosen else None)
        animator = self.animators[monster.id]
        if animator.available:
            animator.draw(surface, (x + CARD_W // 2, y + CARD_H - 11), 26, tint=tint)
        surface.set_clip(None)
        text(surface, monster.name.upper() if not locked else "???", (x + 4, y + 3), 7,
             PALETTE["white"] if not locked else PALETTE["muted"])
        for star in range(5):
            filled = star < record["rank"]
            pygame.draw.rect(surface, PALETTE["gold"] if filled else PALETTE["deep"],
                             (x + 4 + star * 5, y + CARD_H - 7, 4, 4))
        text(surface, home.name[:4].upper(), (x + CARD_W - 4, y + CARD_H - 9), 6, home.color, align="right")

    def _details(self, surface, monster):
        record = self.record(monster)
        locked = not is_unlocked(monster, self.records)
        rank = self.chosen_rank(monster)
        tier = tiers()[rank - 1]
        level = level_for_rank(rank, self.player_level())
        panel(surface, (6, 162, 308, 64), PALETTE["night"], tier.color)
        if locked:
            text(surface, "??? - LOCKED", (12, 166), 11, PALETTE["muted"])
            wrapped(surface, unlock_text(monster, self.records), (12, 180, 296, 20), 9, PALETTE["cream"], 10, 2)
            return
        text(surface, f"{monster.name.upper()}", (12, 165), 11, tuple(monster.color))
        text(surface, f"{topic_label(monster.math_speciality).upper()} SPECIALIST", (100, 167), 7, PALETTE["muted"])
        weak = ", ".join(topic_label(t) for t in monster.weakness)
        text(surface, f"WEAK: {weak}", (308, 167), 7, PALETTE["mint"], align="right")
        wrapped(surface, monster.special_ability, (12, 177, 296, 18), 8, PALETTE["white"], 9, 2)
        wrapped(surface, monster.defence_style, (12, 196, 296, 9), 7, PALETTE["sky"], 8, 1)
        mastery = RANK_NAMES[record["rank"]]
        text(surface, f"MASTERY: {mastery}   WINS {record['wins']}", (12, 208), 7, PALETTE["gold"])
        ranks = self.ranks(monster)
        arrows = ("< " if len(ranks) > 1 else "") + f"{tier.name.upper()} TIER  Lv {level}" + (" >" if len(ranks) > 1 else "")
        pygame.draw.rect(surface, tier.color, (186, 206, 124, 11))
        text(surface, arrows, (248, 211), 8, PALETTE["ink"], center=True)
        warn = level - self.fighter.level
        if warn >= 6:
            text(surface, f"Tough! Your leader is Lv {self.fighter.level}.", (308, 197), 7, PALETTE["coral"], align="right")
        skills = len(unlocked(self.trainer.level))
        text(surface, f"SKILLS {skills}/5", (130, 208), 7, PALETTE["muted"])

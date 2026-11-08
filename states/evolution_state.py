"""The EVOLUTION SHRINE (GDD 9.5). Shows each party monster's requirements (level AND maths
mastery with enough evidence), previews the change, and evolves only when the player confirms."""
import pygame

from config import PALETTE
from game.creatures import draw_creature
from game.ui import panel, text, wrapped
from monsters import evolution_manager
from monsters.monster_data import move as move_data
from states.base import CONFIRM, Screen


class EvolutionScreen(Screen):
    def __init__(self, game):
        super().__init__(game)
        self.profile = self.repo.learning_profile(self.player_id)
        self.confirming = False
        self.celebrate = 0

    def items(self):
        return self.party.party

    def rows(self):
        return 34, 18, 4, 110

    def check(self, monster):
        return evolution_manager.check(monster, self.profile)

    def activate(self, index):
        monster = self.party.party[index]
        result = self.check(monster)
        if not result.eligible:
            self.notice = "Not yet: " + "; ".join(result.missing)[:68]
            return
        self.confirming = True

    def handle_key(self, key, unicode=""):
        if self.confirming:
            if key in CONFIRM or key == pygame.K_y:
                self.evolve()
            elif key in (pygame.K_ESCAPE, pygame.K_n):
                self.confirming = False
                self.notice = "Maybe later. You can come back any time."
            return
        super().handle_key(key, unicode)

    def evolve(self):
        monster = self.party.party[self.selected]
        before = monster.name
        evolution_manager.evolve(monster)
        from game import audio
        audio.play("evolve")
        self.game.after_evolution(monster)
        self.confirming = False
        self.celebrate = 120
        self.notice = f"{before} evolved into {monster.name}!"

    def update(self):
        if self.celebrate:
            self.celebrate -= 1

    def draw(self, surface, frame=0):
        self.draw_frame(surface, "EVOLUTION SHRINE", PALETTE["sky"],
                        "ENTER: CHECK / EVOLVE   ESC: LEAVE" if not self.confirming else "ENTER/Y: EVOLVE NOW   N/ESC: NOT YET")
        labels = [f"{m.name} Lv{m.level}" for m in self.party.party]
        self.draw_list(surface, labels, frame, 34, 18, 4, 106)
        for index, monster in enumerate(self.party.party):
            ready = self.check(monster).eligible
            text(surface, "READY" if ready else "", (108, 34 + index * 18), 8, PALETTE["mint"], align="right")
        monster = self.party.party[min(self.selected, len(self.party.party) - 1)]
        result = self.check(monster)
        panel(surface, (114, 30, 202, 182), PALETTE["night"], PALETTE["sky"] if result.eligible else None)
        if not result.target:
            text(surface, f"{monster.name} has no further stage yet.", (120, 40), 9, PALETTE["muted"])
            return
        info = evolution_manager.preview(monster) if result.eligible or self.celebrate == 0 else None
        target = evolution_manager.preview(monster)["to"] if result.target and monster.spec.evolution else None
        if self.celebrate:
            flash = (frame // 4) % 2
            draw_creature(surface, monster.spec, (215, 110), 64, "happy", tint=PALETTE["white"] if flash and self.celebrate > 80 else None)
            text(surface, f"{monster.name}!", (215, 120), 16, PALETTE["gold"], center=True)
            wrapped(surface, "Its level, EXP and learning records are kept. New colours, stronger stats and an "
                             "evolved move!", (120, 140, 190, 50), 9, PALETTE["white"], 10, 5)
            return
        draw_creature(surface, monster.spec, (160, 86), 44, "idle")
        text(surface, ">", (215, 64), 18, PALETTE["gold"], center=True)
        if target is not None:
            silhouette = None if result.eligible else PALETTE["ink"]
            draw_creature(surface, target, (268, 86), 44, "idle", tint=silhouette)
            text(surface, target.name if result.eligible else "???", (268, 90), 9, PALETTE["gold"], center=True)
        y = 104
        text(surface, "REQUIREMENTS (level AND mastery)", (120, y), 8, PALETTE["gold"])
        for label, met in result.requirements:
            y += 11
            text(surface, ("+ " if met else "- ") + label, (120, y), 8, PALETTE["mint"] if met else PALETTE["coral"])
        if result.eligible and info:
            y += 14
            for stat, (old, new) in info["stats"].items():
                text(surface, f"{stat.upper()[:3]} {old}->{new}", (120 + (list(info["stats"]).index(stat) % 2) * 96,
                                                                    y + (list(info["stats"]).index(stat) // 2) * 10),
                     8, PALETTE["white"])
            y += 22
            gained = ", ".join(move_data(m).name for m in info["gained_moves"])
            text(surface, f"New move: {gained}  (+{info['power_bonus']} power)", (120, y), 8, PALETTE["sky"])
        if self.confirming:
            panel(surface, (60, 96, 200, 40), PALETTE["ink"], PALETTE["gold"])
            text(surface, f"Evolve {monster.name} now?", (160, 108), 12, PALETTE["gold"], center=True)
            text(surface, "ENTER/Y: YES     N: NOT YET", (160, 124), 9, PALETTE["white"], center=True)

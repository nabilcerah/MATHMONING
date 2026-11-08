"""Galaxion's gravity field.

Gravity rises each round (to ``max``). It weakens your hits, strengthens its attacks, and makes the
questions harder (+1 level per ``level_per`` gravity). Each correct answer pushes gravity down by one
and permanently weakens Galaxion's defence - big numbers mastered, big monster weakened.
"""
from battle_engine.events import Badge, Event
from battle_engine.mechanics.base import Mechanic


class GravityField(Mechanic):
    TYPE = "gravity"

    def __init__(self, engine, params):
        super().__init__(engine, params)
        self.gravity = int(self.p("start", 1))
        self.weaken = 0
        # Lower tiers have a lighter field: max gravity = 2 + tier rank (capped by the JSON "max").
        self.max = min(int(self.p("max", 5)), 2 + engine.tier.rank)

    def question_level_offset(self):
        return min(int(self.p("max_level_offset", 1)), self.gravity // int(self.p("level_per", 2)))

    def modify_hit(self, hit, question, correct, request, elapsed):
        if self.gravity:
            hit.extras.append(("Gravity field", max(0.4, 1 - self.p("reduction", 0.07) * self.gravity)))
        if self.weaken:
            hit.defence *= max(0.3, 1 - self.p("weaken_step", 0.08) * self.weaken)

    def after_answer(self, question, correct, hit, request, forgiven):
        if not correct:
            return []
        self.gravity = max(0, self.gravity - 1)
        self.weaken += 1
        return [Event("gravity", f"Your answer pushes the gravity field down to G{self.gravity}. "
                                 f"{self.name}'s defence weakens ({self.weaken}).",
                      {"gravity": self.gravity, "weaken": self.weaken})]

    def modify_monster_hit(self, hit, ability):
        if self.gravity:
            hit.extras.append(("Gravity", 1 + self.p("attack_per_level", 0.08) * self.gravity))

    def end_round(self):
        if self.gravity >= self.max:
            return []
        self.gravity += 1
        return [Event("gravity", f"Gravity intensifies: G{self.gravity}. The numbers grow heavier...",
                      {"gravity": self.gravity})]

    def badges(self):
        color = "coral" if self.gravity >= 4 else "gold" if self.gravity >= 2 else "mint"
        return [Badge("GRAVITY", f"G{self.gravity}/{self.max}", color,
                      "Higher gravity: weaker hits, harder numbers. Correct answers push it down.")]

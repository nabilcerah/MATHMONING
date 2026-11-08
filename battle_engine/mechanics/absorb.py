"""Nullshade's Energy Absorption: wrong answers feed it.

Each wrong answer adds a Void stack (+attack, and a little healing). Correct integer answers drain
a stack. At ``burst_at`` stacks it can release Void Pulse (effect "void_pulse"), spending them all.
"""
from battle_engine.events import Badge, Event
from battle_engine.mechanics.base import Mechanic
from mathematics.question_engine import canonical_topic


class EnergyAbsorb(Mechanic):
    TYPE = "absorb"
    EFFECTS = ("void_pulse",)

    def __init__(self, engine, params):
        super().__init__(engine, params)
        self.stacks = 0
        self.drain_topics = {canonical_topic(t) for t in self.p("drain_topics", ("negative_numbers",))}

    def after_answer(self, question, correct, hit, request, forgiven):
        engine = self.engine
        if not correct and not forgiven:
            if self.stacks >= self.p("max_stacks", 5):
                return []
            self.stacks += 1
            heal = round(engine.monster_max_hp * self.p("heal_fraction", 0.04))
            floor_hp = engine.monster_hp
            engine.monster_hp = min(engine.monster_max_hp, engine.monster_hp + heal)
            healed = engine.monster_hp - floor_hp
            return [Event("absorb", f"{self.name} absorbs the energy of the wrong answer: Void {self.stacks}"
                                    f" (+{healed} HP).", {"stacks": self.stacks, "heal": healed})]
        if correct and self.stacks and canonical_topic(question.topic) in self.drain_topics:
            self.stacks -= 1
            return [Event("absorb_drain", f"Your correct answer drains a Void stack ({self.stacks} left).",
                          {"stacks": self.stacks})]
        return []

    def modify_monster_hit(self, hit, ability):
        if self.stacks:
            hit.extras.append(("Void energy", 1 + self.p("attack_per_stack", 0.12) * self.stacks))

    def ability_score(self, ability):
        return 6.0 if self.stacks >= self.p("burst_at", 3) else None

    def perform(self, effect, ability):
        stacks, self.stacks = self.stacks, 0
        events = [Event("special", f"{self.name} releases VOID PULSE, powered by {stacks} wrong answers!",
                        {"effect": "void_pulse"})]
        return events + self.engine.monster_attack(ability, ability.power + 0.2 * stacks, "Void Pulse")

    def badges(self):
        color = "coral" if self.stacks >= self.p("burst_at", 3) else "gold" if self.stacks else "muted"
        return [Badge("VOID", f"{self.stacks}/{self.p('max_stacks', 5)}", color,
                      "Wrong answers feed it. Correct negative-number answers drain it.")]

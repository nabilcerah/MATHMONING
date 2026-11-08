"""Smaller mechanics: Voltbyte's fast strikes and Infinity Zero's rule shifts."""
from battle_engine.events import Badge, Event
from battle_engine.mechanics.base import Mechanic


class FastStrikes(Mechanic):
    """A very fast monster lands an extra quick jab every few rounds (never while charging or stunned)."""
    TYPE = "fast_strikes"

    def __init__(self, engine, params):
        super().__init__(engine, params)
        self.rounds = 0

    def end_round(self):
        engine = self.engine
        self.rounds += 1
        if engine.outcome or engine.stunned or engine.pending or engine.monster_hp <= 0:
            return []
        if self.rounds % int(self.p("every", 2)):
            return []
        return [Event("fast", f"{self.name} is too fast! An extra Quick Strike.")] + \
            engine.monster_attack(None, self.p("power", 0.45), "Quick Strike")

    def badges(self):
        every = int(self.p("every", 2))
        left = every - self.rounds % every
        return [Badge("SPEED", f"extra hit in {left}", "gold", "Interrupt its charges to keep it from snowballing.")]


class RuleShift(Mechanic):
    """Each phase rewrites a rule of the battle (number of options, typed-only answers...)."""
    TYPE = "rule_shift"

    def _rule(self):
        return self.p("rules", {}).get(self.engine.phase.current.get("id"), {})

    def on_phase(self, phase):
        rule = self.p("rules", {}).get(phase.get("id"), {})
        if rule.get("text"):
            return [Event("rule", f"NEW RULE: {rule['text']}", {"phase": phase.get("id")})]
        return []

    def choice_count(self, count):
        return int(self._rule().get("choices", count))

    def typed_only(self):
        return bool(self._rule().get("typed_only", False))

    def badges(self):
        rule = self._rule()
        if rule.get("short"):
            return [Badge("RULE", rule["short"], "coral", rule.get("text", ""))]
        return []

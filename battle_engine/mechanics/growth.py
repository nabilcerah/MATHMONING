"""Power that builds up every turn.

``linear`` (Infermath's heat): attack x (1 + step x stacks).
``exponential`` (Hexabyte): attack x base^stacks - the badge shows the power, e.g. 1.3^3 = 2.20.
Correct answers on ``reset_topics`` drop the stacks to 0; other correct answers remove
``reduce_on_correct`` stacks.
"""
from battle_engine.events import Badge, Event
from battle_engine.mechanics.base import Mechanic
from mathematics.question_engine import canonical_topic, topic_label


class Growth(Mechanic):
    TYPE = "growth"

    def __init__(self, engine, params):
        super().__init__(engine, params)
        self.stacks = int(self.p("start", 0))
        self.label = self.p("name", "Power")
        self.reset_topics = {canonical_topic(t) for t in self.p("reset_topics", ())}

    @property
    def exponential(self):
        return self.p("mode", "linear") == "exponential"

    @property
    def multiplier(self):
        if self.exponential:
            return float(self.p("base", 1.3)) ** self.stacks
        return 1 + float(self.p("step", 0.15)) * self.stacks

    def formula(self):
        if self.exponential:
            return f"{self.p('base', 1.3)}^{self.stacks} = {self.multiplier:.2f}"
        return f"1 + {self.p('step', 0.15)} x {self.stacks} = {self.multiplier:.2f}"

    def modify_monster_hit(self, hit, ability):
        applies = self.p("applies_to", ())
        if applies and getattr(ability, "id", "") not in applies:
            return
        if self.stacks:
            hit.extras.append((self.label, self.multiplier))

    def end_round(self):
        if self.engine.stunned and self.p("pause_when_stunned", True):
            return []
        if self.stacks >= self.p("max_stacks", 6):
            return []
        self.stacks += 1
        return [Event("growth", f"{self.name}'s {self.label} grows: {self.formula()}x power.",
                      {"stacks": self.stacks, "mult": self.multiplier})]

    def after_answer(self, question, correct, hit, request, forgiven):
        if not correct or not self.stacks:
            return []
        if request.purpose == "interrupt" and self.p("halve_on_interrupt", False):
            self.stacks //= 2
            return [Event("growth_reset", f"Interrupting the charge smothers the {self.label}: {self.formula()}x.",
                          {"stacks": self.stacks})]
        topic = canonical_topic(question.topic)
        if topic in self.reset_topics:
            self.stacks = 0
            return [Event("growth_reset", f"Your {topic_label(topic)} answer collapses {self.name}'s {self.label} "
                                          f"back to {self.formula()}x!", {"stacks": 0})]
        drop = int(self.p("reduce_on_correct", 1))
        if drop:
            self.stacks = max(0, self.stacks - drop)
            return [Event("growth_reset", f"Your correct answer cools {self.name}'s {self.label} to {self.formula()}x.",
                          {"stacks": self.stacks})]
        return []

    def badges(self):
        color = "coral" if self.multiplier >= 2 else "gold" if self.stacks else "muted"
        tip = (f"Solve {'/'.join(topic_label(t) for t in sorted(self.reset_topics))} to reset it."
               if self.reset_topics else "Correct answers cool it down.")
        return [Badge(self.label.upper(), f"x{self.multiplier:.2f}", color, f"{self.formula()}. {tip}")]

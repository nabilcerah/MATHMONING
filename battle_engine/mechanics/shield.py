"""Shields with their own HP (Crystalgon's Crystal Shield, Equinox's Energy Shield, Infinity Zero's
Paradox Barrier).

- While up, most of a hit goes into the shield; only ``leak`` of it reaches the monster.
- Answers on the ``break_topics`` (default: the monster's weakness) hit the shield harder.
  With ``only_break_topics`` other topics cannot dent it at all (Equinox: only equations work).
- Wrong answers let the monster repair it (``regen_on_wrong`` of its max).
- Breaking it stuns the monster; it may raise the shield again later (effect "raise_shield").
"""
from battle_engine.events import Badge, Event
from battle_engine.mechanics.base import Mechanic
from mathematics.question_engine import canonical_topic, topic_label


class Shield(Mechanic):
    TYPE = "shield"
    EFFECTS = ("raise_shield",)

    def __init__(self, engine, params):
        super().__init__(engine, params)
        self.label = self.p("name", "Shield")
        self.max_hp = max(1, round(engine.monster_max_hp * self.p("hp_ratio", 0.25)))
        self.hp = 0
        self.turns_down = 0
        topics = self.p("break_topics", None) or sorted(engine.weakness_topics())
        self.break_topics = {canonical_topic(t) for t in topics}

    @property
    def up(self):
        return self.hp > 0

    def setup(self):
        return self._raise() if self.p("start_up", True) else []

    def on_phase(self, phase):
        if phase.get("id") in self.p("raise_on_phases", ()):
            return self._raise()
        return []

    def _raise(self):
        self.hp = self.max_hp
        self.turns_down = 0
        topics = " or ".join(topic_label(t) for t in sorted(self.break_topics))
        return [Event("shield_up", f"{self.name} raises its {self.label} ({self.max_hp} HP). {topics} answers crack it!",
                      {"hp": self.hp})]

    def absorb(self, hit, question, correct, request):
        if not self.up or not correct or hit.raw <= 0:
            return []
        topic = canonical_topic(question.topic)
        tags = {canonical_topic(t) for t in question.tags}
        breaker = topic in self.break_topics or bool(tags & self.break_topics)
        if breaker:
            to_shield = hit.raw * self.p("break_mult", 1.5) * hit.shield_mult
        elif self.p("only_break_topics", False):
            to_shield = 0
            hit.notes.append(f"Only {' / '.join(topic_label(t) for t in sorted(self.break_topics))} can crack the {self.label}.")
        else:
            to_shield = hit.raw * self.p("other_mult", 0.6) * hit.shield_mult
        to_shield = round(to_shield)
        leak = round(hit.raw * self.p("leak", 0.25))
        hit.to_shield = min(self.hp, to_shield)
        hit.blocked = max(0, hit.raw - leak)
        hit.to_hp = leak
        self.hp -= hit.to_shield
        events = [Event("shield_hit", f"The {self.label} absorbs the blow (-{hit.to_shield} shield).",
                        {"amount": hit.to_shield, "hp": self.hp})]
        if breaker:
            hit.notes.append(f"{topic_label(topic)} cracks the {self.label} (x{self.p('break_mult', 1.5)}).")
        if self.hp <= 0:
            self.hp = 0
            stun = int(self.p("stun_on_break", 1))
            self.engine.stunned = max(self.engine.stunned, stun)
            events.append(Event("shield_break", f"The {self.label} SHATTERS! {self.name} is stunned." if stun
                                else f"The {self.label} shatters!"))
        return events

    def after_answer(self, question, correct, hit, request, forgiven):
        if correct or forgiven or not self.up:
            return []
        regen = round(self.max_hp * self.p("regen_on_wrong", 0.1))
        if not regen or self.hp >= self.max_hp:
            return []
        self.hp = min(self.max_hp, self.hp + regen)
        return [Event("shield_up", f"The wrong answer lets {self.name} repair its {self.label} (+{regen}).",
                      {"hp": self.hp, "regen": regen})]

    def ability_score(self, ability):
        if self.up or self.turns_down < self.p("raise_cooldown", 3):
            return None
        return 4.0

    def perform(self, effect, ability):
        return self._raise()

    def end_round(self):
        if not self.up:
            self.turns_down += 1
        return []

    def badges(self):
        if self.up:
            topics = "/".join(topic_label(t) for t in sorted(self.break_topics))
            return [Badge(self.label.upper(), f"{self.hp}/{self.max_hp}", "sky", f"Use {topics} to break it.")]
        return [Badge(self.label.upper(), "BROKEN", "muted", "Hit hard before it is raised again!")]

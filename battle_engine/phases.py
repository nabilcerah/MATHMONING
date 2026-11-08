"""Battle phases. A phase begins when the monster's HP falls to its ``hp_below`` fraction.

A single answer can never skip a phase: damage stops at the threshold and the new phase begins.
Phases can change the question topics and difficulty, the monster's attack, how many attacks it
makes per turn, and which mechanics are switched on (e.g. Infinity Zero's Paradox barrier).
"""
from battle_engine.events import Event
from battle_engine.monster_data import tier_allows


class PhaseController:
    def __init__(self, engine):
        self.engine = engine
        phases = [p for p in engine.defn.phases if tier_allows(p.get("min_tier", "common"), engine.tier.id, engine.balance)]
        self.phases = phases or [{"id": "normal", "name": "", "hp_below": 1.0}]
        self.index = 0

    @property
    def current(self):
        return self.phases[self.index]

    @property
    def has_next(self):
        return self.index + 1 < len(self.phases)

    @property
    def named(self):
        return len(self.phases) > 1 or bool(self.current.get("name"))

    def next_threshold_hp(self):
        if not self.has_next:
            return None
        return max(1, round(self.phases[self.index + 1]["hp_below"] * self.engine.monster_max_hp))

    def level_offset(self):
        return int(self.current.get("question_level_offset", 0))

    def topics(self):
        return tuple(self.current.get("question_topics") or self.engine.defn.question_topics)

    def attacks_per_turn(self):
        return int(self.current.get("attacks_per_turn", 1))

    def attack_mult(self):
        return float(self.current.get("attack_mult", 1.0))

    def allows(self, ability):
        return not ability.phases or self.current.get("id") in ability.phases

    def enter_first(self):
        return self._apply(self.current, first=True)

    def advance(self):
        self.index += 1
        return self._apply(self.current)

    def _apply(self, phase, first=False):
        engine = self.engine
        for mechanic in engine.mechanics:
            if mechanic.TYPE in phase.get("enable", ()):
                mechanic.active = True
            if mechanic.TYPE in phase.get("disable", ()):
                mechanic.active = False
        events = []
        if not first:
            engine.pending = None  # a phase shift breaks any attack being charged
            engine.stunned = 0
            events.append(Event("phase", phase.get("intro", f"{engine.defn.name} enters {phase.get('name', 'a new phase')}!"),
                                {"phase": phase.get("id"), "name": phase.get("name", ""), "tint": phase.get("tint")}))
        elif phase.get("name"):
            events.append(Event("phase", phase.get("intro", f"Phase 1: {phase['name']}."),
                                {"phase": phase.get("id"), "name": phase["name"], "tint": phase.get("tint"), "first": True}))
        for mechanic in engine.mechanics:
            if mechanic.active:
                events += mechanic.on_phase(phase) or []
        return events

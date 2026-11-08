"""Chronowl's time and sequence mechanics.

- Attack pattern: its moves follow a repeating sequence shown in the UI (a pattern to read).
- Prediction: if you attack with the same topic twice in a row it foresees it (damage halved).
- Time Lock (effect "time_lock"): the next question is a sequence with a generous time window.
  Answering inside it gives a Rewind Strike (x1.5). Missing the window only loses the bonus - the
  answer still counts, so the battle never depends on reaction speed alone.
"""
from battle_engine.events import Badge, Event, QuestionRequest
from battle_engine.mechanics.base import Mechanic
from battle_engine.monster_ai import AIState, Decision
from battle_engine.monster_data import AbilityDef
from mathematics.question_engine import topic_label

PATTERN_MOVE = AbilityDef("pattern_move", "Time Pattern", "special", effect="pattern_attack")


class Timeline(Mechanic):
    TYPE = "timeline"
    EFFECTS = ("pattern_attack", "time_lock")

    def __init__(self, engine, params):
        super().__init__(engine, params)
        self.pattern = list(self.p("pattern", ()))
        self.index = 0
        self.armed = False

    def window_seconds(self):
        table = self.engine.balance["time_window_seconds"]
        return table[min(len(table), self.engine.tier.rank) - 1]

    def upcoming(self, count=4):
        if not self.pattern:
            return []
        return [self.engine.defn.ability(self.pattern[(self.index + i) % len(self.pattern)]) for i in range(count)]

    # -- time lock ------------------------------------------------------------------
    def forces_question(self):
        return self.armed

    def question_request(self):
        if not self.armed:
            return None
        return QuestionRequest("time", self.p("time_topic", "sequences"), time_limit=self.window_seconds(),
                               label=f"TIME WINDOW: {self.window_seconds()}s FOR A REWIND STRIKE")

    def modify_hit(self, hit, question, correct, request, elapsed):
        engine = self.engine
        if request.purpose == "time":
            if elapsed is None or elapsed <= request.time_limit:
                hit.extras.append(("Rewind Strike", self.p("rewind_mult", 1.5)))
                hit.notes.append("Inside the time window: REWIND STRIKE x1.5!")
            else:
                hit.notes.append("The time window closed - still a hit, just no bonus.")
            return
        if len(engine.answers) >= 2 and engine.answers[-2][0] == question.topic and request.purpose == "attack":
            hit.extras.append(("Foreseen", self.p("foreseen_mult", 0.5)))
            hit.notes.append(f"{self.name} predicted another {topic_label(question.topic)} attack (x0.5). "
                             "Switch topics to surprise it!")

    def after_answer(self, question, correct, hit, request, forgiven):
        if request.purpose == "time":
            self.armed = False
        return []

    # -- the pattern ----------------------------------------------------------------
    def ai_options(self):
        if not self.pattern or self.engine.pending or self.armed:
            return []
        return [Decision(AIState.ATTACK, PATTERN_MOVE, 3.0, "follows its time pattern")]

    def ability_score(self, ability):
        if ability.effect == "time_lock":
            return None if self.armed else 4.0
        return 3.0

    def perform(self, effect, ability):
        engine = self.engine
        if effect == "time_lock":
            self.armed = True
            return [Event("time_lock", f"{self.name} freezes time! Next: a sequence question with a "
                                       f"{self.window_seconds()}-second window for a Rewind Strike.",
                          {"seconds": self.window_seconds()})]
        move = engine.defn.ability(self.pattern[self.index % len(self.pattern)])
        self.index += 1
        upcoming = ", ".join(a.name for a in self.upcoming(3))
        events = engine.monster_attack(move, move.power, move.name)
        events.append(Event("predict", f"Pattern continues: {upcoming}...", {"next": upcoming}))
        return events

    def badges(self):
        upcoming = self.upcoming(3)
        if not upcoming:
            return []
        badges = [Badge("PATTERN", " > ".join(a.name.split()[0] for a in upcoming), "gold",
                        "Its attacks repeat in a sequence. Read the pattern!")]
        if self.armed:
            badges.append(Badge("TIME LOCK", f"{self.window_seconds()}s", "sky", "Answer inside the window for x1.5."))
        return badges

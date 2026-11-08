"""Sphynox's puzzle barrier: a wall of locks that only logic opens.

While the barrier stands, every question is a logic puzzle and no damage reaches Sphynox. Each
correct puzzle opens one lock (two with Shield Breaker). With every lock open the barrier falls and
Sphynox is stunned. It can raise a fresh barrier later (effect "puzzle_barrier").
"""
from battle_engine.events import Badge, Event, QuestionRequest
from battle_engine.mechanics.base import Mechanic


class PuzzleBarrier(Mechanic):
    TYPE = "barrier"
    EFFECTS = ("puzzle_barrier",)

    def __init__(self, engine, params):
        super().__init__(engine, params)
        self.max_locks = int(self.p("locks", 2)) + (1 if engine.tier.rank >= 3 else 0) + (1 if engine.tier.rank >= 5 else 0)
        self.locks = 0
        self.turns_down = 0

    @property
    def up(self):
        return self.locks > 0

    def setup(self):
        return self._raise()

    def _raise(self):
        self.locks = self.max_locks
        self.turns_down = 0
        return [Event("barrier", f"{self.name} weaves a PUZZLE BARRIER with {self.locks} locks. Only logic opens it!",
                      {"locks": self.locks})]

    def forces_question(self):
        return self.up

    def question_request(self):
        if not self.up:
            return None
        return QuestionRequest("barrier", self.p("topic", "logic"),
                               label=f"PUZZLE BARRIER: {self.locks} LOCK{'S' if self.locks > 1 else ''} LEFT")

    def absorb(self, hit, question, correct, request):
        if not self.up or request.purpose != "barrier":
            return []
        hit.blocked, hit.to_hp = hit.raw, 0
        if not correct:
            return []
        opened = 2 if hit.shield_mult >= 2 else 1
        self.locks = max(0, self.locks - opened)
        hit.notes.append("Puzzle solved: the barrier takes the hit instead of Sphynox.")
        events = [Event("lock_break", f"Puzzle solved! {opened} lock{'s' if opened > 1 else ''} open"
                                      f" ({self.locks} left).", {"locks": self.locks})]
        if not self.locks:
            self.engine.stunned = max(self.engine.stunned, 1)
            events.append(Event("shield_break", f"The PUZZLE BARRIER collapses! {self.name} is stunned - attack now!"))
        return events

    def after_answer(self, question, correct, hit, request, forgiven):
        if self.up and request.purpose == "barrier" and not correct:
            return [Event("barrier", "The barrier holds. Read every clue again - logic never guesses.")]
        return []

    def ability_score(self, ability):
        if self.up or self.turns_down < self.p("raise_cooldown", 4):
            return None
        return 4.5

    def perform(self, effect, ability):
        return self._raise()

    def end_round(self):
        if not self.up:
            self.turns_down += 1
        return []

    def badges(self):
        if self.up:
            return [Badge("BARRIER", f"{self.locks}/{self.max_locks} locks", "sky",
                          "Solve logic puzzles to open the locks.")]
        return [Badge("BARRIER", "OPEN", "muted", "Strike before a new barrier rises!")]

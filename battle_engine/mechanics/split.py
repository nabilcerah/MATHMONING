"""Mycomorph's split.

When its HP falls to ``at_hp`` it vanishes and leaves spores, each showing a fraction. Every turn
the player gets a fraction question; the answer tells them which spore is the real target. A
correct pick destroys that spore; a wrong pick hits a decoy. Spores attack together each monster
turn. When they are all gone, Mycomorph reforms (stunned and hurt by the recoil).
"""
from fractions import Fraction

from battle_engine.events import Badge, Event, QuestionRequest
from battle_engine.mechanics.base import Mechanic
from mathematics.question_engine import Question, fmt

POOLS = {
    1: [Fraction(1, 2), Fraction(1, 3), Fraction(2, 3), Fraction(1, 4), Fraction(3, 4)],
    3: [Fraction(1, 2), Fraction(1, 3), Fraction(2, 3), Fraction(1, 4), Fraction(3, 4), Fraction(2, 5),
        Fraction(3, 5), Fraction(5, 6), Fraction(3, 8), Fraction(5, 8)],
}
LETTERS = "ABCDE"


class Split(Mechanic):
    TYPE = "split"

    def __init__(self, engine, params):
        super().__init__(engine, params)
        self.minions = []
        self.hidden = False
        self.splits_done = 0
        self.times = int(self.p("times", 1)) + (1 if engine.tier.rank >= int(self.p("extra_split_rank", 4)) else 0)
        self.target = None
        self._question_count = 0

    def _thresholds(self):
        first = float(self.p("at_hp", 0.5))
        return [first, first * 0.4][: self.times]

    def _should_split(self):
        if self.hidden or self.splits_done >= self.times:
            return False
        ratio = self.engine.monster_hp / self.engine.monster_max_hp
        return ratio <= self._thresholds()[self.splits_done]

    # -- splitting ------------------------------------------------------------------
    def _split(self):
        engine = self.engine
        count = int(self.p("minions", 3)) + (1 if engine.tier.rank >= 3 else 0)
        pool = list(POOLS[3] if engine.tier.rank >= 3 else POOLS[1])
        engine.rng.shuffle(pool)
        hp = max(4, round(engine.monster_max_hp * self.p("minion_hp_ratio", 0.08)))
        self.minions = [{"label": f"Spore {LETTERS[i]}", "value": pool[i], "hp": hp, "max_hp": hp, "alive": True}
                        for i in range(count)]
        self.hidden = True
        self.splits_done += 1
        engine.pending = None
        return [Event("split", f"{self.name} bursts into {count} spores! Solve the fraction question to find "
                               "which spore to strike.", {"count": count})]

    def alive(self):
        return [m for m in self.minions if m["alive"]]

    # -- questions ------------------------------------------------------------------
    def forces_question(self):
        return self.hidden and bool(self.alive())

    def question_request(self):
        if not self.hidden or not self.alive():
            return None
        alive = self.alive()
        self.target = alive[self._question_count % len(alive)]
        self._question_count += 1
        return QuestionRequest("split_target", "fractions", question=self._target_question(self.target),
                               label="FIND THE RIGHT SPORE")

    def _target_question(self, target):
        engine = self.engine
        rng, value, level = engine.rng, target["value"], engine.tier.question_level
        if level <= 2:
            k = rng.randint(2, 5)
            prompt = f"Strike the spore equal to {value.numerator * k}/{value.denominator * k}."
            explanation = f"{value.numerator * k}/{value.denominator * k} simplifies (÷{k}) to {fmt(value)}."
            proof = Fraction(value.numerator * k, value.denominator * k)
        elif level == 3:
            part = Fraction(1, value.denominator * 2)
            rest = value - part
            prompt = f"Strike the spore holding {fmt(part)} + {fmt(rest)}."
            explanation = f"{fmt(part)} + {fmt(rest)}: use a common denominator, and the total is {fmt(value)}."
            proof = part + rest
        else:
            factor = rng.choice([Fraction(1, 2), Fraction(2, 3), Fraction(3, 4), Fraction(3, 2), Fraction(2)])
            other = value / factor
            prompt = f"Strike the spore holding {fmt(factor)} × {fmt(other)}."
            explanation = f"Multiply tops and bottoms: {fmt(factor)} × {fmt(other)} = {fmt(value)}."
            proof = factor * other
        if proof != value:  # deterministic self-check: never show an unproven target
            raise ValueError("split question failed verification")
        # Popped spores stay on the list, so the last spore still needs the maths to be found.
        choices = [f"{m['label']}: {fmt(m['value'])}" for m in self.minions]
        answer = f"{target['label']}: {fmt(value)}"
        return Question(f"{engine.defn.id}-split-{self._question_count}", "fractions", level, prompt, answer, choices,
                        explanation + f" That was {target['label']}.", "Simplify, or turn every fraction into the "
                        "same denominator.", "choice", engine.defn.name.upper(), True)

    # -- the hit lands on a spore -------------------------------------------------
    def absorb(self, hit, question, correct, request):
        engine = self.engine
        if self.hidden and request.purpose == "split_target":
            hit.blocked, hit.to_hp = hit.raw, 0
            if correct and self.target is not None:
                self.target["hp"] = 0
                self.target["alive"] = False
                events = [Event("minion_down", f"Correct target! {self.target['label']} ({fmt(self.target['value'])}) "
                                               "pops!", {"label": self.target["label"]})]
                hit.notes.append(f"You found {self.target['label']}.")
                if not self.alive():
                    events += self._merge()
                return events
            return []
        # Mycomorph always gets to split before it can be defeated.
        if not self.hidden and self.splits_done < self.times and engine.monster_hp - hit.to_hp <= 0:
            hit.to_hp = max(0, engine.monster_hp - 1)
        return []

    def _merge(self):
        engine = self.engine
        self.hidden = False
        recoil = round(engine.monster_max_hp * self.p("recoil", 0.08))
        engine.monster_hp = max(1, engine.monster_hp - recoil)
        engine.stunned = max(engine.stunned, 1)
        return [Event("merge", f"All the spores are gone! {self.name} reforms, dizzy from the recoil (-{recoil} HP).",
                      {"recoil": recoil})]

    def after_answer(self, question, correct, hit, request, forgiven):
        if self.hidden and request.purpose == "split_target" and not correct:
            return [Event("decoy", "That spore was a decoy! Look at the fractions again.")]
        if self._should_split() and self.engine.monster_hp > 0:
            return self._split()
        return []

    # -- spores act instead of the main body ---------------------------------------
    def before_monster_turn(self):
        if not self.hidden:
            return [], False
        alive = self.alive()
        if not alive:
            return [], False
        power = self.p("minion_power", 0.3) * len(alive)
        events = [Event("minion_attack", f"{len(alive)} spores puff toxic clouds together.")]
        return events + self.engine.monster_attack(None, power, "Spore Swarm"), True

    def badges(self):
        if self.hidden:
            return [Badge("SPLIT", f"{len(self.alive())} spores", "mint", "Answer the fraction question to pick the real spore.")]
        left = self.times - self.splits_done
        return [Badge("SPLIT", f"at {round(self._thresholds()[self.splits_done] * 100)}% HP" if left else "used",
                      "muted", "It will split into fraction spores.")]

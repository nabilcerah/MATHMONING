"""Arithmord's Operation Combo: it chains attack types into an expression, and the expression's
value IS the damage. Apply the order of operations to predict it exactly and you block the whole
combo (and counter). A wrong prediction lets it land.
"""
from fractions import Fraction

from battle_engine.events import Badge, Event, QuestionRequest
from battle_engine.mechanics.base import Mechanic
from mathematics.question_engine import Question, fmt
from mathematics.question_engine.distractors import build_choices, numeric_options
from mathematics.question_engine.safe_eval import left_to_right, safe_eval

MOVES = {"+": "Plus Slash", "-": "Minus Rend", "*": "Times Crush", "/": "Divide Pierce"}


class OperationCombo(Mechanic):
    TYPE = "operation_combo"
    EFFECTS = ("combo_expression",)

    def __init__(self, engine, params):
        super().__init__(engine, params)
        self.combo = None        # {"expr", "shown", "value", "ability", "blocked"}
        self.count = 0

    def _expression(self):
        rng, level = self.engine.rng, self.engine.tier.question_level
        while True:
            a, b, c, d = (rng.randint(2, 9) for _ in range(4))
            if level <= 1:
                expr = f"{a}+{b}*{c}"
            elif level == 2:
                expr = f"{a}*{b}-{c}"
            elif level == 3:
                expr = f"({a}+{b})*{c}-{d}"
            elif level == 4:
                expr = f"{a}+{b}*{c}-{d * c}/{c}"
            else:
                expr = f"{a}*({b}+{c})-{d}**2"
            value = safe_eval(expr)
            if value > 0 and value.denominator == 1:
                shown = expr.replace("**2", "²").replace("*", " × ").replace("/", " ÷ ").replace("+", " + ").replace("-", " − ")
                return expr, shown, value

    def ability_score(self, ability):
        return None if self.combo else 4.0

    def perform(self, effect, ability):
        expr, shown, value = self._expression()
        moves = " + ".join(dict.fromkeys(MOVES[ch] for ch in expr if ch in MOVES))
        self.combo = {"expr": expr, "shown": shown, "value": value, "ability": ability, "blocked": False}
        return [Event("charge", f"WARNING: {self.name} chains {moves}: {shown}. Its value is the damage! "
                                "Predict it exactly to block.", {"ability": ability.id, "expression": shown})]

    def forces_question(self):
        return bool(self.combo) and not self.combo.get("asked")

    def question_request(self):
        if not self.combo or self.combo.get("asked"):
            return None
        self.combo["asked"] = True
        self.count += 1
        combo = self.combo
        engine = self.engine
        mistakes = [left_to_right(combo["expr"]), combo["value"] + 2, combo["value"] - 3]
        if "(" in combo["expr"]:
            mistakes.insert(0, safe_eval(combo["expr"].replace("(", "").replace(")", "")))
        wrong = numeric_options(combo["value"], mistakes, engine.rng, 3)
        answer = fmt(combo["value"])
        question = Question(f"{engine.defn.id}-combo-{self.count}", "mixed_operations", engine.tier.question_level,
                            f"Predict the combo: {combo['shown']} = ?", answer,
                            build_choices(answer, wrong, engine.rng), "Brackets, then powers, then × and ÷, then + and −. "
                            f"So {combo['shown']} = {answer}.", "BIDMAS - never just left to right!", "number",
                            engine.defn.name.upper(), True, combo["expr"])
        return QuestionRequest("predict", "mixed_operations", question=question, label="PREDICT THE COMBO DAMAGE")

    def after_answer(self, question, correct, hit, request, forgiven):
        if request.purpose != "predict" or not self.combo:
            return []
        if correct:
            self.combo["blocked"] = True
            return [Event("interrupt", f"Perfect prediction! You block the {fmt(self.combo['value'])}-point combo.")]
        return [Event("interrupt_fail", f"Wrong prediction - the combo will land for real!")]

    def modify_hit(self, hit, question, correct, request, elapsed):
        if request.purpose == "predict" and correct:
            hit.extras.append(("Counter", 1.25))

    def before_monster_turn(self):
        if not self.combo or not self.combo.get("asked"):
            return [], False
        combo, self.combo = self.combo, None
        if combo["blocked"]:
            return [Event("special", f"{self.name}'s combo {combo['shown']} fizzles against your prediction!")], True
        power = max(0.8, min(2.2, 0.6 + float(combo["value"]) / 25))
        events = [Event("release", f"{self.name}'s combo {combo['shown']} = {fmt(combo['value'])} strikes!",
                        {"ability": combo["ability"].id})]
        return events + self.engine.monster_attack(combo["ability"], power, "Operation Combo"), True

    def badges(self):
        if self.combo:
            return [Badge("COMBO", self.combo["shown"], "coral", "Its value is the damage. Predict it to block!")]
        return [Badge("COMBO", "ready soon", "muted", "It chains + − × ÷ attacks into one expression.")]

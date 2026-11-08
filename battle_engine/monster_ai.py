"""Deterministic monster AI: a finite state machine scored from the battle situation.

States: IDLE, OBSERVE, PREPARE, ATTACK, DEFEND, COUNTER, SPECIAL, STUNNED, DEFEATED.

Each monster turn the AI scores every usable ability (and any option a mechanic offers) from:
current HP, the player's last action and recent accuracy, shield status, the battle phase and
cooldowns. The highest score wins; ties go to the ability listed first. Same situation, same
choice - no randomness and no LLM. (An LLM may one day *suggest* flavour, but damage and answer
checking always stay in the engine.)
"""
from dataclasses import dataclass
from enum import Enum

from battle_engine.monster_data import tier_allows


class AIState(str, Enum):
    IDLE = "IDLE"
    OBSERVE = "OBSERVE"
    PREPARE = "PREPARE"
    ATTACK = "ATTACK"
    DEFEND = "DEFEND"
    COUNTER = "COUNTER"
    SPECIAL = "SPECIAL"
    STUNNED = "STUNNED"
    DEFEATED = "DEFEATED"


TYPE_STATE = {"attack": AIState.ATTACK, "charge": AIState.PREPARE, "multistage": AIState.PREPARE,
              "special": AIState.SPECIAL, "defend": AIState.DEFEND, "counter": AIState.COUNTER}


@dataclass
class Decision:
    state: AIState
    ability: object = None   # AbilityDef or None
    score: float = 0.0
    reason: str = ""


class MonsterAI:
    def __init__(self, engine):
        self.engine = engine
        self.state = AIState.IDLE
        behaviour = engine.defn.behaviour
        self.aggression = float(behaviour.get("aggression", 0.5))
        self.defend_hp = float(behaviour.get("defend_below_hp", 0.5))
        self.observe_first = bool(behaviour.get("observe_first", not engine.defn.boss))
        self.history = []

    # ------------------------------------------------------------------ inputs
    def player_accuracy(self, last=4):
        answers = self.engine.answers[-last:]
        return sum(1 for _, ok in answers if ok) / len(answers) if answers else 0.5

    def usable(self):
        engine = self.engine
        ratio = engine.monster_hp / engine.monster_max_hp
        for ability in engine.defn.abilities:
            if engine.cooldowns.get(ability.id, 0) > 0:
                continue
            if not tier_allows(ability.min_tier, engine.tier.id, engine.balance):
                continue
            if ratio > ability.hp_below or not engine.phase.allows(ability):
                continue
            yield ability

    def score(self, ability):
        engine = self.engine
        ratio = engine.monster_hp / engine.monster_max_hp
        accuracy = self.player_accuracy()
        struggling = len(engine.answers) >= 3 and accuracy < 0.4
        if ability.type == "attack":
            return 1.0 + 0.5 * self.aggression, "basic attack"
        if ability.type == "counter":
            if engine.last_wrong:
                return 5.0, "punishes a wrong answer"
            return None, ""
        if ability.type in ("charge", "multistage"):
            score = 2.0 + self.aggression + (0.5 if ratio < 0.5 else 0.0)
            if struggling:
                score -= 1.5  # go easier on a student who is finding this hard
            return score, "big attack while the player is doing well" if accuracy > 0.6 else "power attack"
        owner = engine.mechanic_for(ability.effect)
        if owner is not None:
            return owner.ability_score(ability), f"{owner.TYPE} decision"
        if ability.type == "defend":
            if ratio < self.defend_hp and accuracy >= 0.5:
                return 2.5, "low HP against an accurate player"
            return None, ""
        return 1.5, "special"

    # ------------------------------------------------------------------ choice
    def decide(self):
        engine = self.engine
        if engine.monster_hp <= 0:
            return Decision(AIState.DEFEATED)
        if engine.stunned:
            return Decision(AIState.STUNNED)
        best = None
        for order, ability in enumerate(self.usable()):
            score, reason = self.score(ability)
            if score is None:
                continue
            key = (score, -order)
            if best is None or key > best[0]:
                best = (key, Decision(TYPE_STATE.get(ability.type, AIState.SPECIAL), ability, score, reason))
        for option in engine.mechanic_ai_options():
            key = (option.score, 1)
            if best is None or key > best[0]:
                best = (key, option)
        # On its first turn a monster studies you - unless something urgent (score >= 5) is ready.
        if self.observe_first and engine.turn <= 1 and (best is None or best[1].score < 5):
            return Decision(AIState.OBSERVE, reason="studies the player first")
        return best[1] if best else Decision(AIState.OBSERVE, reason="nothing ready")

    def remember(self, decision):
        self.state = decision.state
        self.history.append(decision.state)

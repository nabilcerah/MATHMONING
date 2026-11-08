"""BattleEngine: the rules of an advanced monster battle, with no drawing code.

A turn is: the player answers a question (``next_question`` then ``answer``), then the monster
acts (``monster_turn``). Both return ``Event`` lists the screen turns into animations; every event
is also written to ``log`` in plain language so students can see *why* things happened.

Everything authoritative - answer checking, damage, shields, phases, AI choices - happens here,
deterministically for a given ``random.Random`` seed.
"""
import random
from dataclasses import dataclass

from battle_engine import mechanics as mechanic_registry
from battle_engine.balance import BALANCE
from battle_engine.damage import Hit, MonsterHit, resolve_monster_hit, resolve_player_hit
from battle_engine.events import AnswerResult, Event, QuestionRequest
from battle_engine.monster_ai import AIState, Decision, MonsterAI
from battle_engine.monster_data import MonsterDef, build_stats, get, tier_allows
from battle_engine.phases import PhaseController
from battle_engine.skills import SKILL_BY_ID, unlocked
from battle_engine.tiers import tier_for_level
from mathematics.question_engine import QuestionEngine, canonical_topic, topic_label


@dataclass
class PlayerCombatant:
    name: str
    level: int
    hp: int
    max_hp: int
    attack: float
    defence: float
    speed: float
    crit_chance: float

    @classmethod
    def from_level(cls, name, level, hp, max_hp, trainer_level=1, balance=None):
        p = (balance or BALANCE)["player"]
        return cls(name, level, hp, max_hp,
                   p["attack_base"] * (1 + p["attack_growth"] * (level - 1)) + p["trainer_attack_per_level"] * trainer_level,
                   p["defence_base"] + p["defence_per_level"] * level,
                   p["speed_base"] + p["speed_per_level"] * level, p["crit_base"])


@dataclass
class Pending:
    """An attack being charged (charge) or played out over several turns (multistage)."""
    ability: object
    stage: int = 0
    turns_left: int = 1
    interrupt_topics: tuple = ()

    @property
    def stages(self):
        return self.ability.stages

    @property
    def stage_name(self):
        if self.stages:
            return self.stages[self.stage].get("name", f"Stage {self.stage + 1}")
        return self.ability.name

    @property
    def power(self):
        if self.stages:
            return sum(float(s.get("power", 0)) for s in self.stages[:self.stage + 1]) or self.ability.power
        return self.ability.power


class BattleEngine:
    def __init__(self, monster, level, player, rng=None, balance=None, trainer_level=1, questions=None):
        self.defn = monster if isinstance(monster, MonsterDef) else get(monster)
        self.balance = balance or BALANCE
        self.rng = rng or random.Random()
        self.level = int(level)
        self.tier = tier_for_level(self.level, self.balance)
        self.stats = build_stats(self.defn, self.level, self.balance)
        self.monster_hp = self.monster_max_hp = self.stats.max_hp
        self.player = player
        self.trainer_level = trainer_level
        self.questions = questions or QuestionEngine(self.rng, self.defn.name.upper())
        self.log = []
        self.turn = 0
        self.answers = []
        self.cooldowns = {ability.id: 0 for ability in self.defn.abilities}
        self.stunned = 0
        self.guard = 0
        self.pending = None
        self.outcome = None
        self.combo = 0
        self.last_wrong = False
        self.question = None
        self.request = None
        self.choices = []
        self.buffs = set()
        self.skill_cooldowns = {}
        self.revealed_intent = None
        self.mechanics = [mechanic_registry.create(self, spec) for spec in self.defn.mechanics
                          if tier_allows(spec.get("min_tier", "common"), self.tier.id, self.balance)]
        self.phase = PhaseController(self)
        self.ai = MonsterAI(self)
        self._topic_turn = 0

    # ================================================================== queries
    @property
    def name(self):
        return self.defn.name

    @property
    def skills(self):
        return unlocked(self.trainer_level)

    def mechanic(self, type_name):
        return next((m for m in self.mechanics if m.TYPE == type_name), None)

    def mechanic_for(self, effect):
        if not effect:
            return None
        return next((m for m in self.mechanics if effect in m.EFFECTS and m.active), None)

    def mechanic_ai_options(self):
        options = []
        for mechanic in self.mechanics:
            if mechanic.active:
                options += mechanic.ai_options() or []
        return options

    def weakness_topics(self):
        return {canonical_topic(t) for t in self.defn.weakness}

    def resisted_topics(self):
        return {canonical_topic(t) for t in self.defn.resistance}

    def forced_question(self):
        """True when the next question is decided for the player (a charge to interrupt, a barrier...)."""
        return self.pending is not None or any(m.active and m.forces_question() for m in self.mechanics)

    def topic_options(self):
        """What the ATTACK menu offers: each topic and how well it works on this monster."""
        options = []
        for topic in self.phase.topics():
            topic = canonical_topic(topic)
            effect = "weak" if topic in self.weakness_topics() else "resist" if topic in self.resisted_topics() else "normal"
            options.append({"topic": topic, "label": topic_label(topic), "effect": effect})
        return options

    def badges(self):
        found = []
        for mechanic in self.mechanics:
            if mechanic.active:
                found += mechanic.badges() or []
        return found

    def intent(self):
        """What the monster will do next (shown by the Analyse skill, or always for a charge)."""
        if self.pending:
            return f"{self.pending.stage_name}: {self.pending.ability.warning or 'answer correctly to interrupt!'}"
        if self.stunned:
            return "Stunned - it will lose its next turn."
        decision = self.ai.decide()
        if decision.ability is not None:
            return f"{decision.state.value.title()}: {decision.ability.name}. {decision.ability.description}"
        return {AIState.OBSERVE: "Observe: it is studying you.", AIState.DEFEND: "Defend.",
                AIState.SPECIAL: f"Special: {decision.reason}"}.get(decision.state, decision.state.value.title())

    def recent_accuracy(self, last=4):
        return self.ai.player_accuracy(last)

    # ================================================================== flow
    def begin(self):
        events = [Event("intro", f"{self.name} (Lv {self.level}, {self.tier.name}) appears! "
                                 f"Speciality: {topic_label(self.defn.math_speciality)}.")]
        for mechanic in self.mechanics:
            if mechanic.active:
                events += mechanic.setup() or []
        events += self.phase.enter_first()
        return self._record(events)

    def question_level(self, request=None):
        level = self.tier.question_level + self.phase.level_offset()
        if request is not None:
            level += request.level_offset
        for mechanic in self.mechanics:
            if mechanic.active:
                level += mechanic.question_level_offset()
        # Adaptive support: after a run of misses, step down one level (never below the tier's floor - 1).
        if len(self.answers) >= 3 and self.recent_accuracy(3) == 0:
            level = max(self.tier.question_level - 1, level - 1)
        return max(1, min(5, level))

    def next_question(self, topic=None):
        """Prepare the question for the player's turn. Mechanics and charges take priority."""
        request = None
        for mechanic in self.mechanics:
            if mechanic.active:
                request = mechanic.question_request()
                if request is not None:
                    request.source = mechanic
                    break
        if request is None and self.pending is not None:
            topics = self.pending.interrupt_topics or tuple(self.weakness_topics()) or self.phase.topics()
            chosen = canonical_topic(topic) if topic and canonical_topic(topic) in topics else sorted(topics)[0]
            request = QuestionRequest("interrupt", chosen, label=f"INTERRUPT {self.pending.ability.name.upper()}!")
        if request is None:
            request = QuestionRequest("attack", canonical_topic(topic) if topic else self._default_topic())
        if request.question is None:
            weak = request.topic in self.weakness_topics()
            request.question = self.questions.generate(request.topic, self.question_level(request), weakness=weak,
                                                       choice_count=self.choice_count())
        self.request, self.question = request, request.question
        self.choices = list(self.question.choices)
        if "focus" in self.buffs and len(self.choices) > 2:
            self.buffs.discard("focus")
            wrong = [c for c in self.choices if not self.question.check(c)]
            keep = {self.question.answer, self.rng.choice(wrong)}
            self.choices = [c for c in self.choices if c in keep or self.question.check(c)][:2]
        return self.question

    def choice_count(self):
        count = 4
        for mechanic in self.mechanics:
            if mechanic.active:
                count = mechanic.choice_count(count)
        return count

    def typed_only(self):
        if self.question is not None and self.question.kind != "number":
            return False
        return any(m.active and m.typed_only() for m in self.mechanics)

    def _default_topic(self):
        topics = self.phase.topics()
        topic = topics[self._topic_turn % len(topics)]
        self._topic_turn += 1
        return canonical_topic(topic)

    # ------------------------------------------------------------------ answering
    def answer(self, submitted, typed=False, elapsed=None):
        question, request = self.question, self.request
        if question is None or self.outcome:
            return AnswerResult(False, question, summary="No question to answer.")
        correct = question.check(submitted)
        events, forgiven = [], False
        if not correct and "second_chance" in self.buffs:
            self.buffs.discard("second_chance")
            forgiven = True
            events.append(Event("skill", "Second Chance! This miss is forgiven - the monster can't use it."))
        self.answers.append((question.topic, correct))
        self.combo = self.combo + 1 if correct else 0
        interrupted = False
        if request.purpose == "interrupt" and self.pending is not None:
            if correct:
                events += self._interrupt()
                interrupted = True
            else:
                events.append(Event("interrupt_fail", f"Not quite - {self.name} keeps charging {self.pending.ability.name}!"))
        hit = None
        settings = self.balance["player_damage"]
        if correct or (settings["answer_wrong"] > 0 and not forgiven):
            hit = self._build_hit(question, correct, typed, interrupted)
            for mechanic in self.mechanics:
                if mechanic.active:
                    mechanic.modify_hit(hit, question, correct, request, elapsed)
            resolve_player_hit(hit, self.monster_max_hp, settings)
            for mechanic in self.mechanics:
                if mechanic.active:
                    events += mechanic.absorb(hit, question, correct, request) or []
            if self.guard and hit.to_hp:
                guarded = round(hit.to_hp * 0.5)
                hit.blocked += hit.to_hp - guarded
                hit.to_hp = guarded
                hit.notes.append(f"{self.name} was guarding: damage halved.")
            events += self._damage_monster(hit)
        for mechanic in self.mechanics:
            if mechanic.active:
                events += mechanic.after_answer(question, correct, hit, request, forgiven) or []
        self.last_wrong = not correct and not forgiven
        if "shield_breaker" in self.buffs and correct:
            self.buffs.discard("shield_breaker")
        if "mind_surge" in self.buffs and correct:
            self.buffs.discard("mind_surge")
        for skill_id in list(self.skill_cooldowns):
            self.skill_cooldowns[skill_id] = max(0, self.skill_cooldowns[skill_id] - 1)
        summary = self._summary(correct, hit, forgiven)
        explanation = question.explanation if correct else f"The answer was {question.answer}. {question.explanation}"
        events.insert(0, Event("answer", summary, {"correct": correct}))
        events.append(Event("learn", explanation, {"correct": correct}))
        if self.monster_hp <= 0 and not self.phase.has_next:
            self.outcome = "won"
            self.ai.state = AIState.DEFEATED
            events.append(Event("victory", f"{self.name} is defeated!"))
        self.guard = 0
        self._record(events)
        return AnswerResult(correct, question, hit, events, summary, explanation, forgiven)

    def _build_hit(self, question, correct, typed, interrupted):
        settings = self.balance["player_damage"]
        hit = Hit(base=self.player.attack, defence=self.stats.defence)
        hit.answer_mult = settings["answer_correct"] if correct else settings["answer_wrong"]
        topic = canonical_topic(question.topic)
        tags = {canonical_topic(t) for t in question.tags}
        if topic in self.weakness_topics() or tags & self.weakness_topics():
            hit.weakness_mult = settings["weakness"]
            hit.notes.append(f"{topic_label(topic)} is {self.name}'s weakness (x{settings['weakness']}).")
        elif topic in self.resisted_topics():
            hit.weakness_mult = settings["resistance"]
            hit.notes.append(f"{self.name} resists {topic_label(topic)} (x{settings['resistance']}).")
        if typed and question.kind == "number":
            hit.extras.append(("Typed answer", settings["typed_bonus"]))
        combo_bonus = 1 + settings["combo_step"] * min(max(0, self.combo - 1), settings["combo_cap"])
        if combo_bonus > 1:
            hit.extras.append((f"{self.combo} in a row", combo_bonus))
        if interrupted:
            hit.extras.append(("Counter", 1.25))
        surge = "mind_surge" in self.buffs
        if surge or self.rng.random() < self.player.crit_chance:
            hit.critical, hit.critical_mult = True, settings["critical"]
            hit.notes.append("CRITICAL HIT!" + (" (Mind Surge)" if surge else ""))
        if "shield_breaker" in self.buffs:
            hit.shield_mult *= 2
        return hit

    def _damage_monster(self, hit):
        amount = hit.to_hp
        events = []
        if hit.to_shield or hit.blocked or amount or hit.raw:
            events.append(Event("player_hit", f"Hit for {amount} damage.", {"amount": amount, "critical": hit.critical,
                                                                            "shield": hit.to_shield}))
        threshold = self.phase.next_threshold_hp()
        new_hp = self.monster_hp - amount
        if threshold is not None and new_hp <= threshold:
            new_hp = threshold
            self.monster_hp = new_hp
            events += self.phase.advance()
            return events
        self.monster_hp = max(0, new_hp)
        return events

    def _interrupt(self):
        ability = self.pending.ability
        stage = self.pending.stage_name
        self.pending = None
        self.cooldowns[ability.id] = ability.cooldown
        self.stunned = max(self.stunned, ability.stun_on_interrupt)
        stun = " It is stunned!" if ability.stun_on_interrupt else ""
        return [Event("interrupt", f"INTERRUPTED! Your answer broke {self.name}'s {ability.name} at '{stage}'.{stun}",
                      {"ability": ability.id})]

    def _summary(self, correct, hit, forgiven):
        if not correct:
            return "Not quite." + (" (forgiven)" if forgiven else "")
        if hit is None:
            return "Correct!"
        parts = [f"Correct! {hit.to_hp} damage"]
        if hit.to_shield:
            parts.append(f"{hit.to_shield} to the shield")
        if hit.blocked:
            parts.append(f"{hit.blocked} blocked")
        text = ", ".join(parts) + "."
        if hit.notes:
            text += " " + " ".join(hit.notes)
        return text

    # ------------------------------------------------------------------ skills and items
    def skill_ready(self, skill_id):
        skill = SKILL_BY_ID[skill_id]
        return skill in self.skills and not self.skill_cooldowns.get(skill_id)

    def use_skill(self, skill_id):
        skill = SKILL_BY_ID.get(skill_id)
        if skill is None or skill not in self.skills:
            return self._record([Event("info", "That skill is still locked.")])
        if self.skill_cooldowns.get(skill_id):
            return self._record([Event("info", f"{skill.name} recharges in {self.skill_cooldowns[skill_id]} answer(s).")])
        self.skill_cooldowns[skill_id] = skill.cooldown
        if skill_id == "analyse":
            self.revealed_intent = self.intent()
            weak = ", ".join(topic_label(t) for t in sorted(self.weakness_topics()))
            return self._record([Event("skill", f"ANALYSE: next move - {self.revealed_intent} Weak to: {weak}.")])
        self.buffs.add(skill_id)
        if skill_id == "focus" and self.question is not None and len(self.choices) > 2:
            self.buffs.discard("focus")
            wrong = [c for c in self.choices if not self.question.check(c)]
            self.choices = [c for c in self.choices if self.question.check(c)] + [self.rng.choice(wrong)]
            self.rng.shuffle(self.choices)
        return self._record([Event("skill", f"{skill.name}: {skill.description}")])

    def heal_player(self, amount):
        healed = min(amount, self.player.max_hp - self.player.hp)
        self.player.hp += healed
        return healed

    # ================================================================== monster turn
    def monster_turn(self):
        if self.outcome:
            return []
        self.turn += 1
        events, consumed = [], False
        for mechanic in self.mechanics:
            if mechanic.active:
                extra, consumed = mechanic.before_monster_turn()
                events += extra or []
                if consumed:
                    break
        if not consumed:
            if self.stunned:
                self.stunned -= 1
                self.ai.remember(Decision(AIState.STUNNED))
                events.append(Event("stunned", f"{self.name} is stunned and loses its turn!"))
            elif self.pending is not None:
                events += self._advance_pending()
            else:
                decision = self.ai.decide()
                self.ai.remember(decision)
                events += self._execute(decision)
        for mechanic in self.mechanics:
            if mechanic.active:
                events += mechanic.end_round() or []
        for ability_id in self.cooldowns:
            self.cooldowns[ability_id] = max(0, self.cooldowns[ability_id] - 1)
        self.last_wrong = False
        self.revealed_intent = None
        if self.player.hp <= 0:
            self.player.hp = 0
            self.outcome = "lost"
            events.append(Event("defeat", "Your MATHMON is out of energy. Review the explanations and try again!"))
        return self._record(events)

    def _execute(self, decision):
        ability = decision.ability
        if decision.state == AIState.OBSERVE:
            return [Event("observe", f"{self.name} watches you closely, studying your moves.")]
        if ability is None:
            return [Event("info", f"{self.name} waits.")]
        self.cooldowns[ability.id] = ability.cooldown
        if decision.state == AIState.PREPARE:
            return self._start_pending(ability)
        owner = self.mechanic_for(ability.effect)
        if owner is not None:
            return owner.perform(ability.effect, ability) or []
        if decision.state == AIState.DEFEND:
            self.guard = 1
            return [Event("defend", f"{self.name} raises its guard: your next hit is halved.")]
        power = ability.power * (self.balance["monster_damage"]["counter_power"] if decision.state == AIState.COUNTER else 1)
        label = f"{ability.name} (counter-attack)" if decision.state == AIState.COUNTER else ability.name
        events = []
        for _ in range(max(1, self.phase.attacks_per_turn())):
            events += self.monster_attack(ability, power, label)
        return events

    def _start_pending(self, ability):
        topics = tuple(canonical_topic(t) for t in ability.interrupt_topics) or tuple(sorted(self.weakness_topics()))
        self.pending = Pending(ability, 0, max(1, ability.charge_turns), topics)
        first = ability.stages[0] if ability.stages else {}
        text = first.get("text") or ability.warning or f"{self.name} is charging {ability.name}!"
        return [Event("charge", f"WARNING: {text} Answer correctly to interrupt it!",
                      {"ability": ability.id, "stage": 0, "stages": len(ability.stages) or 1})]

    def _advance_pending(self):
        pending = self.pending
        if pending.stages and pending.stage < len(pending.stages) - 1:
            pending.stage += 1
            stage = pending.stages[pending.stage]
            if pending.stage < len(pending.stages) - 1:
                return [Event("stage", f"{self.name}: {stage.get('text', stage.get('name'))} (stage {pending.stage + 1}"
                                       f"/{len(pending.stages)}) Interrupt it!",
                              {"ability": pending.ability.id, "stage": pending.stage, "stages": len(pending.stages)})]
        else:
            pending.turns_left -= 1
            if pending.turns_left > 0:
                return [Event("stage", f"{self.name} keeps charging {pending.ability.name}...",
                              {"ability": pending.ability.id})]
        self.pending = None
        events = [Event("release", f"{self.name} unleashes {pending.stage_name}!", {"ability": pending.ability.id})]
        for _ in range(max(1, pending.ability.hits)):
            events += self.monster_attack(pending.ability, pending.power / max(1, pending.ability.hits), pending.stage_name)
        return events

    def monster_attack(self, ability, power, label=None, extras=None):
        settings = self.balance["monster_damage"]
        hit = MonsterHit(self.stats.attack * self.phase.attack_mult(), power, list(extras or []), self.player.defence,
                         self.rng.uniform(settings["variance_low"], 1.0), self.rng.random() < self.stats.crit_chance)
        for mechanic in self.mechanics:
            if mechanic.active:
                mechanic.modify_monster_hit(hit, ability)
        resolve_monster_hit(hit, self.player.max_hp, settings, self.balance["crit"]["multiplier"])
        self.player.hp = max(0, self.player.hp - hit.amount)
        bonus = "".join(f" {label_} x{value:.2f}." for label_, value in hit.extras if abs(value - 1) > 0.01)
        crit = " Critical!" if hit.critical else ""
        name = label or (ability.name if ability else "attack")
        return [Event("monster_hit", f"{self.name} uses {name}: {hit.amount} damage.{crit}{bonus}",
                      {"amount": hit.amount, "critical": hit.critical, "ability": getattr(ability, "id", "")})]

    # ================================================================== log
    def _record(self, events):
        for event in events:
            if event.text and event.kind not in ("answer",):
                self.log.append((event.kind, event.text))
        self.log = self.log[-60:]
        return events

"""The battle rules engine (GDD 7-9): pure Python, no pygame, fully deterministic for a seeded RNG.

The battle screen drives it and animates the returned events:

    battle = BattleManager(party, enemy, kind="wild", mastery=profile_lookup, inventory=bag, rng=rng)
    battle.choose_move("crystal_shard")         # -> the screen asks a question on move.topic
    events = battle.resolve_move("first_try")   # player's action resolves first
    if battle.awaiting == "enemy":
        events += battle.enemy_turn()           # then the enemy responds

Every event is a dict with at least "kind" and "text". The AI never calls into this module.
"""
import random

from combat import battle_rules, damage_calculator, reward_manager
from combat.enemy_ai import EnemyAI
from monsters import capture_manager, elemental_system
from monsters.monster_data import items as item_data, move as move_data, rules
from monsters.monster_party import PartyError


class DictInventory:
    """Minimal bag used by tests and as the battle's view of the player's inventory."""

    def __init__(self, counts=None):
        self.counts = dict(counts or {})

    def count(self, item):
        return int(self.counts.get(item, 0))

    def take(self, item):
        if self.count(item) <= 0:
            return False
        self.counts[item] -= 1
        return True


class BattleError(ValueError):
    pass


class BattleManager:
    KINDS = ("wild", "trainer", "boss")

    def __init__(self, party, enemy, kind="wild", mastery=None, inventory=None, rng=None):
        if kind not in self.KINDS:
            raise ValueError(f"unknown battle kind {kind!r}")
        self.party = party
        self.enemy = enemy
        self.kind = "boss" if enemy.spec.boss else kind
        self.mastery = mastery or (lambda topic: 0)
        self.inventory = inventory if inventory is not None else DictInventory()
        self.rng = rng or random.Random()
        self.ai = EnemyAI(boss=self.kind == "boss")
        self.focus = int(rules()["focus"]["start"])   # GDD 7.6: resets every battle
        self.turn = 0
        self.awaiting = "action"   # action | question | capture_question | enemy | switch | over
        self.outcome = None        # won | captured | fled | defeated
        self.pending_move = None
        self.player_shield = self.enemy_shield = False
        self.enemy_debuffed = self.enemy_delayed = False
        self.attack_boost = self.defence_boost = 1.0    # Mathmart boosts, for the rest of this battle
        self.capture_item = None
        self.enemy_slowed = 1.0
        self.heal_guard = False    # healing makes your monster brace: the next enemy hit is softened
        self.topic_streaks = {}    # id(monster) -> correct answers in its passive topic this battle
        self.rhythm = 0            # consecutive first-try answers (CHRONOX passive)
        self.rewards = {"exp": [], "coins": 0, "captured": None, "placed": None}
        self.log = []
        party.start_battle()

    # ------------------------------------------------------------------ views
    @property
    def active(self):
        return self.party.active

    @property
    def can_run(self):
        return self.kind == "wild"

    @property
    def can_capture(self):
        allowed, _ = capture_manager.can_capture(self.enemy, self.kind, self.capture_count())
        return allowed and not (self.party.party_full and self.party.storage_full)

    def capture_items(self):
        """Numeris Cores in the bag (Basic, Advanced, ...): any item whose effect is capture."""
        return [name for name, info in item_data().items() if info["effect"] == "capture" and self.inventory.count(name)]

    def capture_count(self):
        return sum(self.inventory.count(name) for name in self.capture_items())

    def move_usable(self, move):
        if move.focus > self.focus:
            return False, f"{move.name} needs {move.focus} Focus (you have {self.focus})."
        return True, ""

    def move_power(self, move):
        return move.power + (self.active.spec.power_bonus if move.damaging else 0)

    def _event(self, kind, text, **data):
        event = {"kind": kind, "text": text, **data}
        self.log.append(event)
        return event

    def _require(self, *states):
        if self.awaiting not in states:
            raise BattleError(f"not expecting that now (awaiting {self.awaiting})")

    # ------------------------------------------------------------------ FIGHT
    def choose_move(self, move_id):
        self._require("action")
        if move_id not in self.active.spec.moves:
            raise BattleError(f"{self.active.name} does not know that move")
        move = move_data(move_id)
        ok, reason = self.move_usable(move)
        if not ok:
            raise BattleError(reason)
        self.pending_move = move
        self.awaiting = "question"
        return move

    def cancel_question(self):
        """Backing out of a question before answering uses no turn."""
        self._require("question", "capture_question")
        self.pending_move = None
        self.awaiting = "action"

    def resolve_move(self, outcome):
        """Apply the answered move. ``outcome`` is one of battle_rules.OUTCOMES."""
        self._require("question")
        if outcome not in battle_rules.OUTCOMES:
            raise BattleError(f"unknown outcome {outcome!r}")
        move, attacker = self.pending_move, self.active
        self.pending_move = None
        events = []
        answer = battle_rules.answer_multiplier(outcome)
        self._update_rhythm(outcome, events)
        if answer <= 0:
            events.append(self._event("miss", f"{attacker.name}'s {move.name} fizzled. Let's look at that "
                                              "question together, then try again.", move=move.move_id))
        elif move.kind == "support":
            self.focus -= move.focus
            events.append(self._apply_support(move, attacker))
        else:
            events.append(self._player_hit(move, attacker, answer))
            if move.kind == "normal":
                gained = min(battle_rules.focus_gain(), battle_rules.max_focus() - self.focus)
                self.focus += gained
                if gained:
                    events.append(self._event("focus", f"+{gained} Focus ({self.focus}/{battle_rules.max_focus()}).",
                                              focus=self.focus))
            else:
                self.focus -= move.focus
            passive = attacker.spec.passive
            if passive.get("type") == "topic_streak" and move.topic == passive.get("topic"):
                self.topic_streaks[id(attacker)] = self.topic_streaks.get(id(attacker), 0) + 1
        if self.enemy.fainted:
            events += self._victory()
        else:
            self.awaiting = "enemy"
        return events

    def _update_rhythm(self, outcome, events):
        passive = self.active.spec.passive
        if passive.get("type") != "rhythm":
            return
        self.rhythm = self.rhythm + 1 if outcome == battle_rules.FIRST_TRY else 0
        if self.rhythm >= int(passive.get("streak", 2)):
            self.rhythm = 0
            self.enemy_slowed = float(passive.get("multiplier", 0.7))
            events.append(self._event("effect", f"{passive.get('name', 'Rhythm')}! {self.enemy.name} is slowed.",
                                      effect="slow"))

    def passive_power(self, attacker, move):
        passive = attacker.spec.passive
        kind = passive.get("type")
        if kind == "topic_streak":
            return 1 + min(float(passive["max"]), float(passive["step"]) * self.topic_streaks.get(id(attacker), 0))
        if kind == "mastery_power":
            return 1 + float(passive["max"]) * self.mastery(passive["topic"]) / 100
        return 1.0

    @staticmethod
    def focus_bonus(move):
        """Moves that spend Focus hit harder: 1 Focus +30%, 2 Focus +50%, 3 Focus +70% (data/rules.json)."""
        table = rules().get("focus_damage_bonus", {})
        return float(table.get(str(min(int(move.focus), 3)), 0.0)) if move.focus else 0.0

    def _player_hit(self, move, attacker, answer):
        element = elemental_system.multiplier(move.element, self.enemy.element)
        bonus = self.focus_bonus(move)
        extra = self.passive_power(attacker, move) * self.attack_boost * (1 + bonus)
        shielded = self.enemy_shield
        if shielded:
            extra *= rules()["shield"]["incoming_multiplier"]
            self.enemy_shield = False
        result = damage_calculator.calculate(self.move_power(move), attacker.attack, self.enemy.defence, answer,
                                             self.mastery(move.topic), element, extra)
        self.enemy.hp = max(0, self.enemy.hp - result.amount)
        verdict = elemental_system.message(move.element, self.enemy.element)
        note = " The shield softened it." if shielded else ""
        if bonus:
            note = f" Focus power +{round(bonus * 100)}%!" + note
        return self._event("attack", f"{attacker.name} used {move.name}! {verdict} {result.amount} damage.{note}",
                           side="player", move=move.move_id, damage=result.amount, parts=result.parts,
                           effectiveness=elemental_system.effectiveness(move.element, self.enemy.element))

    def _apply_support(self, move, attacker):
        if move.effect == "shield":
            self.player_shield = True
            text = f"{attacker.name} used {move.name}! The next hit will be halved."
        elif move.effect == "debuff":
            if self.enemy_debuffed:
                text = f"{attacker.name} used {move.name}, but {self.enemy.name} is already weakened."
            else:
                self.enemy_debuffed = True
                text = f"{attacker.name} used {move.name}! {self.enemy.name}'s attack fell."
        elif move.effect == "delay":
            self.enemy_delayed = True
            text = f"{attacker.name} used {move.name}! {self.enemy.name} will lose its next turn."
        else:
            text = f"{attacker.name} used {move.name}!"
        return self._event("support", text, side="player", move=move.move_id, effect=move.effect)

    # ------------------------------------------------------------------ enemy
    def enemy_turn(self):
        self._require("enemy")
        self.turn += 1
        events = []
        if self.enemy_delayed:
            self.enemy_delayed = False
            events.append(self._event("info", f"{self.enemy.name} is stuck in time and loses its turn!"))
            self.awaiting = "action"
            return events
        move = self.ai.choose(self.enemy, self.turn, self.enemy_shield)
        target = self.active
        if move.kind == "support":
            self.enemy_shield = True
            events.append(self._event("support", f"{self.enemy.name} used {move.name}! It braces itself.",
                                      side="enemy", move=move.move_id, effect="shield"))
            self.awaiting = "action"
            return events
        events.append(self._enemy_hit(move, target))
        if target.fainted:
            events.append(self._event("faint", f"{target.name} fainted!", side="player"))
            if self.party.healthy():
                self.awaiting = "switch"
                events.append(self._event("info", "Choose who battles next."))
            else:
                self.awaiting, self.outcome = "over", "defeated"
                events.append(self._event("defeat", "Your whole team needs a rest. You hurry to the "
                                                    "Mathmon Recovery Center. Nothing you caught or learned is lost."))
            return events
        self.awaiting = "action"
        return events

    def incoming_multiplier(self, target):
        multiplier = rules()["damage"]["enemy_scale"][self.kind] * self.defence_boost
        if self.enemy_debuffed:
            multiplier *= rules()["debuff"]["attack_multiplier"]
        passive = target.spec.passive
        if passive.get("type") == "mastery_guard":
            multiplier *= 1 - float(passive["max"]) * self.mastery(passive["topic"]) / 100
        charm = item_data().get("Stone Charm", {})
        if target.species_id in charm.get("species", ()) and self.inventory.count("Stone Charm") > 0:
            multiplier *= float(charm.get("guard", 1.0))
        return multiplier

    def _enemy_hit(self, move, target):
        element = elemental_system.multiplier(move.element, target.element)
        extra = self.incoming_multiplier(target) * self.enemy_slowed
        notes = []
        if self.enemy_slowed != 1.0:
            notes.append("It was slowed.")
            self.enemy_slowed = 1.0
        if self.player_shield:
            extra *= rules()["shield"]["incoming_multiplier"]
            self.player_shield = False
            notes.append("Your shield halved it.")
        if self.heal_guard:
            extra *= rules()["heal_guard"]["incoming_multiplier"]
            self.heal_guard = False
            notes.append(f"{target.name} braced while healing - damage halved!")
        result = damage_calculator.calculate(move.power, self.enemy.attack, target.defence, 1.0, 50, element, extra)
        target.hp = max(0, target.hp - result.amount)
        verdict = elemental_system.message(move.element, target.element)
        note = (" " + " ".join(notes)) if notes else ""
        return self._event("attack", f"{self.enemy.name} used {move.name}! {verdict} {result.amount} damage.{note}",
                           side="enemy", move=move.move_id, damage=result.amount,
                           effectiveness=elemental_system.effectiveness(move.element, target.element))

    # ------------------------------------------------------------------ MONSTER
    def switch(self, index):
        self._require("action", "switch")
        forced = self.awaiting == "switch"
        try:
            monster = self.party.switch_to(index)
        except PartyError as error:
            raise BattleError(str(error)) from error
        self.rhythm = 0
        events = [self._event("switch", f"Go, {monster.name}!", side="player")]
        self.awaiting = "action" if forced else "enemy"   # a voluntary switch uses your turn
        return events

    # ------------------------------------------------------------------ BAG
    def item_usable(self, item, target=None):
        info = item_data().get(item)
        if not info or info["use"] not in ("battle", "both"):
            return False, f"{item} can't be used in battle."
        if self.inventory.count(item) <= 0:
            return False, f"You have no {item}."
        target = target or self.active
        effect = info["effect"]
        if effect == "heal" and (target.fainted or target.hp >= target.max_hp):
            return False, f"{target.name} doesn't need healing."
        if effect == "revive" and not target.fainted:
            return False, f"{target.name} hasn't fainted."
        if effect == "focus" and self.focus >= battle_rules.max_focus():
            return False, "Focus is already full."
        if effect == "boost_attack" and self.attack_boost != 1.0:
            return False, "Your attack is already boosted this battle."
        if effect == "boost_defence" and self.defence_boost != 1.0:
            return False, "Your defence is already boosted this battle."
        if effect == "capture":
            return self.can_capture, self.capture_block_reason()
        return True, ""

    def use_item(self, item, target_index=None):
        """Potions, Focus and Revive Crystals. Using one consumes your turn."""
        self._require("action")
        info = item_data().get(item, {})
        if info.get("effect") == "capture":
            raise BattleError("Use begin_capture() for Numeris Cores.")
        target = self.party.party[target_index] if target_index is not None else self.active
        ok, reason = self.item_usable(item, target)
        if not ok:
            raise BattleError(reason)
        self.inventory.take(item)
        effect = info["effect"]
        if effect == "heal":
            healed = target.heal(round(target.max_hp * info["amount"]))
            self.heal_guard = True
            event = self._event("item", f"{item}: {target.name} recovered {healed} HP and braces itself - the next "
                                        "enemy attack is halved!", item=item, amount=healed)
        elif effect == "revive":
            target.revive(info["amount"])
            self.heal_guard = True
            event = self._event("item", f"{item}: {target.name} is back on its feet and braces itself!", item=item)
        elif effect == "boost_attack":
            self.attack_boost = float(info["amount"])
            event = self._event("item", f"{item}: your monsters hit {round((self.attack_boost - 1) * 100)}% harder "
                                        "this battle!", item=item)
        elif effect == "boost_defence":
            self.defence_boost = float(info["amount"])
            event = self._event("item", f"{item}: your monsters take {round((1 - self.defence_boost) * 100)}% less "
                                        "damage this battle!", item=item)
        else:
            gained = min(int(info["amount"]), battle_rules.max_focus() - self.focus)
            self.focus += gained
            event = self._event("item", f"{item}: +{gained} Focus ({self.focus}/{battle_rules.max_focus()}).", item=item)
        self.awaiting = "enemy"
        return [event]

    # ------------------------------------------------------------------ capture
    def capture_block_reason(self):
        allowed, reason = capture_manager.can_capture(self.enemy, self.kind, self.capture_count())
        if not allowed:
            return reason
        if self.party.party_full and self.party.storage_full:
            return "Your party and the Monster Sanctuary are full."
        return ""

    def begin_capture(self, item=None):
        self._require("action")
        reason = self.capture_block_reason()
        if reason:
            raise BattleError(reason)
        held = self.capture_items()
        self.capture_item = item if item in held else held[0]
        self.awaiting = "capture_question"
        return self.enemy.mastery_topic

    def resolve_capture(self, correct):
        self._require("capture_question")
        item = self.capture_item or "Numeris Core"
        self.inventory.take(item)
        bonus = float(item_data().get(item, {}).get("bonus", 0))
        result = capture_manager.attempt(self.enemy, correct, self.rng, bonus)
        events = [self._event("capture_roll", f"Capture chance {round(result.chance)}%...",
                              chance=result.chance, success=result.success)]
        if not result.success:
            events.append(self._event("capture_fail", "The monster escaped the Numeris Core!"))
            self.awaiting = "enemy"
            return events
        self.enemy.hp = max(1, self.enemy.hp)
        placed = self.party.add(self.enemy)
        self.rewards.update(captured=self.enemy, placed=placed)
        where = "joins your party" if placed == "party" else "was sent to the Monster Sanctuary"
        topic = self.enemy.mastery_topic.replace("_", " ")
        events.append(self._event("capture", f"You successfully captured {self.enemy.name}! It {where}. "
                                             f"Maths affinity: {topic}.", placed=placed))
        exp = battle_rules.capture_exp(self.enemy.level)
        events += self._exp_events(reward_manager.distribute_exp([self.active], self.active, exp))
        self.awaiting, self.outcome = "over", "captured"
        return events

    # ------------------------------------------------------------------ RUN
    def run(self):
        self._require("action")
        if not self.can_run:
            raise BattleError("You can't run from this battle!")
        chance = battle_rules.escape_chance(self.active.speed, self.enemy.speed)
        if self.rng.random() * 100 < chance:
            self.awaiting, self.outcome = "over", "fled"
            return [self._event("escape", "You got away safely!", chance=chance)]
        self.awaiting = "enemy"
        return [self._event("escape_fail", "Couldn't get away!", chance=chance)]

    # ------------------------------------------------------------------ results
    def _victory(self):
        events = [self._event("faint", f"{self.enemy.name} fainted!", side="enemy")]
        boss = self.kind == "boss"
        exp = battle_rules.battle_exp(self.enemy.level, boss)
        coins = battle_rules.battle_coins(self.enemy.level, boss)
        self.rewards["coins"] = coins
        events.append(self._event("victory", f"Victory! +{coins} Numera Coins.", coins=coins))
        events += self._exp_events(reward_manager.distribute_exp(self.party.party, self.active, exp))
        self.awaiting, self.outcome = "over", "won"
        return events

    def _exp_events(self, results):
        events = []
        for monster, gained, levels in results:
            self.rewards["exp"].append((monster, gained, levels))
            events.append(self._event("exp", f"{monster.name} gained {gained} EXP.", amount=gained))
            for level_up in levels:
                events.append(self._event("levelup", f"{monster.name} grew to Lv {level_up['level']}!",
                                          level=level_up["level"], gains=level_up["gains"]))
        return events

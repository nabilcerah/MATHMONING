"""Turn-based math battles with hint-first retries and fair consequences."""
import random

import pygame

from config import PALETTE, VIRTUAL_WIDTH
from game.creatures import ENEMIES, STARTERS, WILD_BY_NAME, bond_topic, creature_spec, draw_creature, leader_spec
from game.ui import heart, menu, meter, panel, text, wrapped
from mathematics.solution_steps import steps_for


class Battle:
    ACTIONS = ("ATTACK", "SKILLS", "ITEMS", "AI MENTOR", "FLEE")
    ITEMS = ("Health Potion", "EXP Booster", "Learning Crystal")
    BOSS_TOPICS = ("addition", "subtraction", "multiplication", "division")
    TOPIC_FOR_SKILL = {
        "Addition Spark": "addition", "Solar Addition": "addition",
        "Multiplication Flare": "multiplication", "Multiplication Nova": "multiplication",
        "Multiplication Boulder": "multiplication",
        "Subtraction Splash": "subtraction", "Subtraction Shield": "subtraction",
        "Tidal Subtraction": "subtraction", "Division Current": "division",
        "Division Surge": "division",
        "Times Bolt": "multiplication", "Multiply Storm": "multiplication",
        "Share Gust": "division", "Division Dive": "division",
        "Shard Split": "division", "Fraction Burst": "division",
        "Clockwork Plus": "addition", "Time Split": "subtraction",
        "Prism Bolt": "multiplication", "Times Storm": "multiplication",
        "Opal Gust": "division", "Share Storm": "division",
        "Gem Split": "subtraction", "Facet Burst": "subtraction",
        "Vector Beam": "addition", "Axis Nova": "multiplication",
    }
    ENEMY_TURN_DELAY = 42
    MAX_TRIES = 3
    COMBO_STEP = 0.1          # +10% damage per correct answer in a row
    COMBO_CAP = 5             # ... up to x1.5
    CRITICAL_MULTIPLIER = 1.5
    # A correct first try inside this window is a CRITICAL. It is only ever a bonus:
    # slower answers lose nothing, so nobody is punished for thinking carefully.
    CRITICAL_SECONDS = {"easy": 5, "intermediate": 8, "advanced": 12}
    BOND_THRESHOLD = 0.4      # CAPTURE appears once a wild creature is at or below 40% HP
    BOND_ROUNDS, BOND_NEEDED = 3, 2
    BOND_EXP = 10
    FRIEND_BONUS_STEP, FRIEND_BONUS_CAP = 0.1, 3

    def __init__(self, player, repository, orchestrator, llm_provider, enemy=None, rng=None):
        self.player = player
        self.repository = repository
        self.orchestrator = orchestrator
        self.llm_provider = llm_provider
        self.rng = rng or random.Random()
        self.spec = enemy or self.rng.choice(ENEMIES[:3])
        self.is_boss = self.spec.element == "BOSS"
        self.boss_round = 0
        self.enemy_hp = self.spec.hp
        self.enemy_max_hp = self.spec.hp
        self.player_spec = creature_spec(player.creature, player.level)
        self.state = "menu"
        self.selected = 0
        self.sub_selected = 0
        self.question = None
        self.answer = ""
        intro = (f"{self.spec.name}, the Arithmetic Beast, blocks the arch!" if self.is_boss
                 else f"A wild {self.spec.name} appears!")
        self.feedback = intro
        self.wrong_count = 0
        self.damage_multiplier = 1.0
        self.next_victory_bonus = 0
        self.last_question = None
        self.mentor_future = None
        self.outcome = None
        self.closed = False
        self.level_message = ""
        self._inventory = None
        # Presentation-only state: eased bars, hit flashes, shakes and popups.
        self.age = 0
        self.timer = 0
        self.enemy_hp_shown = float(self.enemy_hp)
        self.player_hp_shown = float(player.hp)
        self.enemy_flash = self.player_flash = 0
        self.enemy_shake = self.player_shake = 0
        self.answer_shake = 0
        self.popups = []
        # Sprite poses: (pose name, frames left; -1 holds). "idle" cycles the breathing frames.
        self.player_pose = ("idle", 0)
        self.enemy_pose = ("burst", 40) if self.is_boss else ("idle", 0)
        # Combo state: grows with each correct answer, cools by one step on a miss.
        self.combo = 0
        self.best_combo = 0
        self.criticals = 0
        self.question_frames = 0
        self.combo_pulse = 0
        self.screen_flash = 0
        # Capturing: weakened wild creatures can join your team through a Capture Challenge.
        flags = repository.world_flags(player.player_id) if hasattr(repository, "world_flags") else set()
        self.friends = {flag.split(":", 1)[1] for flag in flags if flag.startswith("dex_friend:")}
        self.flags = set(flags)
        self.player_spec = self._leader()
        self.bond = None
        self.walkthrough = None   # "solve it together" after the last try is used up
        self.solve_future = None
        self.ko_offer = False     # a knocked-out wild MATHMON can still be captured
        self.ko_selected = 0
        self.is_trainer = False  # a rival's MATHMON belongs to them and cannot be captured
        self.bond_cooldown = 0
        self.bond_offered = False
        if not self.is_boss and hasattr(repository, "set_world_flag"):
            repository.set_world_flag(player.player_id, f"dex_seen:{self.spec.name}")

    # ------------------------------------------------------------------ update
    def update(self):
        self.age += 1
        if self.mentor_future and self.mentor_future.done():
            try:
                response = self.mentor_future.result()
                if response:
                    self.feedback = response
            except Exception:
                pass
            self.mentor_future = None
        if self.solve_future and self.solve_future.done():
            try:
                steps = self.solve_future.result()
                if self.walkthrough and self.walkthrough["shown"] <= 1 and steps:
                    self.walkthrough["steps"] = list(steps)
            except Exception:
                pass
            self.solve_future = None
        if self.state == "question":
            self.question_frames += 1
        if self.state == "resolving":
            self.timer -= 1
            if self.timer <= 0:
                self._enemy_turn()
        self.enemy_hp_shown = self._ease(self.enemy_hp_shown, self.enemy_hp)
        self.player_hp_shown = self._ease(self.player_hp_shown, self.player.hp)
        for name in ("enemy_flash", "player_flash", "enemy_shake", "player_shake", "answer_shake",
                     "combo_pulse", "screen_flash"):
            value = getattr(self, name)
            if value:
                setattr(self, name, value - 1)
        for side in ("player_pose", "enemy_pose"):
            pose, frames = getattr(self, side)
            if frames > 0:
                setattr(self, side, (pose, frames - 1) if frames > 1 else ("idle", 0))
        for popup in self.popups:
            popup["age"] += 1
        self.popups = [p for p in self.popups if p["age"] < p.get("life", 50)]

    @staticmethod
    def _ease(shown, actual):
        if abs(shown - actual) < 0.15:
            return float(actual)
        return shown + (actual - shown) * 0.12

    def _pose(self, side, pose, frames=24):
        """frames=-1 holds the pose for the rest of the battle (victory, rest)."""
        setattr(self, f"{side}_pose", (pose, frames))

    def _popup(self, message, x, y, color, size=15, life=50):
        self.popups.append({"text": message, "x": x, "y": y, "color": color, "age": 0, "size": size, "life": life})

    # ------------------------------------------------------------------- input
    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if self.state == "walkthrough":
            self._walkthrough_key(event)
        elif self.state == "ko_offer":
            if event.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                self.ko_selected = 1 - self.ko_selected
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.ko_selected == 0:
                    self.ko_offer = True
                    self._start_bond()
                    self.feedback = (f"{self.spec.name} is too tired to run! Get {self.BOND_NEEDED} of "
                                     f"{self.BOND_ROUNDS} right on the first try to capture it.")
                else:
                    self._victory()
        elif self.state == "question":
            self._question_key(event)
        elif self.state in ("skills", "items"):
            self._list_key(event)
        elif self.state == "resolving":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.timer = 0
        elif self.state == "mentor":
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                self.state = "menu"
            elif event.key == pygame.K_h and self.question:
                self.feedback = self.orchestrator.tutor.hint(self.question)
        elif self.state == "over":
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                self.closed = True
        elif self.state == "menu":
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.actions())
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.actions())
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._choose_action()

    def actions(self):
        if self.can_befriend:
            return ("ATTACK", "CAPTURE", "SKILLS", "ITEMS", "AI MENTOR", "FLEE")
        return self.ACTIONS

    @property
    def can_befriend(self):
        return (not self.is_boss and not self.is_trainer and self.spec.name not in self.friends and 0 < self.enemy_hp
                and self.enemy_hp <= self.enemy_max_hp * self.BOND_THRESHOLD and not self.bond_cooldown)

    def _question_key(self, event):
        if event.key == pygame.K_ESCAPE:
            self.bond = None
            self.state, self.feedback = "menu", "Take your time. Choose another action when ready."
        elif event.key == pygame.K_BACKSPACE:
            self.answer = self.answer[:-1]
        elif event.key == pygame.K_h:
            self.feedback = self.orchestrator.tutor.hint(self.question)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.answer.strip():
                self._submit()
        elif event.unicode and event.unicode in "0123456789.-/" and len(self.answer) < 14:
            self.answer += event.unicode

    def _choose_action(self):
        actions = self.actions()
        action = actions[min(self.selected, len(actions) - 1)]
        if action == "ATTACK":
            self._start_question()
        elif action == "CAPTURE":
            self._start_bond()
        elif action == "SKILLS":
            if self.player.level < 2:
                self.feedback = "Your creature is learning its first moves. Skills unlock at Level 2."
            else:
                self.state, self.sub_selected = "skills", 0
        elif action == "ITEMS":
            self._inventory = None
            self.state, self.sub_selected = "items", 0
        elif action == "AI MENTOR":
            self.state = "mentor"
            if self.question:
                fallback = self.orchestrator.tutor.mentor(self.question,
                    self.repository.get_learning_profile(self.player.player_id))
                self.feedback = self.orchestrator.tutor.hint(self.question)
                self.mentor_future = self.llm_provider.explain_async(self.question, self.answer, fallback)
            else:
                self.feedback = "The mentor says: every step builds a stronger mind. Try ATTACK for a practice question."
        elif action == "FLEE":
            self.outcome, self.state, self.feedback = "fled", "over", "You retreat to the trail. Your learning progress is safe."

    # ------------------------------------------------------------------- rules
    def _start_question(self, topic=None, multiplier=1.0):
        if self.is_boss:
            topic = self.BOSS_TOPICS[self.boss_round % len(self.BOSS_TOPICS)]
        result = self.orchestrator.next_question(self.player.player_id, topic)
        self.question = self._at_least(result["question"], self.spec.min_difficulty)
        self.last_question = self.question
        self.answer = ""
        self.wrong_count = 0
        self.damage_multiplier = multiplier
        self.question_frames = 0
        self.state = "question"
        self.feedback = f"{self.question.difficulty.title()} challenge. Press H for a hint."

    # ------------------------------------------------------------- befriending
    def _start_bond(self):
        self.bond = {"round": 0, "hearts": 0, "results": []}
        self._next_bond_question()
        self.feedback = (f"Capture Challenge! Get {self.BOND_NEEDED} of {self.BOND_ROUNDS} right on the first try "
                         f"to capture {self.spec.name}.")

    def _next_bond_question(self):
        topic = bond_topic(self.spec, self.rng)
        question = self.orchestrator.next_question(self.player.player_id, topic)["question"]
        self.question = self.last_question = self._at_least(question, self.spec.min_difficulty)
        self.answer = ""
        self.wrong_count = 0
        self.question_frames = 0
        self.state = "question"

    def _submit_bond(self):
        decision = self.orchestrator.submit_answer(self.player.player_id, self.question, self.answer)
        bond = self.bond
        bond["round"] += 1
        bond["results"].append(decision.correct)
        self.answer = ""
        if decision.correct:
            bond["hearts"] += 1
            self._popup("+1 HOLD", 258, 30, PALETTE["mint"], size=16)
            self._pose("enemy", "happy", 30)
            message = f"Correct! The capture holds..."
        else:
            self.answer_shake = 14
            message = f"Not quite. {self.question.explanation}"
        misses = bond["round"] - bond["hearts"]
        if bond["hearts"] >= self.BOND_NEEDED:
            self._befriended()
        elif misses > self.BOND_ROUNDS - self.BOND_NEEDED and self.ko_offer:
            self.bond = None
            self._victory()
            self.feedback = f"{message} {self.spec.name} slipped away into the grass. " + self.feedback
        elif misses > self.BOND_ROUNDS - self.BOND_NEEDED:
            self.bond, self.bond_cooldown, self.state = None, 1, "menu"
            self.feedback = (f"{message} {self.spec.name} broke free! Land one more ATTACK, "
                             "then try CAPTURE again.")
        else:
            self._next_bond_question()
            self.feedback = message

    def _befriended(self):
        name = self.spec.name
        self.friends.add(name)
        if hasattr(self.repository, "set_world_flag"):
            self.repository.set_world_flag(self.player.player_id, f"dex_friend:{name}")
        evolution = self._grant_exp(self.BOND_EXP + self.next_victory_bonus)
        self.repository.save_player(self.player)
        self.bond = None
        self.outcome, self.state = "befriended", "over"
        self.screen_flash = 8
        self._popup("CAPTURED!", 160, 58, PALETTE["mint"], size=22, life=70)
        self._pose("enemy", "happy", -1)
        self._pose("player", "happy", -1)
        topic = self.spec.topic or "every"
        self.feedback = (f"Gotcha! {name} was captured and joins your team! +{self.BOND_EXP + self.next_victory_bonus} EXP."
                         f"{evolution} It boosts your {topic} attacks. Press M to see your MathDex.")

    def friend_bonus(self, topic):
        count = sum(1 for name in self.friends if WILD_BY_NAME.get(name) and WILD_BY_NAME[name].topic == topic)
        return 1 + self.FRIEND_BONUS_STEP * min(count, self.FRIEND_BONUS_CAP)

    LEVELS = ("easy", "intermediate", "advanced")

    def _at_least(self, question, minimum):
        """Crystal Realm monsters never ask below their minimum difficulty."""
        if not minimum or self.LEVELS.index(question.difficulty) >= self.LEVELS.index(minimum):
            return question
        generator = self.orchestrator.questions.generator
        profile = self.repository.get_learning_profile(self.player.player_id)
        return generator.generate(minimum, question.topic, profile)

    @property
    def capturable_after_ko(self):
        return not self.is_boss and not self.is_trainer and self.spec.name not in self.friends

    # ------------------------------------------------- "solve it together" walkthrough
    WALK_DAMAGE = 0.5  # finishing a walkthrough still lands a gentle "teamwork" hit

    def _start_walkthrough(self):
        """Out of tries: the mentor solves *this* question step by step, then the child types the answer."""
        steps = steps_for(self.question)
        self.walkthrough = {"steps": steps, "shown": 1, "question": self.question, "typing": False}
        self.answer = ""
        self.state = "walkthrough"
        self.mentor_future = None
        if self.llm_provider is not None and getattr(self.llm_provider, "available", False):
            self.solve_future = self.llm_provider.solve_async(self.question, steps)
        self.feedback = "No worries - let's solve it together, one step at a time."

    def _walkthrough_key(self, event):
        walk = self.walkthrough
        if not walk["typing"]:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                if walk["shown"] < len(walk["steps"]):
                    walk["shown"] += 1
                else:
                    walk["typing"] = True
                    self.feedback = "Your turn: type the answer you just found, then press ENTER."
            return
        if event.key == pygame.K_BACKSPACE:
            self.answer = self.answer[:-1]
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.answer.strip():
            from mathematics.answer_validator import AnswerValidator
            if AnswerValidator.check(self.answer, walk["question"].answer):
                self._finish_walkthrough()
            else:
                self.answer = ""
                self.answer_shake = 14
                self.feedback = f"Look at the last step again - it shows the answer {walk['question'].answer}."
        elif event.unicode and event.unicode in "0123456789.-/" and len(self.answer) < 14:
            self.answer += event.unicode

    def _finish_walkthrough(self):
        # Not recorded as a correct attempt (the answer was shown), so no EXP, but the team still acts.
        question = self.walkthrough["question"]
        self.walkthrough = None
        self.wrong_count = 0
        self.answer = ""
        base = question.base_damage + self.player.level + self.player_spec.attack // 2
        damage = max(2, round(base * self.WALK_DAMAGE))
        self.enemy_hp = max(0, self.enemy_hp - damage)
        self.enemy_flash, self.enemy_shake = 12, 8
        self._popup(f"-{damage}", 258, 14, PALETTE["mint"])
        self._pose("player", "attack", 24)
        self.feedback = f"You got it! Teamwork hit for {damage} damage. Next time you'll solve one like it on your own."
        if self.enemy_hp <= 0:
            if self.capturable_after_ko:
                self.state, self.ko_selected = "ko_offer", 0
                self.feedback += f" {self.spec.name} is exhausted... capture it?"
                return
            self._victory()
            return
        self._queue_enemy_turn()

    @property
    def combo_multiplier(self):
        return 1 + self.COMBO_STEP * min(self.combo, self.COMBO_CAP)

    def critical_window(self):
        return self.CRITICAL_SECONDS.get(self.question.difficulty, 5) * 60 if self.question else 0

    def _is_critical(self):
        # question_frames stays 0 when nothing has been timed (e.g. scripted turns).
        return self.wrong_count == 0 and 0 < self.question_frames <= self.critical_window()

    def _submit(self):
        if self.bond:
            self._submit_bond()
            return
        decision = self.orchestrator.submit_answer(self.player.player_id, self.question, self.answer)
        if not decision.correct:
            self.wrong_count += 1
            self.answer = ""
            self.answer_shake = 14
            cooled = ""
            if self.combo:
                self.combo -= 1
                cooled = f" Your combo cools to x{self.combo_multiplier:.1f}." if self.combo else " Your combo cools down."
            if self.wrong_count >= self.MAX_TRIES:
                self._start_walkthrough()
            else:
                self.feedback = decision.feedback + cooled
            return
        self.level_message = self._grant_exp(decision.exp_reward)
        critical = self._is_critical()
        combo_bonus = self.combo_multiplier  # earned by the answers before this one
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        self.combo_pulse = 24
        friends = self.friend_bonus(self.question.topic)
        multiplier = self.damage_multiplier * combo_bonus * friends * (self.CRITICAL_MULTIPLIER if critical else 1)
        base = self.question.base_damage + self.player.level + self.player_spec.attack // 2
        damage = max(4, round(base * multiplier))
        self.enemy_hp = max(0, self.enemy_hp - damage)
        self.enemy_flash, self.enemy_shake = 14, 20 if critical else 12
        self._popup(f"-{damage}", 258, 14, PALETTE["coral"] if critical else PALETTE["gold"])
        self._pose("player", "burst" if critical else "attack", 30)
        self._pose("enemy", "hurt", 24)
        if critical:
            self.criticals += 1
            self.screen_flash = 10
            self._popup("CRITICAL!", 160, 58, PALETTE["gold"], size=22, life=60)
        elif self.combo >= 2:
            self._popup(f"{self.combo} IN A ROW!", 160, 60, PALETTE["cream"], size=16)
        if decision.exp_reward:
            self._popup(f"+{decision.exp_reward} EXP", 110, 112, PALETTE["sky"])
        if self.is_boss:
            self.boss_round += 1
        tags = []
        if critical:
            tags.append("CRITICAL!")
        if combo_bonus > 1:
            tags.append(f"Combo x{combo_bonus:.1f}!")
        if friends > 1:
            tags.append(f"Team +{round((friends - 1) * 100)}%!")
        prefix = " ".join(tags) + " " if tags else ""
        self.feedback = f"Correct! {prefix}{self.player_spec.name} lands {damage} damage.{self.level_message}"
        self.repository.save_player(self.player)
        self.answer = ""
        if self.bond_cooldown:
            self.bond_cooldown -= 1
        if self.enemy_hp <= 0:
            if self.capturable_after_ko:
                self.state, self.ko_selected = "ko_offer", 0
                self.feedback += f" {self.spec.name} is exhausted but still here... capture it?"
                self._pose("enemy", "hurt", -1)
                return
            self._victory()
            return
        if self.can_befriend and not self.bond_offered:
            self.bond_offered = True
            self.feedback += f" {self.spec.name} is worn out... try CAPTURE!"
        self._queue_enemy_turn()

    def _victory(self):
        bonus = 20 if self.is_boss else 8
        total = bonus + self.next_victory_bonus
        evolution = self._grant_exp(total)
        self.player.hp = min(self.player.max_hp, self.player.hp + 4)
        self.repository.save_player(self.player)
        self.outcome, self.state = "won", "over"
        self._pose("player", "happy", -1)
        booster = f" (+{self.next_victory_bonus} from your booster)" if self.next_victory_bonus else ""
        flair = f" Best streak: {self.best_combo} in a row!" if self.best_combo >= 2 else ""
        if self.criticals:
            flair += f" Criticals: {self.criticals}."
        self.feedback = f"{self.spec.name} is defeated! +{total} EXP{booster}.{evolution}{flair} Your creature rests and recovers 4 HP."

    def _leader(self):
        return leader_spec(self.player, getattr(self, "flags", set()))

    def _grant_exp(self, amount):
        old_form = self.player_spec.name
        leveled = self.player.add_exp(amount)
        self.player_spec = self._leader()
        if self.player_spec.name != old_form:
            return f" EVOLUTION! {old_form} became {self.player_spec.name}!"
        return f" LEVEL UP! Lv {self.player.level}!" if leveled else ""

    def _queue_enemy_turn(self):
        self.state = "resolving"
        self.timer = self.ENEMY_TURN_DELAY

    def _enemy_turn(self):
        damage = self.rng.randint(max(1, self.spec.attack - 2), self.spec.attack)
        self.player.hp = max(0, self.player.hp - damage)
        self.player_flash, self.player_shake = 14, 12
        self._popup(f"-{damage}", 62, 62, PALETTE["coral"])
        self._pose("enemy", "attack", 26)
        self._pose("player", "hurt", 24)
        self.repository.save_player(self.player)
        self.feedback += f" {self.spec.name} answers with {damage} damage."
        self.state = "menu"
        if self.player.hp == 0:
            self.player.hp = max(1, self.player.max_hp // 2)
            self.repository.save_player(self.player)
            self.outcome, self.state = "defeated", "over"
            self._pose("player", "hurt", -1)
            self._pose("enemy", "happy", -1)
            self.feedback = "Your creature needs a rest. The ranger restores half its HP; your learning progress is saved."

    def inventory(self):
        if self._inventory is None:
            self._inventory = self.repository.inventory(self.player.player_id)
        return self._inventory

    def _list_key(self, event):
        choices = self._skills() if self.state == "skills" else self.ITEMS
        if event.key == pygame.K_ESCAPE:
            self.state = "menu"
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.sub_selected = (self.sub_selected - 1) % len(choices)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.sub_selected = (self.sub_selected + 1) % len(choices)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.state == "skills":
                skill = choices[self.sub_selected]
                self._start_question(self.TOPIC_FOR_SKILL.get(skill, "addition"), 1.35)
            else:
                self._use_item(choices[self.sub_selected])

    def _skills(self):
        return self.player_spec.skills

    def _use_item(self, item):
        self._inventory = None
        self.state = "menu"
        if item == "Learning Crystal":
            if not self.last_question:
                self.feedback = "The crystal stays dim. Answer a question first, then it can explain the idea."
            elif not self.repository.use_item(self.player.player_id, item):
                self.feedback = "No Learning Crystals left."
            else:
                self.feedback = self.orchestrator.tutor.explain(self.last_question)
                self.repository.add_recommendation(self.player.player_id, "Use a hint, then explain the steps in your own words.")
            return
        if item == "Health Potion":
            if self.player.hp >= self.player.max_hp:
                self.feedback = "HP is already full. Save the potion for later."
                return
            if not self.repository.use_item(self.player.player_id, item):
                self.feedback = "No Health Potions left."
                return
            healed = min(14, self.player.max_hp - self.player.hp)
            self.player.hp += healed
            self._popup(f"+{healed}", 62, 62, PALETTE["mint"])
            self._pose("player", "special", 30)
            self.feedback = f"A Health Potion restores {healed} HP."
        else:
            if not self.repository.use_item(self.player.player_id, item):
                self.feedback = "No EXP Boosters left."
                return
            self.next_victory_bonus += 10
            self.feedback = "The EXP Booster will add +10 EXP after this battle."
        self.repository.save_player(self.player)
        self._queue_enemy_turn()

    # -------------------------------------------------------------------- draw
    @staticmethod
    def _heart(surface, x, y, state):
        """Filled for a correct bond answer, dim for a miss, outline while pending."""
        color = PALETTE["mint"] if state else (PALETTE["deep"] if state is False else PALETTE["muted"])
        heart(surface, x, y, color, filled=state is not None)

    def _draw_combo_badge(self, surface, frame):
        if self.combo < 1:
            return
        heat = min(self.combo, self.COMBO_CAP)
        color = (PALETTE["cream"], PALETTE["cream"], PALETTE["gold"], PALETTE["gold"], PALETTE["coral"], PALETTE["coral"])[heat]
        grow = 2 if self.combo_pulse > 12 else (1 if self.combo_pulse else 0)
        grow = 1 if grow else 0
        # Sits in the top-right of the player's status card, clear of the larger sprites.
        rect = pygame.Rect(240 - grow, 74 - grow, 64 + grow * 2, 9 + grow * 2)
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, PALETTE["ink"], rect.inflate(-2, -2))
        text(surface, f"COMBO x{self.combo_multiplier:.1f}", (244, 75), 8, color)
        for i in range(self.COMBO_CAP):
            lit = i < heat
            flicker = 1 if lit and heat == self.COMBO_CAP and (frame // 4 + i) % 3 == 0 else 0
            pygame.draw.rect(surface, color if lit else PALETTE["deep"], (284 + i * 4, 76 - flicker, 3, 5 + flicker))

    @staticmethod
    def _frame_pose(pose, frame):
        """Idle breathes through the three idle frames; other poses hold."""
        if pose == "idle":
            return ("idle", "idle2", "idle3", "idle2")[(frame // 18) % 4]
        return pose

    def _shake(self, frames):
        return ((frames % 4) - 1.5) * 2 if frames else 0

    def draw(self, surface, frame=0):
        # Layered forest arena with blocky, original scenery.
        surface.fill((76, 126, 132))
        pygame.draw.rect(surface, (97, 157, 110), (0, 78, 320, 54))
        for i in range(12):
            x = (i * 31 + frame // 4) % 350 - 15
            pygame.draw.rect(surface, (53, 101, 75), (x, 47 + (i % 3) * 6, 18, 34))
            pygame.draw.rect(surface, (69, 132, 83), (x - 5, 40 + (i % 3) * 6, 27, 13))
        pygame.draw.ellipse(surface, (143, 177, 104), (-12, 95, 150, 38))
        pygame.draw.ellipse(surface, (135, 168, 97), (179, 65, 160, 37))
        # Ground shadows anchor the creatures to their platforms.
        pygame.draw.ellipse(surface, (112, 146, 84), (234, 62, 48, 8))
        pygame.draw.ellipse(surface, (118, 150, 86), (36, 113, 52, 10))

        # Opponent slides in from the right; fades down when defeated.
        slide = max(0, 30 - self.age) * 4
        ex = 258 + slide + self._shake(self.enemy_shake)
        if not (self.outcome == "won" and self.state == "over"):
            enemy_pose = "windup" if self.state == "resolving" and self.enemy_pose[0] == "idle" else self.enemy_pose[0]
            draw_creature(surface, self.spec, (ex, 67), 46, self._frame_pose(enemy_pose, frame), flip=True,
                          tint=PALETTE["white"] if self.enemy_flash % 4 >= 2 else None)
        if self.outcome == "befriended":
            self._heart(surface, int(ex) - 4, 8 - (frame // 10) % 3, True)
        panel(surface, (8, 8, 143, 43), PALETTE["night"], PALETTE["gold"] if self.is_boss else None)
        text(surface, self.spec.name, (15, 12), 13, PALETTE["white"])
        text(surface, self.spec.element, (15, 25), 9, PALETTE["muted"])
        text(surface, f"{self.enemy_hp}/{self.enemy_max_hp}", (139, 25), 9, PALETTE["muted"], align="right")
        meter(surface, 15, 39, 124, 6, self.enemy_hp_shown, self.enemy_max_hp, PALETTE["coral"])

        # Player creature and status card.
        px = 62 - slide + self._shake(self.player_shake)
        draw_creature(surface, self.player_spec, (px, 120), 52, self._frame_pose(self.player_pose[0], frame),
                      tint=PALETTE["coral"] if self.player_flash % 4 >= 2 else None)
        panel(surface, (143, 71, 168, 46), PALETTE["night"])
        text(surface, f"{self.player_spec.name}  Lv {self.player.level}", (151, 75), 12, PALETTE["white"])
        text(surface, f"{self.player.hp}/{self.player.max_hp}", (298, 84), 9, PALETTE["cream"], align="right")
        meter(surface, 151, 93, 147, 7, self.player_hp_shown, self.player.max_hp, PALETTE["mint"], "HP", warn=True)
        meter(surface, 151, 108, 147, 5, self.player.exp, self.player.next_level_exp, PALETTE["sky"], "EXP")

        self._draw_combo_badge(surface, frame)
        for popup in self.popups:
            rise = popup["age"] // 2
            life = popup.get("life", 50)
            size = popup.get("size", 15)
            if popup["age"] < 6 and size > 15:
                size += (6 - popup["age"]) * 2  # big text punches in, then settles
            if popup["age"] < life - 10 or popup["age"] % 4 < 2:
                text(surface, popup["text"], (popup["x"], popup["y"] - rise), size, popup["color"],
                     center=True, shadow=PALETTE["ink"])

        # Dialogue/question at lower left, action list at lower right.
        if self.state == "walkthrough" and self.walkthrough:
            self._draw_walkthrough(surface, frame)
            self._draw_footer(surface, frame)
            return
        panel(surface, (7, 128, 193, 83), PALETTE["night"])
        if self.state == "question" and self.question:
            if self.bond:
                header = f"CAPTURE CHALLENGE  •  {self.question.topic.upper()}  {self.bond['round'] + 1}/{self.BOND_ROUNDS}"
                text(surface, header, (14, 134), 10, PALETTE["mint"])
            else:
                text(surface, f"{self.question.topic.upper()}  •  {self.question.difficulty.upper()}", (14, 134), 10, PALETTE["gold"])
            wrapped(surface, self.question.prompt, (14, 148, 174, 20), 17, PALETTE["white"], 17, 1)
            jiggle = self._shake(self.answer_shake)
            box = PALETTE["coral"] if self.answer_shake else PALETTE["ink"]
            pygame.draw.rect(surface, box, (13 + jiggle, 171, 176, 23))
            pygame.draw.rect(surface, PALETTE["ink"], (14 + jiggle, 172, 174, 21))
            caret = "_" if frame % 50 < 28 else " "
            text(surface, "> " + self.answer + caret, (19 + jiggle, 177), 15, PALETTE["cream"])
            wrapped(surface, self.feedback, (14, 196, 178, 12), 9, PALETTE["mint"], 10, 1)
        else:
            wrapped(surface, self.feedback, (15, 137, 177, 63), 12, PALETTE["white"], 13, 5)
            if self.state == "mentor" and self.mentor_future and not self.mentor_future.done():
                dots = "." * (1 + frame // 15 % 3)
                text(surface, "Mentor is thinking" + dots, (15, 197), 9, PALETTE["gold"])

        if self.state == "menu":
            actions = self.actions()
            disabled = (actions.index("SKILLS"),) if self.player.level < 2 else ()
            highlight = (actions.index("CAPTURE"),) if "CAPTURE" in actions else ()
            menu(surface, (207, 128, 106, 83), actions, min(self.selected, len(actions) - 1), 10, frame,
                 disabled, 15 if len(actions) <= 5 else 12, highlight)
        elif self.state == "skills":
            menu(surface, (207, 128, 106, 83), list(self._skills()), self.sub_selected, 9, frame)
        elif self.state == "items":
            stock = self.inventory()
            labels = [f"{name}  x{stock.get(name, 0)}" for name in self.ITEMS]
            empty = tuple(i for i, name in enumerate(self.ITEMS) if not stock.get(name))
            menu(surface, (207, 128, 106, 83), labels, self.sub_selected, 9, frame, empty)
        elif self.state == "question" and self.bond:
            panel(surface, (206, 128, 107, 83), PALETTE["night"], PALETTE["mint"])
            text(surface, "CAPTURE!", (214, 137), 11, PALETTE["mint"])
            wrapped(surface, f"One try per question. {self.BOND_NEEDED} right and {self.spec.name} is yours!",
                    (214, 151, 91, 30), 9, PALETTE["white"], 10, 3)
            text(surface, "TRUST", (214, 186), 9, PALETTE["muted"])
            results = self.bond["results"]
            for i in range(self.BOND_ROUNDS):
                state = results[i] if i < len(results) else None
                self._heart(surface, 214 + i * 14, 197, state)
        elif self.state == "question":
            panel(surface, (206, 128, 107, 83), PALETTE["night"])
            text(surface, "BATTLE TIP", (214, 137), 11, PALETTE["gold"])
            wrapped(surface, "Type your answer, then ENTER. H gives a hint. Mistakes never hurt you.",
                    (214, 151, 91, 30), 9, PALETTE["white"], 10, 3)
            window = self.critical_window()
            left = max(0, window - self.question_frames)
            if self.wrong_count == 0 and left:
                # A bonus that quietly fades - never a countdown to failure.
                text(surface, "QUICK BONUS", (214, 183), 8, PALETTE["gold"])
                pygame.draw.rect(surface, PALETTE["ink"], (262, 185, 44, 4))
                pygame.draw.rect(surface, PALETTE["gold"], (262, 185, max(1, round(44 * left / window)), 4))
            else:
                text(surface, "Take your time!", (214, 183), 8, PALETTE["muted"])
            tries_left = self.MAX_TRIES - self.wrong_count
            for i in range(self.MAX_TRIES):
                color = PALETTE["mint"] if i < tries_left else PALETTE["deep"]
                pygame.draw.rect(surface, color, (214 + i * 9, 198, 6, 6))
            text(surface, "TRIES", (244, 197), 9, PALETTE["muted"])
        elif self.state == "ko_offer":
            menu(surface, (207, 128, 106, 83), ["CAPTURE!", "LET IT GO"], self.ko_selected, 10, frame,
                 highlight=(0,))
        elif self.state == "resolving":
            panel(surface, (207, 128, 106, 83), PALETTE["night"])
            text(surface, f"{self.spec.name[:10]}", (216, 143), 11, PALETTE["coral"])
            text(surface, "is winding up" + "." * (1 + frame // 10 % 3), (216, 158), 10, PALETTE["white"])
        else:
            panel(surface, (207, 128, 106, 83), PALETTE["night"])
            title = {"won": "VICTORY!", "defeated": "RESTING", "fled": "ESCAPED",
                     "befriended": "CAPTURED!"}.get(self.outcome, "ENTER")
            text(surface, title, (216, 143), 12, PALETTE["gold"])
            text(surface, "ENTER to continue" if self.outcome else "ENTER to go back", (216, 160), 9, PALETTE["white"])
        self._draw_footer(surface, frame)

    def _draw_footer(self, surface, frame):
        if self.screen_flash:
            flash = pygame.Surface(surface.get_size())
            flash.fill(PALETTE["white"])
            flash.set_alpha(18 * self.screen_flash)
            surface.blit(flash, (0, 0))
        walk = self.walkthrough
        if self.state == "walkthrough" and walk:
            hints = "TYPE THE ANSWER   ENTER CHECK" if walk["typing"] else "ENTER: NEXT STEP"
        else:
            hints = {
                "question": "TYPE ANSWER   ENTER SUBMIT   H HINT   ESC BACK",
                "resolving": "ENTER SKIP",
            }.get(self.state, "UP/DOWN SELECT   ENTER CHOOSE   ESC BACK")
        text(surface, hints, (160, 226), 9, PALETTE["cream"], center=True)

    def _draw_walkthrough(self, surface, frame):
        """Full-width panel: the missed question, solved one revealed step at a time."""
        walk = self.walkthrough
        panel(surface, (7, 128, 306, 83), PALETTE["night"], PALETTE["sky"])
        text(surface, "LET'S SOLVE IT TOGETHER", (14, 133), 10, PALETTE["sky"])
        text(surface, walk["question"].prompt, (14, 145), 13, PALETTE["white"])
        y = 160
        for index, step in enumerate(walk["steps"][:walk["shown"]]):
            last = index == walk["shown"] - 1
            color = PALETTE["gold"] if last and not walk["typing"] else PALETTE["cream"]
            pygame.draw.rect(surface, PALETTE["sky"], (14, y + 3, 3, 3))
            lines = wrapped(surface, step, (21, y, 286, 22), 9, color, 10, 2)
            y += 10 * lines + 1
            if y > 200:
                break
        if walk["typing"]:
            jiggle = self._shake(self.answer_shake)
            box = PALETTE["coral"] if self.answer_shake else PALETTE["gold"]
            pygame.draw.rect(surface, box, (219 + jiggle, 141, 88, 17))
            pygame.draw.rect(surface, PALETTE["ink"], (220 + jiggle, 142, 86, 15))
            caret = "_" if frame % 50 < 28 else " "
            text(surface, "> " + self.answer + caret, (224 + jiggle, 144), 12, PALETTE["cream"])
        elif walk["shown"] < len(walk["steps"]) and frame % 40 < 26:
            x, yy = 300, 202
            pygame.draw.polygon(surface, PALETTE["sky"], [(x, yy), (x + 6, yy), (x + 3, yy + 4)])

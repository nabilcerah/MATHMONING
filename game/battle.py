"""Turn-based math battles with hint-first retries and fair consequences."""
import random

import pygame

from config import PALETTE, VIRTUAL_WIDTH
from game.creatures import ENEMIES, STARTERS, creature_spec, pixel_monster
from game.ui import menu, meter, panel, text, wrapped


class Battle:
    ACTIONS = ("ATTACK", "SKILLS", "ITEMS", "AI MENTOR", "FLEE")
    BOSS_TOPICS = ("addition", "subtraction", "multiplication", "division")
    TOPIC_FOR_SKILL = {
        "Addition Spark": "addition", "Solar Addition": "addition",
        "Multiplication Flare": "multiplication", "Multiplication Nova": "multiplication",
        "Subtraction Splash": "subtraction", "Subtraction Shield": "subtraction",
        "Tidal Subtraction": "subtraction", "Division Current": "division",
        "Division Surge": "division",
    }

    def __init__(self, player, repository, orchestrator, llm_provider, enemy=None, rng=None):
        self.player = player
        self.repository = repository
        self.orchestrator = orchestrator
        self.llm_provider = llm_provider
        self.rng = rng or random.Random()
        self.spec = enemy or self.rng.choice(ENEMIES[:3])
        self.boss_round = 0
        self.enemy_hp = self.spec.hp
        self.enemy_max_hp = self.spec.hp
        self.player_spec = creature_spec(player.creature, player.level)
        self.state = "menu"
        self.selected = 0
        self.sub_selected = 0
        self.question = None
        self.answer = ""
        self.feedback = f"A wild {self.spec.name} appears!"
        self.wrong_count = 0
        self.damage_multiplier = 1.0
        self.next_victory_bonus = 0
        self.last_question = None
        self.mentor_future = None
        self.outcome = None
        self.closed = False
        self.level_message = ""

    def update(self):
        if self.mentor_future and self.mentor_future.done():
            try:
                response = self.mentor_future.result()
                if response:
                    self.feedback = response
            except Exception:
                pass
            self.mentor_future = None

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if self.state == "question":
            self._question_key(event)
        elif self.state in ("skills", "items"):
            self._list_key(event)
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
                self.selected = (self.selected - 1) % len(self.ACTIONS)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.ACTIONS)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._choose_action()

    def _question_key(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state, self.feedback = "menu", "Take your time. Choose another action when ready."
        elif event.key == pygame.K_BACKSPACE:
            self.answer = self.answer[:-1]
        elif event.key == pygame.K_h:
            self.feedback = self.orchestrator.tutor.hint(self.question)
        elif event.key == pygame.K_RETURN:
            if self.answer.strip():
                self._submit()
        elif event.unicode and event.unicode in "0123456789.-/" and len(self.answer) < 14:
            self.answer += event.unicode

    def _choose_action(self):
        action = self.ACTIONS[self.selected]
        if action == "ATTACK":
            self._start_question()
        elif action == "SKILLS":
            if self.player.level < 2:
                self.feedback = "Your creature is learning its first moves. Skills unlock at Level 2."
            else:
                self.state, self.sub_selected = "skills", 0
        elif action == "ITEMS":
            self.state, self.sub_selected = "items", 0
        elif action == "AI MENTOR":
            self.state = "mentor"
            if self.question:
                fallback = self.orchestrator.tutor.mentor(self.question,
                    self.repository.get_learning_profile(self.player.player_id))
                self.feedback = "The mentor is thinking… " + self.orchestrator.tutor.hint(self.question)
                self.mentor_future = self.llm_provider.explain_async(self.question, self.answer, fallback)
            else:
                self.feedback = "The mentor says: every step builds a stronger mind. Try ATTACK for a practice question."
        elif action == "FLEE":
            self.outcome, self.state, self.feedback = "fled", "over", "You retreat to the trail. Your learning progress is safe."

    def _start_question(self, topic=None, multiplier=1.0):
        if self.spec.name == "ARITHMETIC BEAST":
            topic = self.BOSS_TOPICS[self.boss_round % len(self.BOSS_TOPICS)]
        result = self.orchestrator.next_question(self.player.player_id, topic)
        self.question = result["question"]
        self.last_question = self.question
        self.answer = ""
        self.wrong_count = 0
        self.damage_multiplier = multiplier
        self.state = "question"
        self.feedback = f"{self.question.difficulty.title()} challenge — use H for a hint."

    def _submit(self):
        decision = self.orchestrator.submit_answer(self.player.player_id, self.question, self.answer)
        if not decision.correct:
            self.wrong_count += 1
            self.answer = ""
            if self.wrong_count >= 3:
                topic = self.question.topic
                profile = self.repository.get_learning_profile(self.player.player_id)
                coaching = self.orchestrator.tutor.mentor(self.question, profile)
                next_question = self.orchestrator.next_question(
                    self.player.player_id, topic, decision.next_difficulty
                )["question"]
                self.question = self.last_question = next_question
                self.wrong_count = 0
                self.mentor_future = None
                self.feedback = f"{coaching} A fresh {topic} challenge is ready."
            else:
                self.feedback = decision.feedback
            return
        self.level_message = self._grant_exp(decision.exp_reward)
        damage = max(4, round((self.question.base_damage + self.player.level + self.player_spec.attack // 2) * self.damage_multiplier))
        self.enemy_hp = max(0, self.enemy_hp - damage)
        if self.spec.name == "ARITHMETIC BEAST":
            self.boss_round += 1
        self.feedback = f"Correct! {self.player_spec.name} lands {damage} damage.{self.level_message}"
        self.repository.save_player(self.player)
        if self.enemy_hp <= 0:
            bonus = 20 if self.spec.name == "ARITHMETIC BEAST" else 8
            evolution = self._grant_exp(bonus + self.next_victory_bonus)
            self.player.hp = min(self.player.max_hp, self.player.hp + 4)
            self.repository.save_player(self.player)
            self.outcome, self.state = "won", "over"
            self.feedback = f"{self.spec.name} is defeated! +{bonus} EXP.{evolution} Your creature rests and recovers 4 HP."
            return
        self.answer = ""
        self.state = "menu"
        self._enemy_turn()

    def _grant_exp(self, amount):
        old_form = self.player_spec.name
        leveled = self.player.add_exp(amount)
        self.player_spec = creature_spec(self.player.creature, self.player.level)
        if self.player_spec.name != old_form:
            return f" EVOLUTION! {old_form} became {self.player_spec.name}!"
        return " LEVEL UP!" if leveled else ""

    def _enemy_turn(self):
        damage = self.rng.randint(max(1, self.spec.attack - 2), self.spec.attack)
        self.player.hp = max(0, self.player.hp - damage)
        self.repository.save_player(self.player)
        self.feedback += f" {self.spec.name} answers with {damage} damage."
        if self.player.hp == 0:
            self.player.hp = max(1, self.player.max_hp // 2)
            self.repository.save_player(self.player)
            self.outcome, self.state = "defeated", "over"
            self.feedback = "Your creature needs a rest. The ranger restores half its HP; your learning progress is saved."

    def _list_key(self, event):
        choices = self._skills() if self.state == "skills" else ("Health Potion", "EXP Booster", "Learning Crystal")
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
        if item == "Learning Crystal":
            if not self.repository.use_item(self.player.player_id, item):
                self.feedback = "No Learning Crystals left."
            elif self.last_question:
                self.feedback = self.orchestrator.tutor.explain(self.last_question)
                self.repository.add_recommendation(self.player.player_id, "Use a hint, then explain the steps in your own words.")
            else:
                self.feedback = "The crystal glows softly. Choose ATTACK to receive a practice hint."
            self.state = "menu"
            return
        if item == "Health Potion":
            if self.player.hp >= self.player.max_hp:
                self.feedback = "HP is already full. Save the potion for later."
                self.state = "menu"
                return
            if not self.repository.use_item(self.player.player_id, item):
                self.feedback = "No Health Potions left."
                self.state = "menu"
                return
            self.player.hp = min(self.player.max_hp, self.player.hp + 14)
            self.feedback = "A Health Potion restores 14 HP."
        else:
            if not self.repository.use_item(self.player.player_id, item):
                self.feedback = "No EXP Boosters left."
                self.state = "menu"
                return
            self.next_victory_bonus += 10
            self.feedback = "The EXP Booster will add +10 EXP after this battle."
        self.repository.save_player(self.player)
        self.state = "menu"
        self._enemy_turn()

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
        # Opponent and status.
        panel(surface, (8, 8, 143, 43), PALETTE["night"])
        text(surface, self.spec.name, (15, 12), 13, PALETTE["white"])
        text(surface, self.spec.element, (15, 25), 9, PALETTE["muted"])
        meter(surface, 15, 39, 124, 6, self.enemy_hp, self.enemy_max_hp, PALETTE["coral"])
        pixel_monster(surface, 226, 20 + (frame % 40 // 20), self.spec, 2, True)
        # Player creature and status card.
        pixel_monster(surface, 36, 73 + (frame % 40 // 20), self.player_spec, 2)
        panel(surface, (143, 71, 168, 46), PALETTE["night"])
        text(surface, f"{self.player_spec.name}  Lv {self.player.level}", (151, 75), 12, PALETTE["white"])
        meter(surface, 151, 93, 147, 7, self.player.hp, self.player.max_hp, PALETTE["mint"], "HP")
        meter(surface, 151, 108, 147, 5, self.player.exp, self.player.next_level_exp, PALETTE["sky"], "EXP")
        # Dialogue/question at lower left, action list at lower right.
        panel(surface, (7, 128, 193, 83), PALETTE["night"])
        if self.state == "question" and self.question:
            text(surface, f"{self.question.topic.upper()}  •  {self.question.difficulty.upper()}", (14, 134), 10, PALETTE["gold"])
            wrapped(surface, self.question.prompt, (14, 148, 174, 20), 17, PALETTE["white"], 17, 1)
            pygame.draw.rect(surface, PALETTE["ink"], (14, 172, 174, 21))
            text(surface, "> " + self.answer + ("_" if frame % 50 < 28 else " "), (19, 177), 15, PALETTE["cream"])
            wrapped(surface, self.feedback, (14, 196, 178, 12), 9, PALETTE["mint"], 10, 1)
        else:
            wrapped(surface, self.feedback, (15, 137, 177, 63), 12, PALETTE["white"], 13, 5)
            if self.state == "mentor" and self.mentor_future and not self.mentor_future.done():
                text(surface, "Mentor is thinking…", (15, 192), 9, PALETTE["gold"])
        if self.state == "menu":
            menu(surface, (207, 128, 106, 83), self.ACTIONS, self.selected, 10)
        elif self.state in ("skills", "items"):
            choices = [f"{x}" for x in self._skills()] if self.state == "skills" else [
                f"{name} x{count}" for name, count in self.repository.inventory(self.player.player_id).items()]
            labels = choices or ["No items"]
            menu(surface, (207, 128, 106, 83), labels, min(self.sub_selected, len(labels) - 1), 9)
        elif self.state == "question":
            panel(surface, (206, 128, 107, 83), PALETTE["night"])
            text(surface, "BATTLE TIP", (214, 137), 11, PALETTE["gold"])
            wrapped(surface, "Type your answer. H gives a hint. Your turn stays safe while you learn.",
                    (214, 154, 91, 48), 10, PALETTE["white"], 12, 4)
        else:
            panel(surface, (207, 128, 106, 83), PALETTE["night"])
            text(surface, "ENTER", (216, 143), 11, PALETTE["gold"])
            text(surface, "to continue", (216, 158), 10, PALETTE["white"])
        text(surface, "↑↓ SELECT  ENTER CHOOSE  ESC BACK", (57, 222), 9, PALETTE["cream"])

"""The advanced monster battle screen: draws a ``BattleEngine`` battle and turns input into engine calls.

All rules live in ``battle_engine``. This module only:
- shows the monster card (name, level, rarity, speciality, weakness, HP, shield, phase) and status badges,
- plays the sliced sprite animations plus placeholder effects for hits, shields, charges and defeat,
- presents each question with multiple-choice options (keys 1-5) or a typed answer (TAB),
- explains every result (why it hit, why it was blocked, the worked answer) and keeps a battle log (L).
"""
import random

import pygame

from battle_engine.engine import BattleEngine, PlayerCombatant
from battle_engine.monster_data import get
from battle_engine.progression import ProgressStore
from battle_engine.skills import SKILLS
from battle_engine.tiers import level_for_rank
from config import FPS, PALETTE
from game.animation import Effects, SpriteAnimator, draw_lock, draw_shield_bubble, warning_glow
from game.creatures import draw_creature
from game.ui import menu, meter, panel, text, wrapped
from mathematics.question_engine import topic_label

MONSTER_AT = (248, 102)
PLAYER_AT = (62, 146)
EVENT_FRAMES = 54          # how long each monster-turn event stays on screen (ENTER skips)
POTION_HEAL = 0.35
# The same menu as every other battle (report: boss fights felt different and you could not switch).
ACTIONS = ("FIGHT", "SKILLS", "MONSTER", "BAG", "RUN")
ALIASES = {"ATTACK": "FIGHT", "FLEE": "RUN", "POTION": "BAG"}      # older names still work
BAG_EFFECTS = ("heal", "revive", "boost_attack", "boost_defence")
TIP_FLAG = "tip:trial_battle"
TIP = ("TRIAL BATTLE! This monster has PHASES, SHIELDS and charged attacks. FIGHT: pick a maths topic - green "
       "topics hit its weakness. Answer interrupt questions to stop a charge. MONSTER: switch your fighter. "
       "BAG: items. L: battle log.")
COLORS = {"sky": PALETTE["sky"], "gold": PALETTE["gold"], "coral": PALETTE["coral"], "mint": PALETTE["mint"],
          "muted": PALETTE["muted"], "cream": PALETTE["cream"], "white": PALETTE["white"]}


class MonsterBattleScreen:
    def __init__(self, repository, player, monster_id, rank, rng=None, team=None):
        self.repository, self.player = repository, player
        self.rng = rng or random.Random()
        self.defn = get(monster_id)
        self.rank = rank
        from game.team import Team
        self.team = team or Team(repository, player)
        self.fighter = self.team.leader()
        if self.fighter.hp <= 0:
            healthy = self.team.healthy() or [self.fighter]
            self.fighter = healthy[0]
            self.fighter.hp = max(self.fighter.hp, self.fighter.max_hp // 2)
        self.fighter_spec = self.team.spec_of(self.fighter)
        self.store = ProgressStore(repository, player.player_id)
        trainer = self.store.trainer()
        level = level_for_rank(rank, max(self.fighter.level, trainer.level))
        combatant = PlayerCombatant.from_level(self.fighter_spec.name, self.fighter.level, self.fighter.hp,
                                               self.fighter.max_hp, trainer.level)
        self.engine = BattleEngine(self.defn, level, combatant, self.rng, trainer_level=trainer.level)
        self.animator = SpriteAnimator(self.defn.sprite)
        self.effects = Effects()
        self.popups = []
        self.state = "intro"
        self.selected = 0
        self.sub_selected = 0
        self.choice = 0
        self.typing = False
        self.typed = ""
        self.hint_shown = False
        self.question_frames = 0
        self.result = None
        self.queue = []
        self.current = None
        self.event_timer = 0
        self.message = ""
        self.show_log = False
        self.closed = False
        self.reward = None
        self.age = 0
        self.monster_flash = self.player_flash = 0
        self.monster_shake = self.player_shake = 0
        self.player_pose = ("idle", 0)
        self.monster_alpha = 255.0
        self.screen_flash = 0
        self.banner = None          # (text, color, frames)
        self.monster_hp_shown = float(self.engine.monster_hp)
        self.player_hp_shown = float(self.engine.player.hp)
        self.animator.play("walk", loop=True)
        self._enqueue(self.engine.begin())
        self.message = self.queue[0].text if self.queue else ""
        self.bag_items = []
        self.forced_switch = False       # your fighter fainted: choose who battles next
        self.tip = None
        flags = repository.world_flags(player.player_id) if getattr(player, "player_id", None) else set()
        if TIP_FLAG not in flags and getattr(player, "player_id", None):
            self.tip = TIP                # shown once, the first time you face a Trial monster
            repository.set_world_flag(player.player_id, TIP_FLAG)

    # ================================================================== helpers
    @property
    def tint(self):
        tint = self.engine.phase.current.get("tint")
        return tuple(tint) if tint else None

    def _popup(self, message, x, y, color, size=12, life=50):
        self.popups.append({"text": message, "x": x, "y": y, "color": color, "age": 0, "size": size, "life": life})

    def _enqueue(self, events):
        self.queue.extend(e for e in events if e.kind not in ("answer", "learn"))

    def _start_event(self, event):
        """Trigger the animation/effect for one engine event."""
        self.current = event
        self.event_timer = EVENT_FRAMES
        self.message = event.text
        mx, my = MONSTER_AT[0], MONSTER_AT[1] - 26
        px, py = PLAYER_AT[0], PLAYER_AT[1] - 22
        kind, data = event.kind, event.data
        color = tuple(self.defn.color)
        if kind == "player_hit":
            self.player_pose = ("attack", 26)
            self.effects.add("slash", mx, my, PALETTE["white"], 16)
            if data.get("amount"):
                self.monster_flash, self.monster_shake = 12, 12
                self._popup(f"-{data['amount']}", mx, my - 26, PALETTE["coral"] if data.get("critical") else PALETTE["gold"],
                            16 if data.get("critical") else 13)
            if data.get("critical"):
                self.effects.add("ring", mx, my, PALETTE["gold"], 24, start=4, grow=30)
                self._popup("CRITICAL!", 160, 70, PALETTE["gold"], 16)
            if data.get("shield"):
                self._popup(f"-{data['shield']} SHIELD", mx, my - 12, PALETTE["sky"], 10)
        elif kind == "shield_hit":
            self.effects.add("ring", mx, my, PALETTE["sky"], 20, start=24, grow=6)
        elif kind == "shield_break":
            self.effects.burst(mx, my, PALETTE["sky"], 16, 34, 2.2, self.rng)
            self.screen_flash = 8
            self.banner = ("SHIELD BROKEN!", PALETTE["sky"], 70)
        elif kind == "shield_up" or kind == "barrier":
            self.effects.add("ring", mx, my, PALETTE["sky"], 26, start=8, grow=22)
        elif kind == "lock_break":
            self.effects.burst(mx, my - 20, PALETTE["gold"], 10, 26, 1.4, self.rng)
        elif kind in ("charge", "stage"):
            self.animator.play("attack", hold_last=False)
            self.effects.add("ring", mx, my, PALETTE["coral"], 30, start=30, grow=-24)
            label = data.get("stage", 0) + 1
            stages = data.get("stages", 1)
            self.banner = ((f"WARNING! STAGE {label}/{stages}" if stages > 1 else "WARNING! CHARGING"),
                           PALETTE["coral"], 70)
        elif kind == "interrupt":
            self.monster_flash, self.monster_shake = 14, 16
            self._popup("INTERRUPTED!", mx, my - 34, PALETTE["gold"], 14, 60)
            self.effects.burst(mx, my, PALETTE["gold"], 12, 30, 1.8, self.rng)
        elif kind == "release":
            self.animator.play("attack")
        elif kind == "monster_hit":
            self.animator.play("attack")
            self.effects.add("beam", mx - 14, my + 6, color, 14, tx=px + 6, ty=py)
            self.player_flash, self.player_shake = 12, 12
            self.player_pose = ("hurt", 24)
            self._popup(f"-{data.get('amount', 0)}", px, py - 26, PALETTE["coral"], 14 if data.get("critical") else 12)
        elif kind == "special":
            self.animator.play("attack")
            self.effects.add("ring", mx, my, color, 30, start=6, grow=40)
        elif kind == "stunned":
            self._popup("STUNNED", mx, my - 36, PALETTE["cream"], 11)
        elif kind == "phase":
            self.banner = (f"PHASE: {data.get('name', '').upper()}", tuple(data.get("tint") or PALETTE["gold"]), 100)
            self.screen_flash = 10
            self.effects.burst(mx, my, tuple(data.get("tint") or color), 20, 40, 2.4, self.rng)
        elif kind == "rule":
            self.banner = ("NEW RULE!", PALETTE["coral"], 90)
        elif kind == "split":
            self.effects.burst(mx, my, PALETTE["mint"], 18, 36, 2.0, self.rng)
        elif kind == "minion_down":
            self.effects.burst(mx, my, PALETTE["mint"], 10, 24, 1.5, self.rng)
        elif kind == "merge":
            self.effects.add("ring", mx, my, PALETTE["mint"], 30, start=30, grow=-26)
        elif kind == "absorb":
            self.effects.add("ring", mx, my, (170, 110, 230), 24, start=26, grow=-20)
            self._popup("+VOID", mx, my - 30, (190, 140, 255), 11)
        elif kind in ("growth", "gravity"):
            self.effects.add("ring", mx, my, PALETTE["coral"] if kind == "growth" else (140, 110, 255), 20, start=10, grow=14)
        elif kind == "time_lock":
            self.effects.add("ring", mx, my, PALETTE["gold"], 40, start=4, grow=50)
            self.banner = ("TIME LOCK", PALETTE["gold"], 80)
        elif kind == "observe":
            self.animator.play("walk")
        elif kind == "victory":
            self.effects.burst(mx, my, color, 24, 50, 2.0, self.rng)
            self.banner = ("VICTORY!", PALETTE["gold"], 140)
        elif kind == "defeat":
            self.banner = ("TOO TIRED...", PALETTE["coral"], 140)

    # ================================================================== update
    def update(self):
        self.age += 1
        self.animator.update()
        self.effects.update()
        if self.state == "intro" and self.age > 50 and not self.tip:
            self.animator.play("idle", loop=True)
            self.state = "events"
        if self.state == "question":
            self.question_frames += 1
        if self.state == "events":
            if self.current is None and self.queue:
                self._start_event(self.queue.pop(0))
            elif self.current is not None:
                self.event_timer -= 1
                if self.event_timer <= 0:
                    self.current = None
                    if not self.queue:
                        self._after_events()
        for name in ("monster_flash", "player_flash", "monster_shake", "player_shake", "screen_flash"):
            value = getattr(self, name)
            if value:
                setattr(self, name, value - 1)
        pose, frames = self.player_pose
        if frames > 0:
            self.player_pose = (pose, frames - 1) if frames > 1 else ("idle", 0)
        if self.banner:
            message, color, frames = self.banner
            self.banner = (message, color, frames - 1) if frames > 1 else None
        if self.engine.outcome == "won":
            self.monster_alpha = max(0.0, self.monster_alpha - 4)
        for popup in self.popups:
            popup["age"] += 1
        self.popups = [p for p in self.popups if p["age"] < p["life"]]
        self.monster_hp_shown += (self.engine.monster_hp - self.monster_hp_shown) * 0.15
        self.player_hp_shown += (self.engine.player.hp - self.player_hp_shown) * 0.15

    def _after_events(self):
        if self.engine.outcome == "lost" and self.switch_options():
            # Your fighter fainted but the team can go on: choose who battles next.
            self.fighter.hp = 0
            self.team.save(self.fighter)
            self.engine.outcome = None
            self.forced_switch = True
            self.state, self.sub_selected = "party", 0
            self.message = f"{self.fighter_spec.name} fainted! Choose who battles next."
            return
        if self.engine.outcome:
            self._finish()
        elif self.state == "events":
            self.state, self.selected = "menu", 0

    def _finish(self):
        if self.reward is not None:
            return
        engine = self.engine
        self.reward = self.store.apply(engine, self.rank)
        self.fighter.hp = engine.player.hp if engine.outcome == "won" else max(1, self.fighter.max_hp // 2)
        exp_message = ""
        if self.reward.member_exp and self.fighter.add_exp(self.reward.member_exp):
            exp_message = f" {self.team.name_of(self.fighter)} reached Lv {self.fighter.level}!"
        self.team.save(self.fighter)
        self.exp_message = exp_message
        self.state = "over"

    # ================================================================== input
    def handle_key(self, key, unicode=""):
        if key == pygame.K_l and not (self.state == "question" and self.typing):
            self.show_log = not self.show_log
            return
        if self.show_log and key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            self.show_log = False
            return
        if self.state == "intro":
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.tip = None
                self.age = 60
        elif self.state == "events":
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.event_timer = 0
        elif self.state == "menu":
            self._menu_key(key)
        elif self.state == "topic":
            self._topic_key(key)
        elif self.state == "skills":
            self._skills_key(key)
        elif self.state == "party":
            self._party_key(key)
        elif self.state == "bag":
            self._bag_key(key)
        elif self.state == "question":
            self._question_key(key, unicode)
        elif self.state == "result":
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self._monster_turn()
        elif self.state == "over":
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self.closed = True

    def _menu_key(self, key):
        if key in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % len(ACTIONS)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % len(ACTIONS)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self.choose(ACTIONS[self.selected])

    def choose(self, action):
        engine = self.engine
        action = ALIASES.get(action, action)
        if action == "FIGHT":
            if engine.forced_question():
                self._ask(None)
            else:
                self.state, self.sub_selected = "topic", 0
        elif action == "SKILLS":
            self.state, self.sub_selected = "skills", 0
        elif action == "MONSTER":
            if not self.switch_options():
                self.message = "No one else can battle right now."
            else:
                self.state, self.sub_selected = "party", 0
        elif action == "BAG":
            self.bag_items = self.usable_items()
            if not self.bag_items:
                self.message = "Your bag has nothing to use in battle. Visit the Mathmart!"
            else:
                self.state, self.sub_selected = "bag", 0
        elif action == "LOG":
            self.show_log = True
        elif action == "RUN":
            engine.outcome = "fled"
            engine.log.append(("info", "You step back from the battle."))
            self.fighter.hp = engine.player.hp
            self.team.save(self.fighter)
            self.state, self.closed = "over", True

    # ------------------------------------------------------------------ MONSTER: switch your fighter
    def switch_options(self):
        """Party members who can take over (not fainted, not already battling)."""
        return [m for m in self.team.members if m is not self.fighter and m.hp > 0]

    def switch_to(self, member, free=False):
        """Send ``member`` in. The boss keeps its HP, phase and charge. Costs your turn unless ``free``."""
        engine = self.engine
        self.fighter.hp = engine.player.hp
        self.team.save(self.fighter)
        trainer_level = engine.trainer_level
        self.fighter = member
        self.fighter_spec = self.team.spec_of(member)
        engine.player = PlayerCombatant.from_level(self.fighter_spec.name, member.level, member.hp, member.max_hp,
                                                   trainer_level)
        self.player_hp_shown = float(member.hp)
        self.player_pose = ("idle", 0)
        engine.log.append(("info", f"Go, {self.fighter_spec.name}!"))
        self.message = f"Go, {self.fighter_spec.name}!"
        self._popup(self.fighter_spec.name, PLAYER_AT[0], PLAYER_AT[1] - 56, PALETTE["gold"])
        if free:
            self.state, self.selected = "menu", 0
        else:
            self._monster_turn()

    def _party_key(self, key):
        options = self.switch_options()
        if key == pygame.K_ESCAPE and not self.forced_switch:
            self.state = "menu"
            return
        if not options:
            return
        if key in (pygame.K_UP, pygame.K_w):
            self.sub_selected = (self.sub_selected - 1) % len(options)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.sub_selected = (self.sub_selected + 1) % len(options)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            free, self.forced_switch = self.forced_switch, False
            self.switch_to(options[self.sub_selected], free=free)

    # ------------------------------------------------------------------ BAG: battle items
    def usable_items(self):
        from monsters.monster_data import items as item_data
        bag = self.repository.inventory(self.player.player_id) if hasattr(self.repository, "inventory") else {}
        data = item_data()
        return [name for name, count in bag.items()
                if count > 0 and data.get(name, {}).get("effect") in BAG_EFFECTS
                and data[name].get("use") in ("battle", "both")]

    def use_item(self, name):
        """Use a bag item on your fighter (or revive a fainted team-mate). Costs your turn."""
        from monsters.monster_data import items as item_data
        info = item_data()[name]
        engine = self.engine
        effect = info["effect"]
        if effect == "heal" and engine.player.hp >= engine.player.max_hp:
            self.message = "HP is already full."
            return False
        fainted = [m for m in self.team.members if m is not self.fighter and m.hp <= 0]
        if effect == "revive" and not fainted:
            self.message = "No one in your team has fainted."
            return False
        if not self.repository.use_item(self.player.player_id, name):
            self.message = f"No {name} left."
            return False
        if effect == "heal":
            healed = engine.heal_player(round(engine.player.max_hp * float(info["amount"])))
            self._popup(f"+{healed}", PLAYER_AT[0], PLAYER_AT[1] - 48, PALETTE["mint"])
            text_ = (f"{name} restores {healed} HP and you brace yourself - {engine.name}'s next hit is halved!")
        elif effect == "revive":
            member = fainted[0]
            member.hp = max(1, round(member.max_hp * float(info["amount"])))
            self.team.save(member)
            text_ = f"{name}: {self.team.name_of(member)} is back on its feet!"
        elif effect == "boost_attack":
            engine.player.attack *= float(info["amount"])
            text_ = f"{name}: your attacks hit {round((float(info['amount']) - 1) * 100)}% harder!"
        else:
            engine.player.defence /= float(info["amount"])
            text_ = f"{name}: you take less damage!"
        engine.log.append(("item", text_))
        self.message = text_
        self._monster_turn()
        return True

    def _bag_key(self, key):
        if key == pygame.K_ESCAPE:
            self.state = "menu"
            return
        if not self.bag_items:
            return
        if key in (pygame.K_UP, pygame.K_w):
            self.sub_selected = (self.sub_selected - 1) % len(self.bag_items)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.sub_selected = (self.sub_selected + 1) % len(self.bag_items)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            if not self.use_item(self.bag_items[self.sub_selected]):
                self.state = "menu"

    def _topic_key(self, key):
        options = self.engine.topic_options()
        if key == pygame.K_ESCAPE:
            self.state = "menu"
        elif key in (pygame.K_UP, pygame.K_w):
            self.sub_selected = (self.sub_selected - 1) % len(options)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.sub_selected = (self.sub_selected + 1) % len(options)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._ask(options[self.sub_selected]["topic"])

    def _skills_key(self, key):
        if key == pygame.K_ESCAPE:
            self.state = "menu"
        elif key in (pygame.K_UP, pygame.K_w):
            self.sub_selected = (self.sub_selected - 1) % len(SKILLS)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.sub_selected = (self.sub_selected + 1) % len(SKILLS)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            skill = SKILLS[self.sub_selected]
            if skill.unlock_level > self.engine.trainer_level:
                self.message = self.lock_text(skill)
                return
            events = self.engine.use_skill(skill.id)
            self.message = events[-1].text if events else ""
            self.state = "menu"  # skills are free: you still choose your action

    def lock_text(self, skill):
        """How to unlock a skill: it needs a Trainer level (not your MathMon's level)."""
        trainer = self.store.trainer()
        return (f"LOCKED: {skill.name} needs TRAINER Lv {skill.unlock_level} (you are Lv {trainer.level}, "
                f"{trainer.xp}/{trainer.next_level_xp} XP). Win any battle or catch MathMon to earn Trainer XP.")

    def _ask(self, topic):
        self.engine.next_question(topic)
        self.choice = 0
        self.typed = ""
        self.typing = self.engine.typed_only()
        self.hint_shown = False
        self.question_frames = 0
        self.banner = None  # the question panel now carries the warning
        self.state = "question"

    def _question_key(self, key, unicode):
        engine = self.engine
        question = engine.question
        if key == pygame.K_ESCAPE:
            if not engine.forced_question() and engine.request.purpose == "attack":
                self.state = "menu"
            return
        if key == pygame.K_h:
            self.hint_shown = True
            return
        if key == pygame.K_TAB and question.typed_allowed and not engine.typed_only():
            self.typing = not self.typing
            return
        if key == pygame.K_f and not self.typing and engine.skill_ready("focus"):
            engine.use_skill("focus")
            self.choice = 0
            return
        if self.typing:
            if key == pygame.K_BACKSPACE:
                self.typed = self.typed[:-1]
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.typed.strip():
                self.submit(self.typed, typed=True)
            elif unicode and unicode in "0123456789-/.," and len(self.typed) < 14:
                self.typed += unicode
            return
        choices = engine.choices
        if key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w):
            self.choice = (self.choice - (2 if key in (pygame.K_UP, pygame.K_w) else 1)) % len(choices)
        elif key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN, pygame.K_s):
            self.choice = (self.choice + (2 if key in (pygame.K_DOWN, pygame.K_s) else 1)) % len(choices)
        elif unicode and unicode.isdigit() and 1 <= int(unicode) <= len(choices):
            self.choice = int(unicode) - 1
            self.submit(choices[self.choice])
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            self.submit(choices[self.choice])

    def submit(self, answer, typed=False):
        result = self.engine.answer(answer, typed=typed, elapsed=self.question_frames / FPS)
        self.result = result
        if hasattr(self.repository, "record_attempt"):
            try:
                self.repository.record_attempt(self.player.player_id, result.question, answer, result.correct)
            except Exception:
                pass  # learning analytics must never break a battle
        for event in result.events:
            if event.kind in ("player_hit", "shield_hit", "shield_break", "interrupt", "phase", "victory", "split",
                              "minion_down", "merge", "lock_break", "rule"):
                self._start_event(event)
        self.state = "result"
        if not result.correct:
            self.player_shake = 8

    def _monster_turn(self):
        if self.engine.outcome:
            self.queue = []
            self._finish()
            return
        self.result = None
        self._enqueue(self.engine.monster_turn())
        self.current = None
        self.state = "events"
        if not self.queue:
            self._after_events()

    # ================================================================== draw
    def draw(self, surface, frame=0):
        self._draw_arena(surface, frame)
        self._draw_monster(surface, frame)
        self._draw_player(surface, frame)
        self.effects.draw(surface)
        self._draw_cards(surface, frame)
        for popup in self.popups:
            rise = popup["age"] // 2
            if popup["age"] < popup["life"] - 10 or popup["age"] % 4 < 2:
                text(surface, popup["text"], (popup["x"], popup["y"] - rise), popup["size"], popup["color"],
                     center=True, shadow=PALETTE["ink"])
        if self.banner:
            message, color, frames = self.banner
            pygame.draw.rect(surface, PALETTE["ink"], (0, 128, 320, 16))
            pygame.draw.rect(surface, color, (0, 128, 320, 1))
            pygame.draw.rect(surface, color, (0, 143, 320, 1))
            text(surface, message, (160, 136), 13, color, center=True)
        self._draw_bottom(surface, frame)
        if self.tip and self.state == "intro":
            self._draw_tip(surface)
        if self.screen_flash:
            flash = pygame.Surface(surface.get_size())
            flash.fill(PALETTE["white"])
            flash.set_alpha(16 * self.screen_flash)
            surface.blit(flash, (0, 0))
        if self.show_log:
            self._draw_log(surface)

    def _draw_arena(self, surface, frame):
        tint = self.tint
        top = tint and tuple(max(0, min(255, c // 5 + 12)) for c in tint) or (24, 30, 52)
        surface.fill(top)
        for i in range(24):  # distant stars / dust
            x = (i * 53 + frame // 6) % 330 - 5
            y = 8 + (i * 37) % 90
            surface.set_at((x % 320, y), (90, 96, 130) if i % 3 else (150, 150, 190))
        pygame.draw.rect(surface, (36, 44, 70), (0, 92, 320, 58))
        pygame.draw.ellipse(surface, (54, 64, 96), (190, 92, 118, 18))
        pygame.draw.ellipse(surface, (54, 64, 96), (12, 132, 104, 22))

    def _draw_monster(self, surface, frame):
        engine = self.engine
        split = engine.mechanic("split")
        mx, my = MONSTER_AT
        slide = max(0, 50 - self.age) * 3
        shake = ((self.monster_shake % 4) - 1.5) * 2 if self.monster_shake else 0
        anchor = (mx + slide + shake, my)
        if engine.pending is not None or self._combo_armed():
            warning_glow(surface, (int(anchor[0]), my - 26), 30, PALETTE["coral"], frame)
        shield = engine.mechanic("shield")
        if split and split.hidden:
            self._draw_spores(surface, split, frame)
        elif self.monster_alpha > 0:
            height = 58 if not engine.defn.boss else 66
            tint = PALETTE["white"] if self.monster_flash % 4 >= 2 else None
            if engine.stunned and not tint and frame % 30 < 6:
                tint = (200, 200, 220)
            if (engine.pending is not None or self._combo_armed()) and self.animator.animation == "idle":
                # Charging: hold the sheet's first attack frame as the wind-up pose.
                self.animator.draw_frame(surface, self.animator.frames("attack")[0], anchor, height, True, tint)
            else:
                self.animator.draw(surface, anchor, height, flip=True, tint=tint, alpha=self.monster_alpha)
            if engine.stunned:
                for i in range(3):
                    sx = int(anchor[0]) - 10 + i * 10 + (frame // 6 + i) % 3
                    pygame.draw.rect(surface, PALETTE["gold"], (sx, my - height - 4 - (i % 2) * 2, 2, 2))
        if shield and shield.up and not (split and split.hidden):
            draw_shield_bubble(surface, (int(anchor[0]), my - 28), 34, PALETTE["sky"], shield.hp / shield.max_hp, frame)
        barrier = engine.mechanic("barrier")
        if barrier and barrier.up:
            draw_shield_bubble(surface, (int(anchor[0]), my - 28), 36, (230, 220, 160), 0.6, frame)
            for i in range(barrier.max_locks):
                draw_lock(surface, int(anchor[0]) - barrier.max_locks * 6 + i * 12, my - 74,
                          PALETTE["gold"] if i < barrier.locks else PALETTE["muted"], opened=i >= barrier.locks)

    def _combo_armed(self):
        combo = self.engine.mechanic("operation_combo")
        return bool(combo and combo.combo)

    def _draw_spores(self, surface, split, frame):
        """Placeholder for the split: the real idle frame, scaled down, once per spore."""
        spores = split.minions
        for index, spore in enumerate(spores):
            x = 206 + index * (98 // max(1, len(spores) - 1) if len(spores) > 1 else 0)
            y = 102 - (index % 2) * 14
            if spore["alive"]:
                bob = 1 if (frame // 12 + index) % 2 else 0
                self.animator.draw(surface, (x, y - bob), 24, flip=True)
                label = spore["label"][-1] + " " + _fraction_text(spore["value"])
                text(surface, label, (x, y + 6), 8, PALETTE["mint"], center=True, shadow=PALETTE["ink"])

    def _draw_player(self, surface, frame):
        slide = max(0, 50 - self.age) * 3
        shake = ((self.player_shake % 4) - 1.5) * 2 if self.player_shake else 0
        pose = self.player_pose[0]
        if pose == "idle":
            pose = ("idle", "idle2", "idle3", "idle2")[(frame // 18) % 4]
        alpha_out = self.engine.outcome == "lost"
        draw_creature(surface, self.fighter_spec, (PLAYER_AT[0] - slide + shake, PLAYER_AT[1]), 46, pose,
                      tint=PALETTE["coral"] if self.player_flash % 4 >= 2 else ((90, 90, 110) if alpha_out else None))

    def _draw_cards(self, surface, frame):
        engine = self.engine
        tier = engine.tier
        # Monster card.
        panel(surface, (6, 4, 158, 50), PALETTE["night"], tier.color)
        text(surface, f"{engine.name.upper()}  Lv {engine.level}", (12, 8), 11, PALETTE["white"])
        pygame.draw.rect(surface, tier.color, (122, 8, 38, 9))
        text(surface, tier.name.upper(), (141, 12), 7, PALETTE["ink"], center=True)
        text(surface, f"{topic_label(engine.defn.math_speciality).upper()} SPECIALIST", (12, 19), 7, PALETTE["muted"])
        meter(surface, 12, 28, 112, 6, self.monster_hp_shown, engine.monster_max_hp, PALETTE["coral"])
        text(surface, f"{engine.monster_hp}/{engine.monster_max_hp}", (160, 27), 8, PALETTE["cream"], align="right")
        shield = engine.mechanic("shield")
        if shield and shield.active and shield.up:
            meter(surface, 12, 35, 112, 4, shield.hp, shield.max_hp, PALETTE["sky"])
            text(surface, "SHIELD", (160, 34), 7, PALETTE["sky"], align="right")
        weak = ", ".join(topic_label(t) for t in sorted(engine.weakness_topics()))
        text(surface, f"WEAK: {weak}", (12, 42), 7, PALETTE["mint"])
        if engine.phase.named:
            phase = engine.phase.current
            text(surface, f"PHASE {engine.phase.index + 1}/{len(engine.phase.phases)}: {phase.get('name', '').upper()}",
                 (160, 42), 7, tuple(phase.get("tint") or PALETTE["gold"]), align="right")
        # Status badges (mechanics) under the monster card, clear of both creatures.
        y = 58
        for badge in engine.badges()[:3]:
            color = COLORS.get(badge.color, PALETTE["cream"])
            pygame.draw.rect(surface, PALETTE["ink"], (6, y, 158, 10))
            pygame.draw.rect(surface, color, (6, y, 2, 10))
            text(surface, badge.label, (11, y + 1), 7, color)
            text(surface, badge.value, (162, y + 1), 7, PALETTE["white"], align="right")
            y += 11
        if engine.pending is not None:
            pending = engine.pending
            stages = f" {pending.stage + 1}/{len(pending.stages)}" if pending.stages else ""
            pygame.draw.rect(surface, PALETTE["coral"] if frame % 30 < 20 else PALETTE["ink"], (6, y, 158, 11))
            text(surface, f"! {pending.stage_name.upper()}{stages} - INTERRUPT IT!", (85, y + 1), 7, PALETTE["white"],
                 center=True)
        # Player card.
        panel(surface, (150, 112, 164, 32), PALETTE["night"])
        text(surface, f"{self.fighter_spec.name}  Lv {self.fighter.level}", (156, 116), 10, PALETTE["white"])
        text(surface, f"TRAINER Lv {engine.trainer_level}", (310, 117), 7, PALETTE["gold"], align="right")
        meter(surface, 156, 128, 112, 6, self.player_hp_shown, engine.player.max_hp, PALETTE["mint"], warn=True)
        text(surface, f"{engine.player.hp}/{engine.player.max_hp}", (310, 127), 8, PALETTE["cream"], align="right")
        if engine.combo >= 2:
            text(surface, f"{engine.combo} IN A ROW", (156, 136), 7, PALETTE["gold"])
        buffs = " ".join(sorted(b.replace("_", " ").upper() for b in engine.buffs))
        if buffs:
            text(surface, buffs, (310, 136), 7, PALETTE["sky"], align="right")

    # ------------------------------------------------------------------ bottom panel
    def _draw_bottom(self, surface, frame):
        if self.state == "question":
            self._draw_question(surface, frame)
        elif self.state == "result" and self.result:
            self._draw_result(surface)
        elif self.state == "over":
            self._draw_over(surface)
        else:
            panel(surface, (6, 150, 202, 74), PALETTE["night"])
            message = self.message or (self.engine.log[-1][1] if self.engine.log else "")
            wrapped(surface, message, (12, 155, 190, 64), 9, PALETTE["white"], 10, 6)
            if self.state == "menu":
                menu(surface, (214, 150, 100, 74), list(ACTIONS), self.selected, 9, frame, (), 13)
            elif self.state == "topic":
                options = self.engine.topic_options()
                labels = [o["label"][:16] for o in options]
                weak = tuple(i for i, o in enumerate(options) if o["effect"] == "weak")
                resist = tuple(i for i, o in enumerate(options) if o["effect"] == "resist")
                menu(surface, (214, 150, 100, 74), labels, self.sub_selected, 8, frame, resist, 12, weak)
                option = options[self.sub_selected]
                note = {"weak": "WEAKNESS x1.5!", "resist": "RESISTED x0.6", "normal": "normal damage"}[option["effect"]]
                text(surface, note, (264, 216), 7, PALETTE["mint"] if option["effect"] == "weak" else
                     PALETTE["coral"] if option["effect"] == "resist" else PALETTE["muted"], center=True)
            elif self.state == "party":
                options = self.switch_options()
                labels = [f"{self.team.name_of(m)[:9]} {m.hp}/{m.max_hp}" for m in options]
                menu(surface, (214, 150, 100, 74), labels or ["(nobody)"], self.sub_selected, 8, frame, (), 13)
            elif self.state == "bag":
                bag = self.repository.inventory(self.player.player_id)
                labels = [f"{name[:12]} x{bag.get(name, 0)}" for name in self.bag_items]
                rows = 5                                     # what fits in the box; a full bag scrolls
                top = max(0, min(self.sub_selected - rows + 1, len(labels) - rows)) if len(labels) > rows else 0
                top = min(top, self.sub_selected)
                menu(surface, (214, 150, 100, 74), labels[top:top + rows], self.sub_selected - top, 8, frame, (), 13)
                if top > 0:
                    pygame.draw.polygon(surface, PALETTE["gold"], [(306, 156), (309, 152), (312, 156)])
                if top + rows < len(labels):
                    pygame.draw.polygon(surface, PALETTE["gold"], [(306, 216), (309, 220), (312, 216)])
            elif self.state == "skills":
                labels, locked = [], []
                for index, skill in enumerate(SKILLS):
                    cooldown = self.engine.skill_cooldowns.get(skill.id, 0)
                    if skill.unlock_level > self.engine.trainer_level:
                        labels.append(f"{skill.name} (T{skill.unlock_level})")
                        locked.append(index)
                    else:
                        labels.append(f"{skill.name[:12]}" + (f" ({cooldown})" if cooldown else ""))
                        if cooldown:
                            locked.append(index)
                menu(surface, (214, 150, 100, 74), labels, self.sub_selected, 8, frame, tuple(locked), 13)
                skill = SKILLS[self.sub_selected]
                if skill.unlock_level > self.engine.trainer_level:
                    wrapped(surface, self.lock_text(skill), (12, 186, 190, 34), 7, PALETTE["coral"], 8, 4)
                else:
                    wrapped(surface, skill.description, (12, 200, 190, 20), 8, PALETTE["sky"], 9, 2)
        hints = {"menu": "UP/DOWN  ENTER   L: BATTLE LOG",
                 "party": ("CHOOSE WHO BATTLES NEXT" if self.forced_switch else "SWITCH COSTS YOUR TURN   ESC BACK"),
                 "bag": "USING AN ITEM COSTS YOUR TURN   ESC BACK",
                 "topic": "CHOOSE A MATHS ATTACK   GREEN = WEAKNESS   ESC BACK",
                 "skills": "SKILLS ARE FREE   T4 = NEEDS TRAINER Lv 4   ESC BACK",
                 "question": ("TYPE + ENTER   TAB: OPTIONS   H: HINT" if self.typing else
                              "1-5 OR ARROWS + ENTER   TAB: TYPE IT (x1.15)   H: HINT   F: FOCUS"),
                 "result": "ENTER: CONTINUE", "events": "ENTER: NEXT", "over": "ENTER: LEAVE"}.get(self.state, "")
        text(surface, hints, (160, 232), 7, PALETTE["cream"], center=True)

    def _draw_tip(self, surface):
        panel(surface, (20, 60, 280, 84), PALETTE["night"], PALETTE["gold"])
        text(surface, "HOW TRIAL BATTLES WORK", (160, 66), 10, PALETTE["gold"], center=True)
        wrapped(surface, self.tip, (28, 80, 264, 58), 8, PALETTE["white"], 9, 6)
        text(surface, "ENTER: GOT IT", (160, 136), 8, PALETTE["mint"], center=True)

    def _draw_question(self, surface, frame):
        engine = self.engine
        question, request = engine.question, engine.request
        colors = {"interrupt": PALETTE["coral"], "barrier": (230, 220, 160), "split_target": PALETTE["mint"],
                  "predict": PALETTE["coral"], "time": PALETTE["gold"], "attack": PALETTE["gold"]}
        color = colors.get(request.purpose, PALETTE["gold"])
        panel(surface, (6, 150, 308, 74), PALETTE["night"], color)
        label = request.label or "ATTACK"
        tag = "  WEAKNESS x1.5" if question.weakness else ""
        text(surface, f"{label}  •  {topic_label(question.topic).upper()}  •  {question.level_name.upper()}{tag}",
             (12, 154), 7, color)
        lines = 1 if len(question.prompt) < 46 else 2
        wrapped(surface, question.prompt, (12, 164, 296, 22), 11 if lines == 1 else 9, PALETTE["white"],
                11 if lines == 1 else 10, 2)
        if request.time_limit:
            seconds = self.question_frames / FPS
            left = max(0.0, request.time_limit - seconds)
            pygame.draw.rect(surface, PALETTE["ink"], (232, 154, 76, 5))
            pygame.draw.rect(surface, PALETTE["gold"], (232, 154, max(1, round(76 * left / request.time_limit)), 5))
            if not left:
                text(surface, "window closed - no penalty", (308, 160), 6, PALETTE["muted"], align="right")
        if self.typing:
            pygame.draw.rect(surface, color, (12, 186, 140, 17))
            pygame.draw.rect(surface, PALETTE["ink"], (13, 187, 138, 15))
            caret = "_" if frame % 50 < 28 else " "
            text(surface, "> " + self.typed + caret, (17, 190), 11, PALETTE["cream"])
            note = "TYPE-ONLY RULE!" if engine.typed_only() else "typed answers deal x1.15"
            text(surface, note, (160, 191), 8, PALETTE["coral"] if engine.typed_only() else PALETTE["muted"])
        else:
            choices = engine.choices
            for index, choice in enumerate(choices):
                col, row = index % 2, index // 2
                x, y = 12 + col * 150, 186 + row * 11
                chosen = index == self.choice
                if chosen:
                    pygame.draw.rect(surface, PALETTE["deep"], (x - 2, y - 1, 146, 11))
                text(surface, f"{index + 1}) {choice}", (x, y), 9, PALETTE["gold"] if chosen else PALETTE["white"])
        if self.hint_shown and question.hint:
            wrapped(surface, "HINT: " + question.hint, (12, 213, 296, 9), 7, PALETTE["sky"], 8, 1)

    def _draw_result(self, surface):
        result = self.result
        color = PALETTE["mint"] if result.correct else PALETTE["coral"]
        panel(surface, (6, 150, 308, 74), PALETTE["night"], color)
        text(surface, "CORRECT!" if result.correct else "NOT QUITE", (12, 154), 10, color)
        text(surface, f"{result.question.prompt[:44]}  =  {result.question.answer}", (308, 155), 7, PALETTE["cream"],
             align="right")
        why = result.summary.replace("Correct! ", "") if result.correct else result.summary
        mechanic_lines = [e.text for e in result.events if e.kind in ("interrupt", "interrupt_fail", "shield_break",
                                                                     "absorb", "growth_reset", "lock_break", "decoy",
                                                                     "minion_down", "phase", "gravity", "split")]
        body = " ".join([why] + mechanic_lines)
        used = wrapped(surface, body, (12, 166, 296, 30), 8, PALETTE["white"], 9, 3)
        wrapped(surface, "WHY: " + result.question.explanation, (12, 168 + used * 9, 296, 30), 8, PALETTE["sky"], 9,
                max(1, 6 - used))

    def _draw_over(self, surface):
        reward = self.reward
        engine = self.engine
        won = engine.outcome == "won"
        panel(surface, (6, 150, 308, 74), PALETTE["night"], PALETTE["gold"] if won else PALETTE["coral"])
        if reward is None:
            text(surface, "You left the battle.", (12, 156), 10, PALETTE["white"])
            return
        title = f"{engine.name} DEFEATED!" if won else "DEFEATED - but you learned a lot"
        text(surface, title, (12, 154), 10, PALETTE["gold"] if won else PALETTE["coral"])
        correct = sum(1 for _, ok in engine.answers if ok)
        text(surface, f"+{reward.trainer_xp} TRAINER XP   +{reward.member_exp} EXP   {correct}/{len(engine.answers)} correct",
             (12, 166), 8, PALETTE["cream"])
        lines = list(reward.lines)
        if reward.items:
            lines.append("Items: " + ", ".join(f"{name} x{count}" for name, count in reward.items.items()))
        if getattr(self, "exp_message", ""):
            lines.append(self.exp_message.strip())
        if not won:
            lines.append("Your MATHMON rests and recovers half its HP. Read the battle log (L) for tips.")
        wrapped(surface, " ".join(lines) or "Train more to raise its mastery rank!", (12, 177, 296, 40), 8,
                PALETTE["white"], 9, 5)

    def _draw_log(self, surface):
        panel(surface, (10, 10, 300, 210), PALETTE["ink"], PALETTE["cream"])
        text(surface, "BATTLE LOG", (18, 14), 10, PALETTE["gold"])
        y = 28
        colors = {"player_hit": PALETTE["mint"], "monster_hit": PALETTE["coral"], "learn": PALETTE["sky"],
                  "phase": PALETTE["gold"], "charge": PALETTE["coral"], "interrupt": PALETTE["gold"]}
        for kind, message in self.engine.log[-30:][::-1]:
            used = wrapped(surface, message, (18, y, 284, 30), 7, colors.get(kind, PALETTE["white"]), 8, 2)
            y += used * 8 + 2
            if y > 206:
                break
        text(surface, "L / ESC: CLOSE (newest first)", (160, 214), 7, PALETTE["muted"], center=True)


def _fraction_text(value):
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"

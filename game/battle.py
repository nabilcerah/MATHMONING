"""The BATTLE screen (GDD 7, 8, 24.2, 26). It draws and animates; every rule lives in
combat.battle_manager.BattleManager, and every question comes from the AI Orchestrator.

Animation sequence for an attack (GDD 24.2): wind-up pose while the question is shown, then the
attack pose, the hit/damage reaction and the HP bar easing down, then back to idle.
"""
import random

import pygame

from combat.battle_manager import BattleError, BattleManager
from config import PALETTE
from game import audio, ui
from game.creatures import draw_creature
from game.question_panel import QuestionPanel
from game.ui import menu, meter, panel, text, wrapped
from mathematics import curriculum
from monsters import elemental_system
from monsters.monster_data import items as item_data

ACTIONS = ("FIGHT", "MONSTER", "BAG", "RUN")
BATTLE_ITEMS = ("Health Potion", "Greater Potion", "Focus Crystal", "Revival Crystal", "Math Capsule")
EVENT_FRAMES = 70       # how long each battle message stays (ENTER skips)
MENU_RECT = (207, 150, 106, 62)
LIST_RECT = (7, 128, 306, 84)


class RepositoryBag:
    """The battle's view of the bag: a working copy written back when the battle ends."""

    def __init__(self, counts):
        self.counts = dict(counts)
        self.used = {}

    def count(self, item):
        return int(self.counts.get(item, 0))

    def take(self, item):
        if self.count(item) <= 0:
            return False
        self.counts[item] -= 1
        self.used[item] = self.used.get(item, 0) + 1
        return True


class BattleScreen:
    def __init__(self, orchestrator, player_id, party, enemy, kind="wild", bag=None, rng=None, llm=None,
                 trainer_name="", min_difficulty=None, mastery=None, scene="number_forest"):
        self.orchestrator, self.player_id, self.llm = orchestrator, player_id, llm
        self.scene = scene
        self.rng = rng or random.Random()
        self.bag = bag if bag is not None else RepositoryBag({})
        mastery = mastery or (lambda topic: orchestrator.repository.mastery(player_id, topic))
        self.battle = BattleManager(party, enemy, kind, mastery, self.bag, self.rng)
        self.party, self.enemy = party, enemy
        self.trainer_name = trainer_name
        self.min_difficulty = min_difficulty
        self.state = "events"          # events | menu | moves | party | bag | target | question | over
        self.selected = 0
        self.sub_selected = 0
        self.panel = None              # QuestionPanel while a question is open
        self.panel_kind = None         # "move" or "capture"
        self.pending_item = None
        self.answers = []
        self.closed = False
        self.events, self.current, self.event_timer = [], None, 0
        self.message = ""
        self.age = 0
        self.shown = {"enemy": float(enemy.hp), "player": float(self.battle.active.hp)}
        self.target = {"enemy": enemy.hp, "player": self.battle.active.hp}
        self.poses = {"player": ("idle", 0), "enemy": ("idle", 0)}
        self.flash = {"player": 0, "enemy": 0}
        self.shake = {"player": 0, "enemy": 0}
        self.popups = []
        self.capsule = 0               # capture animation frames
        self.capsule_success = None
        self.enemy_gone = False
        if kind == "boss" or enemy.spec.boss:
            intro = f"{enemy.spec.display_name} rises from the shadows!"
        elif trainer_name:
            intro = f"{trainer_name} sends out {enemy.name} (Lv {enemy.level})!"
        else:
            intro = f"A wild {enemy.name} (Lv {enemy.level}) appeared!"
        self._queue([{"kind": "intro", "text": intro},
                     {"kind": "info", "text": f"Go, {self.battle.active.name}! What will you do?"}])

    # ================================================================== properties
    @property
    def outcome(self):
        return self.battle.outcome

    @property
    def active(self):
        return self.battle.active

    def moves(self):
        return self.active.moves()

    def battle_items(self):
        return [item for item in BATTLE_ITEMS if self.bag.count(item) > 0]

    # ================================================================== event queue
    def _queue(self, events):
        self.events.extend(events)
        if self.current is None:
            self._next_event()

    def _next_event(self):
        if not self.events:
            self.current = None
            self._after_events()
            return
        self.current = self.events.pop(0)
        self.event_timer = EVENT_FRAMES
        self.message = self.current["text"]
        self.state = "events"
        self._animate(self.current)

    def _animate(self, event):
        kind = event["kind"]
        audio.play({"attack": "hit", "support": "heal", "item": "heal", "capture": "capture",
                    "capture_fail": "wrong", "levelup": "levelup", "victory": "correct",
                    "switch": "select"}.get(kind, ""))
        if kind == "attack":
            attacker = event["side"]
            defender = "enemy" if attacker == "player" else "player"
            self.poses[attacker] = ("attack", 30)
            self.poses[defender] = ("hurt", 26)
            self.flash[defender], self.shake[defender] = 14, 12
            self.target[defender] = self.enemy.hp if defender == "enemy" else self.active.hp
            colour = {"super": PALETTE["coral"], "weak": PALETTE["muted"]}.get(event.get("effectiveness"), PALETTE["gold"])
            x, y = (250, 30) if defender == "enemy" else (70, 70)
            self._popup(f"-{event['damage']}", x, y, colour)
        elif kind == "support":
            self.poses[event["side"]] = ("special", 30)
        elif kind in ("item", "switch"):
            self.target["player"] = self.active.hp
            self.shown["player"] = float(self.active.hp) if kind == "switch" else self.shown["player"]
            if kind == "switch":
                self.poses["player"] = ("happy", 20)
        elif kind == "faint":
            if event.get("side") == "enemy":
                self.enemy_gone = True
            else:
                self.poses["player"] = ("hurt", -1)
        elif kind == "capture_roll":
            self.capsule, self.capsule_success = 60, event["success"]
            self.enemy_gone = True
            self.event_timer = 80
        elif kind == "capture_fail":
            self.enemy_gone = False
            self.poses["enemy"] = ("happy", 30)
        elif kind == "capture":
            self._popup("CAPTURED!", 160, 50, PALETTE["mint"], 20)
        elif kind == "levelup":
            self._popup("LEVEL UP!", 160, 58, PALETTE["gold"], 18)
            self.target["player"] = self.active.hp
        elif kind == "victory":
            self.poses["player"] = ("happy", -1)
        elif kind == "escape":
            self.poses["player"] = ("walk1", -1)

    def _after_events(self):
        if self.battle.awaiting == "over":
            self.state = "over"
            self.message = {"won": "Victory!", "captured": "Captured!", "fled": "You escaped.",
                            "defeated": "Your team rests."}.get(self.outcome, "")
            self._report_battle()
        elif self.battle.awaiting == "enemy":
            self.poses["enemy"] = ("windup", 20)
            self._queue(self.battle.enemy_turn())
        elif self.battle.awaiting == "switch":
            self.state, self.sub_selected = "party", 0
        else:
            self.state = "menu"
            self.message = f"What will {self.active.name} do?"

    def _report_battle(self):
        try:
            self.orchestrator.handle({"type": "battle_end", "player_id": self.player_id, "enemy": self.enemy.name,
                                      "outcome": self.outcome, "answers": self.answers})
        except Exception:
            pass   # an AI log failure must never stop the game

    def _popup(self, message, x, y, color, size=14, life=50):
        self.popups.append({"text": message, "x": x, "y": y, "color": color, "age": 0, "size": size, "life": life})

    # ================================================================== update
    def update(self):
        self.age += 1
        if self.panel:
            self.panel.update()
        if self.state == "events" and self.current is not None:
            self.event_timer -= 1
            if self.event_timer <= 0:
                self._next_event()
        for side in ("enemy", "player"):
            target = self.target[side]
            shown = self.shown[side]
            self.shown[side] = float(target) if abs(shown - target) < 0.2 else shown + (target - shown) * 0.12
            pose, frames = self.poses[side]
            if frames > 0:
                self.poses[side] = (pose, frames - 1) if frames > 1 else ("idle", 0)
            for store in (self.flash, self.shake):
                if store[side]:
                    store[side] -= 1
        if self.capsule:
            self.capsule -= 1
        for popup in self.popups:
            popup["age"] += 1
        self.popups = [p for p in self.popups if p["age"] < p["life"]]

    # ================================================================== input
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(ui.to_virtual(event.pos))
            return
        if event.type != pygame.KEYDOWN:
            return
        self.handle_key(event.key, getattr(event, "unicode", ""))

    def handle_key(self, key, unicode=""):
        confirm = key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_e)
        if self.state == "events":
            if confirm:
                self._next_event()
        elif self.state == "over":
            if confirm or key == pygame.K_ESCAPE:
                self.closed = True
        elif self.state == "question":
            self._question_key(key, unicode, confirm)
        elif self.state == "menu":
            self._menu_key(key, confirm)
        elif self.state in ("moves", "party", "bag", "target"):
            self._list_key(key, confirm)

    def _menu_key(self, key, confirm):
        if key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT, pygame.K_a):
            self.selected = (self.selected - 1) % len(ACTIONS)
        elif key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT, pygame.K_d):
            self.selected = (self.selected + 1) % len(ACTIONS)
        elif pygame.K_1 <= key <= pygame.K_4:
            self.selected = key - pygame.K_1
            self.choose_action(ACTIONS[self.selected])
        elif confirm:
            self.choose_action(ACTIONS[self.selected])

    def choose_action(self, action):
        if action == "FIGHT":
            self.state, self.sub_selected = "moves", 0
        elif action == "MONSTER":
            self.state, self.sub_selected = "party", 0
        elif action == "BAG":
            if not self.battle_items():
                self.message = "Your bag has nothing to use in battle. Visit the shop!"
                return
            self.state, self.sub_selected = "bag", 0
        elif action == "RUN":
            try:
                self._queue(self.battle.run())
            except BattleError as error:
                self.message = str(error)

    def _list_choices(self):
        if self.state == "moves":
            return self.moves()
        if self.state in ("party", "target"):
            return self.party.party
        return self.battle_items()

    def _list_key(self, key, confirm):
        choices = self._list_choices()
        if key == pygame.K_ESCAPE:
            if self.state == "party" and self.battle.awaiting == "switch":
                return   # a fainted monster must be replaced
            self.state = "bag" if self.state == "target" else "menu"
            return
        if not choices:
            return
        if key in (pygame.K_UP, pygame.K_w):
            self.sub_selected = (self.sub_selected - 1) % len(choices)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.sub_selected = (self.sub_selected + 1) % len(choices)
        elif pygame.K_1 <= key <= pygame.K_9 and key - pygame.K_1 < len(choices):
            self.sub_selected = key - pygame.K_1
            self._pick(choices[self.sub_selected])
        elif confirm:
            self._pick(choices[self.sub_selected])

    def _pick(self, choice):
        if self.state == "moves":
            self.choose_move(choice.move_id)
        elif self.state == "party":
            self.switch_to(self.party.party.index(choice))
        elif self.state == "bag":
            self.choose_item(choice)
        elif self.state == "target":
            self.use_item(self.pending_item, self.party.party.index(choice))

    def _click(self, pos):
        if self.state in ("events", "over"):
            self.handle_key(pygame.K_RETURN)
        elif self.state == "menu":
            index = ui.menu_index(MENU_RECT, len(ACTIONS), pos, 14)
            if index is not None:
                self.selected = index
                self.choose_action(ACTIONS[index])
        elif self.state in ("moves", "party", "bag", "target"):
            index = ui.row_index(LIST_RECT[1] + 18, 14, len(self._list_choices()), pos, 7, 200)
            if index is not None:
                self.sub_selected = index
                self._pick(self._list_choices()[index])

    # ================================================================== actions
    def choose_move(self, move_id):
        try:
            move = self.battle.choose_move(move_id)
        except BattleError as error:
            self.message = str(error)
            return
        self.poses["player"] = ("windup", -1)
        self._open_question(move.topic, "move")

    def _open_question(self, topic, kind):
        decision = self.orchestrator.request_question(self.player_id, topic, context="capture" if kind == "capture" else "battle",
                                                      affinity=self.active.species_id,
                                                      min_difficulty=self.min_difficulty)
        self.panel_kind = kind
        self.panel = QuestionPanel(self.orchestrator, self.player_id, decision.question,
                                   max_attempts=1 if kind == "capture" else 2, allow_worked=kind != "capture",
                                   context=kind, proactive_hint=decision.tutor, llm=self.llm)
        self.state = "question"

    def _question_key(self, key, unicode, confirm):
        panel_ = self.panel
        if panel_.resolved:
            if confirm:
                self._finish_question()
            return
        result = panel_.handle_key(key, unicode)
        if result == "cancel":
            self.battle.cancel_question()
            self.panel = None
            self.poses["player"] = ("idle", 0)
            self.state, self.message = "menu", "Take your time. Choose again when you're ready."

    def answer(self, text):
        """Submit an answer programmatically (tests, touch input)."""
        return self.panel.submit(text)

    def _finish_question(self):
        panel_, kind = self.panel, self.panel_kind
        self.panel = None
        self.answers.append(panel_.outcome)
        if kind == "move":
            self.poses["player"] = ("idle", 0)
            self._queue(self.battle.resolve_move(panel_.outcome))
        else:
            self._queue(self.battle.resolve_capture(panel_.correct))

    def switch_to(self, index):
        try:
            events = self.battle.switch(index)
        except BattleError as error:
            self.message = str(error)
            return
        self._queue(events)

    def choose_item(self, item):
        info = item_data()[item]
        if info["effect"] == "capture":
            try:
                topic = self.battle.begin_capture()
            except BattleError as error:
                self.message = str(error)
                return
            self._open_question(topic, "capture")
            self.panel.feedback = f"Binding challenge! Answer to strengthen the capsule ({self.enemy.name}'s affinity)."
            return
        if info["effect"] in ("heal", "revive"):
            self.pending_item, self.state, self.sub_selected = item, "target", 0
            return
        self.use_item(item, None)

    def use_item(self, item, target_index):
        try:
            events = self.battle.use_item(item, target_index)
        except BattleError as error:
            self.message = str(error)
            self.state = "bag"
            return
        self.pending_item = None
        self._queue(events)

    # ================================================================== drawing
    @staticmethod
    def _frame_pose(pose, frame):
        if pose == "idle":
            return ("idle", "idle2", "idle3", "idle2")[(frame // 18) % 4]
        return pose

    def draw(self, surface, frame=0):
        boss = self.battle.kind == "boss"
        self._draw_background(surface, frame, boss)
        self._draw_enemy(surface, frame)
        self._draw_player(surface, frame)
        self._draw_cards(surface)
        for popup in self.popups:
            rise = popup["age"] // 2
            text(surface, popup["text"], (popup["x"], popup["y"] - rise), popup["size"], popup["color"],
                 center=True, shadow=PALETTE["ink"])
        if self.state == "question" and self.panel:
            self.panel.draw(surface, (7, 120, 306, 94), frame,
                            "BINDING CHALLENGE  •  " + curriculum.label(self.panel.question.topic).upper()
                            if self.panel_kind == "capture" else None)
        else:
            self._draw_bottom(surface, frame)
        footer = {"question": "TYPE  ENTER: ANSWER  H: HINT  ESC: BACK (before answering)",
                  "events": "ENTER: NEXT", "over": "ENTER: CONTINUE"}.get(
            self.state, "ARROWS/1-4: CHOOSE   ENTER: SELECT   ESC: BACK")
        text(surface, footer, (160, 228), 9, PALETTE["cream"], center=True)

    # Battle scenery per world: (sky, ground, trees/rocks/towers).
    SCENES = {"number_forest": ((76, 126, 132), (97, 157, 110), (53, 101, 75)),
              "crystal_realm": ((30, 26, 70), (90, 76, 146), (60, 50, 110)),
              "algebra_cavern": ((30, 26, 38), (78, 72, 92), (48, 42, 60)),
              "geometry_kingdom": ((120, 170, 200), (120, 176, 100), (200, 196, 184)),
              "chronos_dimension": ((26, 18, 48), (150, 120, 80), (70, 52, 100))}

    def _draw_background(self, surface, frame, boss):
        sky, ground, trees = self.SCENES.get(self.scene, self.SCENES["number_forest"])
        if boss:   # boss fights are a darker version of the same place
            sky, ground, trees = (tuple(c * 3 // 5 for c in sky), tuple(c * 3 // 4 for c in ground),
                                  tuple(c * 3 // 5 for c in trees))
        surface.fill(sky)
        pygame.draw.rect(surface, ground, (0, 78, 320, 54))
        for i in range(12):
            x = (i * 31 + frame // 4) % 350 - 15
            pygame.draw.rect(surface, trees, (x, 47 + (i % 3) * 6, 18, 34))
            pygame.draw.rect(surface, tuple(min(255, c + 16) for c in trees), (x - 5, 40 + (i % 3) * 6, 27, 13))
        pygame.draw.ellipse(surface, tuple(min(255, c + 40) for c in ground), (-12, 95, 150, 38))
        pygame.draw.ellipse(surface, tuple(min(255, c + 34) for c in ground), (179, 65, 160, 37))

    def _draw_enemy(self, surface, frame):
        if self.enemy_gone and not (self.capsule and self.capsule_success is False and self.capsule < 20):
            if self.capsule or self.outcome == "captured":
                self._draw_capsule(surface, frame)
            return
        slide = max(0, 30 - self.age) * 4
        shake = ((self.shake["enemy"] % 4) - 1.5) * 2 if self.shake["enemy"] else 0
        pose = self._frame_pose(self.poses["enemy"][0], frame)
        tint = PALETTE["white"] if self.flash["enemy"] % 4 >= 2 else None
        height = 58 if self.battle.kind == "boss" else 46
        draw_creature(surface, self.enemy.spec, (252 + slide + shake, 72), height, pose, flip=True, tint=tint)

    def _draw_capsule(self, surface, frame):
        wobble = 0 if self.capsule <= 0 else ((self.capsule // 6) % 3 - 1) * 2
        x, y = 252 + wobble, 66
        pygame.draw.circle(surface, PALETTE["ink"], (x, y), 9)
        pygame.draw.circle(surface, PALETTE["coral"], (x, y), 8)
        pygame.draw.rect(surface, PALETTE["white"], (x - 8, y, 17, 8))
        pygame.draw.line(surface, PALETTE["ink"], (x - 8, y), (x + 8, y), 2)
        pygame.draw.circle(surface, PALETTE["gold"], (x, y), 3)
        if self.outcome == "captured" and frame % 30 < 15:
            for dx, dy in ((-12, -10), (12, -12), (0, -16)):
                pygame.draw.rect(surface, PALETTE["gold"], (x + dx, y + dy, 2, 2))

    def _draw_player(self, surface, frame):
        slide = max(0, 30 - self.age) * 4
        shake = ((self.shake["player"] % 4) - 1.5) * 2 if self.shake["player"] else 0
        pose = self._frame_pose(self.poses["player"][0], frame)
        tint = PALETTE["coral"] if self.flash["player"] % 4 >= 2 else None
        draw_creature(surface, self.active.spec, (64 - slide + shake, 120), 52, pose, tint=tint)

    def _element_badge(self, surface, element, pos):
        color = elemental_system.color(element)
        rect = pygame.Rect(pos[0], pos[1], 40, 9)
        pygame.draw.rect(surface, color, rect)
        text(surface, element.upper(), (rect.centerx, rect.centery), 8, PALETTE["ink"], center=True)

    def _draw_cards(self, surface):
        enemy = self.enemy
        border = PALETTE["coral"] if self.battle.kind == "boss" else None
        panel(surface, (8, 8, 150, 42), PALETTE["night"], border)
        name = enemy.spec.display_name if self.battle.kind == "boss" else enemy.name
        text(surface, name[:24], (14, 11) if len(name) <= 16 else (14, 12), 11 if len(name) <= 16 else 8,
             PALETTE["white"])
        text(surface, f"Lv {enemy.level}", (152, 11), 9, PALETTE["cream"], align="right")
        self._element_badge(surface, enemy.element, (14, 24))
        text(surface, f"{max(0, round(self.shown['enemy']))}/{enemy.max_hp}", (152, 24), 9, PALETTE["muted"], align="right")
        meter(surface, 14, 37, 138, 6, self.shown["enemy"], enemy.max_hp, PALETTE["coral"], warn=True)

        me = self.active
        panel(surface, (152, 72, 160, 46), PALETTE["night"])
        text(surface, f"{me.name[:12]}", (158, 75), 11, PALETTE["white"])
        text(surface, f"Lv {me.level}", (306, 75), 9, PALETTE["cream"], align="right")
        self._element_badge(surface, me.element, (230, 76))
        meter(surface, 158, 89, 110, 6, self.shown["player"], me.max_hp, PALETTE["mint"], warn=True)
        text(surface, f"{max(0, round(self.shown['player']))}/{me.max_hp}", (306, 88), 9, PALETTE["cream"], align="right")
        meter(surface, 158, 99, 110, 4, me.exp, me.next_level_exp, PALETTE["sky"])
        text(surface, "EXP", (306, 97), 8, PALETTE["sky"], align="right")
        text(surface, "FOCUS", (158, 106), 8, PALETTE["gold"])
        for i in range(3):
            lit = i < self.battle.focus
            pygame.draw.rect(surface, PALETTE["gold"] if lit else PALETTE["deep"], (188 + i * 9, 107, 7, 6))
        status = []
        if self.battle.player_shield:
            status.append("SHIELD")
        if self.battle.enemy_debuffed:
            status.append("FOE WEAK")
        if self.battle.enemy_delayed:
            status.append("FOE STUCK")
        if status:
            text(surface, " ".join(status), (306, 106), 8, PALETTE["mint"], align="right")

    def _draw_bottom(self, surface, frame):
        if self.state in ("moves", "party", "bag", "target"):
            self._draw_list(surface, frame)
            return
        width = 193 if self.state == "menu" else 306
        panel(surface, (7, 128, width, 84), PALETTE["night"])
        wrapped(surface, self.message, (15, 136, width - 16, 70), 12, PALETTE["white"], 13, 5)
        if self.state == "events" and frame % 40 < 26:
            pygame.draw.polygon(surface, PALETTE["gold"], [(width - 6, 202), (width, 202), (width - 3, 206)])
        if self.state == "menu":
            labels = list(ACTIONS)
            disabled = () if self.battle.can_run else (3,)
            panel(surface, (207, 128, 106, 20), PALETTE["night"])
            text(surface, f"FOCUS {self.battle.focus}/3", (214, 132), 9, PALETTE["gold"])
            menu(surface, MENU_RECT, labels, self.selected, 11, frame, disabled, 14)
        elif self.state == "over":
            pass

    def _draw_list(self, surface, frame):
        panel(surface, LIST_RECT, PALETTE["night"])
        choices = self._list_choices()
        title = {"moves": "FIGHT - choose a move", "party": "MONSTER - who battles?", "bag": "BAG",
                 "target": f"Use {self.pending_item} on..."}[self.state]
        if self.state == "party" and self.battle.awaiting == "switch":
            title = "Choose who battles next!"
        text(surface, title, (14, 132), 10, PALETTE["gold"])
        detail = ""
        for index, choice in enumerate(choices):
            y = 146 + index * 14
            chosen = index == self.sub_selected
            if chosen:
                pygame.draw.rect(surface, PALETTE["deep"], (11, y - 2, 190, 13))
                ui.cursor(surface, 13, y + 1, PALETTE["gold"], frame)
            if self.state == "moves":
                usable, _ = self.battle.move_usable(choice)
                color = PALETTE["gold"] if chosen else (PALETTE["white"] if usable else PALETTE["muted"])
                text(surface, f"{index + 1} {choice.name}", (22, y), 10, color)
                cost = f"F{choice.focus}" if choice.focus else ""
                text(surface, cost, (196, y), 9, PALETTE["gold"] if usable else PALETTE["coral"], align="right")
                if chosen:
                    power = "Support" if choice.kind == "support" else f"Power {self.battle.move_power(choice)}"
                    detail = (f"{choice.element} • {curriculum.label(choice.topic)} • {power} • Focus {choice.focus}. "
                              f"{choice.description} {elemental_system.message(choice.element, self.enemy.element)}")
            elif self.state in ("party", "target"):
                usable = not choice.fainted and choice is not self.active if self.state == "party" else True
                color = PALETTE["gold"] if chosen else (PALETTE["white"] if usable else PALETTE["muted"])
                text(surface, f"{index + 1} {choice.name[:10]} Lv{choice.level}", (22, y), 10, color)
                meter(surface, 130, y + 2, 66, 5, choice.hp, choice.max_hp, PALETTE["mint"], warn=True)
                if chosen:
                    effect = elemental_system.message(choice.element, self.enemy.element)
                    state = "FAINTED" if choice.fainted else f"{choice.hp}/{choice.max_hp} HP"
                    detail = f"{choice.name} ({choice.element}) {state}. Its {choice.element} moves vs {self.enemy.name}: {effect}"
                    if self.state == "party" and self.battle.awaiting != "switch":
                        detail += " Switching uses your turn."
            else:
                count = self.bag.count(choice)
                text(surface, f"{index + 1} {choice}", (22, y), 10, PALETTE["gold"] if chosen else PALETTE["white"])
                text(surface, f"x{count}", (196, y), 9, PALETTE["cream"], align="right")
                if chosen:
                    detail = item_data()[choice]["description"] + " Uses your turn."
                    if choice == "Math Capsule" and self.battle.capture_block_reason():
                        detail = self.battle.capture_block_reason()
        panel(surface, (208, 140, 102, 68), PALETTE["ink"], PALETTE["deep"])
        wrapped(surface, detail or self.message, (213, 145, 94, 60), 8, PALETTE["cream"], 9, 6)


Battle = BattleScreen

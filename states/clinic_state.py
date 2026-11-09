"""The MATHMON RECOVERY CENTER: one MathMon at a time goes into the Recovery Capsule.

    choose   -> pick which hurt (or fainted) MathMon to place in the capsule
    question -> Nurse Hana asks up to three problems while it floats in the healing liquid
    result   -> after each answer; a right answer heals it by 34% of its max HP (reviving a fainted
                one), a wrong answer still heals 10% and shows the worked explanation - the clinic
                should never feel like a penalty. Three right answers fully restore it.
    done     -> it is discharged; choose the next one, or leave when the whole team is healthy

The capsule is drawn in code (no sprite sheet) with the player's own MathMon inside, so the scene
always shows the right monster. All numbers live in data/rules.json ("clinic").
"""
import json
import math

import pygame

from config import PALETTE, ROOT
from game import audio
from game.creatures import draw_creature
from game.question_panel import QuestionPanel
from game.ui import cursor, meter, panel, text, wrapped
from monsters.monster_data import rules
from states.base import CONFIRM, DOWN, UP, Screen

CLINIC_DIR = ROOT / "assets" / "sprites" / "clinic"
STAGES = ("Capsule ready", "Patient admitted", "Diagnostics", "Healing pulse", "Wound closure",
          "Energy boost", "Restoration", "Verification", "Ready for discharge")
_images = {}


def clinic_image(name):
    """A processed clinic frame (see tools/process_building_art.py), or None if the art is missing."""
    if name not in _images:
        path = CLINIC_DIR / f"{name}.png"
        try:
            image = pygame.image.load(str(path))
            _images[name] = image.convert() if pygame.display.get_surface() else image
        except (pygame.error, FileNotFoundError):
            _images[name] = None
    return _images[name]


def manifest():
    try:
        return json.loads((CLINIC_DIR / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"nurse_moods": {}}


def draw_capsule(surface, rect, monster, stage, frame):
    """The Recovery Capsule: a glass tube whose healing liquid rises with ``stage`` (0-8), with the
    patient MathMon floating inside, bubbles, and status lights that turn from red to green."""
    x, y, w, h = rect
    cx = x + w // 2
    tube = pygame.Rect(cx - 30, y + 14, 60, h - 44)
    # Machine base and cap.
    pygame.draw.rect(surface, (52, 60, 78), (cx - 40, tube.bottom - 2, 80, 26), border_radius=6)
    pygame.draw.rect(surface, (30, 36, 50), (cx - 40, tube.bottom - 2, 80, 26), 2, border_radius=6)
    pygame.draw.rect(surface, (52, 60, 78), (cx - 36, y + 4, 72, 14), border_radius=5)
    pygame.draw.rect(surface, (30, 36, 50), (cx - 36, y + 4, 72, 14), 2, border_radius=5)
    for side in (-1, 1):   # coolant hoses
        hx = cx + side * 40
        pygame.draw.line(surface, (70, 120, 200), (hx, tube.bottom + 8), (hx + side * 6, tube.bottom - 30), 4)
    # Glass back, then the liquid.
    pygame.draw.rect(surface, (24, 44, 58), tube, border_radius=10)
    level = 0.12 + 0.88 * min(8, stage) / 8 if monster else 0.0
    liquid_h = int((tube.h - 6) * level)
    if liquid_h:
        glow = 0.4 + 0.6 * min(8, stage) / 8
        color = (int(40 + 60 * glow), int(120 + 110 * glow), int(110 + 70 * glow))
        wave = int(2 * math.sin(frame / 9))
        liquid = pygame.Rect(tube.x + 3, tube.bottom - 3 - liquid_h + wave, tube.w - 6, liquid_h - wave)
        pygame.draw.rect(surface, color, liquid, border_radius=8)
        for i in range(6):   # bubbles drifting up
            bx = tube.x + 8 + (i * 11 + frame // 3) % (tube.w - 16)
            by = tube.bottom - 6 - ((frame * (1 + i % 3) + i * 23) % max(1, liquid_h - 6))
            pygame.draw.circle(surface, (200, 255, 240), (bx, by), 1 + i % 2, 1)
    if monster:
        bob = int(3 * math.sin(frame / 14))
        pose = "hurt" if monster.fainted and stage == 0 else "idle"
        draw_creature(surface, monster.spec, (cx, tube.bottom - 18 + bob), 46, pose)
    else:
        text(surface, "EMPTY", (cx, tube.centery), 9, PALETTE["muted"], center=True)
    # Glass shine and frame.
    pygame.draw.line(surface, (220, 250, 255), (tube.x + 8, tube.y + 10), (tube.x + 8, tube.bottom - 14), 2)
    pygame.draw.rect(surface, (150, 190, 210), tube, 2, border_radius=10)
    # Status lights: red while healing starts, yellow mid-way, green when ready.
    lit = (220, 70, 70) if stage < 3 else (240, 200, 70) if stage < 8 else (90, 230, 120)
    for i in range(3):
        on = monster is not None and (frame // 12 + i) % 3 != 0
        pygame.draw.circle(surface, lit if on else (40, 44, 56), (cx - 16 + i * 16, tube.bottom + 13), 3)


class ClinicScreen(Screen):
    def __init__(self, game):
        super().__init__(game)
        cfg = rules()["clinic"]
        self.questions = int(cfg["questions"])
        self.heal_correct, self.heal_wrong = float(cfg["heal_correct"]), float(cfg["heal_wrong"])
        self.info = manifest()
        self.patient = None             # the MathMon in the capsule
        self.asked = self.correct = 0
        self.stage = 0                  # capsule progress 0-8
        self.panel = None
        self.mood = "welcome"
        self.last_heal = 0
        self.selected = self._first_hurt()
        if self.all_healthy():
            self.state, self.mood = "all_done", "happy"
            self.message = "Your team is already in perfect health! Come back after your next adventure."
        else:
            self.state = "choose"
            self.message = ("Welcome to the Mathmon Recovery Center! Which MathMon should rest in the Recovery "
                            "Capsule? Solve my problems to power it.")

    # ------------------------------------------------------------------ rules
    def all_healthy(self):
        return all(m.hp >= m.max_hp for m in self.party.party)

    @staticmethod
    def hurt(monster):
        return monster.hp < monster.max_hp

    def _first_hurt(self):
        return next((i for i, m in enumerate(self.party.party) if self.hurt(m)), 0)

    def heal(self, fraction):
        """Heal the patient only. Returns the HP restored."""
        monster = self.patient
        amount = max(1, round(monster.max_hp * fraction))
        if monster.fainted:
            monster.hp = min(monster.max_hp, amount)
            restored = monster.hp
        else:
            restored = monster.heal(amount)
        self.game.save_party()
        return restored

    def admit(self, index):
        """Place party member ``index`` in the capsule and start its check-up."""
        monster = self.party.party[index]
        if not self.hurt(monster):
            self.message = f"{monster.name} is already healthy! Choose a MathMon that needs care."
            self.mood = "point"
            return False
        self.patient = monster
        self.asked = self.correct = 0
        self.stage = 1
        audio.play("select")
        self.next_question()
        return True

    def next_question(self):
        decision = self.game.orchestrator.request_question(self.player_id, None, context="clinic")
        self.panel = QuestionPanel(self.game.orchestrator, self.player_id, decision.question, context="clinic",
                                   proactive_hint=decision.tutor, cancellable=False, llm=self.game.llm)
        self.state, self.mood = "question", "thinking"

    def answer(self, value):
        """Submit an answer programmatically (tests)."""
        return self.panel.submit(value)

    def finish_question(self):
        self.asked += 1
        name = self.patient.name
        if self.panel.correct:
            self.correct += 1
            self.last_heal = self.heal(self.heal_correct)
            self.stage = min(8, self.stage + 3)
            self.mood = "check"
            self.message = f"Capsule charged! {name} recovered {self.last_heal} HP."
            audio.play("heal")
        else:
            self.last_heal = self.heal(self.heal_wrong)
            self.stage = min(8, self.stage + 1)
            self.mood = "listen"
            self.message = (f"Good effort - the capsule still gave {name} {self.last_heal} HP. "
                            "Let's look at the next one together.")
        self.panel = None
        if self.correct >= self.questions or not self.hurt(self.patient):
            if self.correct >= self.questions:
                self.patient.hp = self.patient.max_hp     # three right answers always mean a full recovery
                self.game.save_party()
            self.stage, self.mood, self.state = 8, "cheer", "done"
            audio.play("levelup")
            if self.all_healthy():
                self.message = f"{name} is ready for discharge! Your whole team is healthy. Take care out there!"
            else:
                self.message = f"{name} is ready for discharge! Who should go in the capsule next?"
        else:
            self.state = "result"
            if self.asked >= self.questions:
                self.message += " Want another round to finish healing?"

    def discharge(self):
        """Back to choosing (or finished, if everyone is healthy)."""
        self.patient, self.stage = None, 0
        if self.all_healthy():
            self.state, self.mood = "all_done", "happy"
            self.message = "Your whole team is in perfect health!"
        else:
            self.state, self.mood = "choose", "welcome"
            self.selected = self._first_hurt()

    # ------------------------------------------------------------------ input
    def items(self):
        return list(self.party.party) if self.state == "choose" else []

    def rows(self):
        return 52, 22, 108, 314

    def activate(self, index):
        if self.state == "choose":
            self.admit(index)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.state not in ("question", "choose"):
            self.handle_key(pygame.K_RETURN)
            return
        super().handle_event(event)

    def handle_key(self, key, unicode=""):
        if self.state == "question":
            if self.panel.resolved:
                if key in CONFIRM:
                    self.finish_question()
            else:
                self.panel.handle_key(key, unicode)
                if self.panel.used_hint:
                    self.mood = "idea"
            return
        if self.state == "choose":
            if key == pygame.K_ESCAPE:
                self.close()
            elif key in UP or key in DOWN or key in CONFIRM or pygame.K_1 <= key <= pygame.K_9:
                super().handle_key(key, unicode)
            return
        if key == pygame.K_ESCAPE:
            self.close()
        elif self.state == "all_done" and key in CONFIRM:
            self.close()
        elif self.state == "done" and key in CONFIRM:
            self.discharge()
        elif self.state == "result" and key in CONFIRM:
            if self.asked >= self.questions:
                self.asked = self.correct = 0
            self.next_question()

    def update(self):
        if self.panel:
            self.panel.update()

    # ------------------------------------------------------------------ drawing
    def draw(self, surface, frame=0):
        footers = {"choose": "UP/DOWN: CHOOSE   ENTER: PLACE IN CAPSULE   ESC: LEAVE",
                   "result": "ENTER: NEXT PROBLEM   ESC: LEAVE", "done": "ENTER: CONTINUE",
                   "all_done": "ENTER: LEAVE", "question": "TYPE  ENTER: ANSWER  H: HINT  W: EXAMPLE"}
        self.draw_frame(surface, "MATHMON RECOVERY CENTER", PALETTE["mint"], footers[self.state])
        # The Recovery Capsule (left).
        panel(surface, (4, 28, 96, 150), PALETTE["night"], PALETTE["mint"])
        preview = self.patient or (self.party.party[self.selected] if self.state == "choose" and self.party.party
                                   else None)
        draw_capsule(surface, (6, 30, 92, 136), preview if self.patient else None, self.stage, frame)
        if self.state == "choose" and preview is not None:
            text(surface, f"PLACE {preview.name[:10]}?", (52, 168), 7, PALETTE["gold"], center=True)
        else:
            text(surface, STAGES[min(8, self.stage)].upper(), (52, 168), 7, PALETTE["mint"], center=True)
        # Right side: the patient list, the question, or Nurse Hana.
        if self.state == "question" and self.panel:
            self.panel.draw(surface, (104, 28, 212, 150), frame, f"CHECK-UP: {self.patient.name}")
        elif self.state == "choose":
            self._draw_choose(surface, frame)
        else:
            self._draw_nurse(surface)
        # The patient's HP (or the whole team while choosing) along the bottom.
        panel(surface, (4, 182, 312, 34), PALETTE["night"])
        team = [self.patient] if self.patient else self.party.party
        for i, monster in enumerate(team):
            x = 10 + i * 104
            draw_creature(surface, monster.spec, (x + 10, 212), 18, "hurt" if monster.fainted else "idle")
            text(surface, monster.name[:9], (x + 24, 186), 8, PALETTE["white"])
            meter(surface, x + 24, 198, 70 if not self.patient else 200, 5, monster.hp, monster.max_hp,
                  PALETTE["mint"], warn=True)
            text(surface, "FAINTED" if monster.fainted else f"{monster.hp}/{monster.max_hp}", (x + 24, 205), 7,
                 PALETTE["coral"] if monster.fainted else PALETTE["cream"])

    def _draw_choose(self, surface, frame):
        panel(surface, (104, 28, 212, 150), PALETTE["night"])
        text(surface, "WHO NEEDS THE CAPSULE?", (112, 34), 10, PALETTE["gold"])
        for i, monster in enumerate(self.party.party):
            y = 52 + i * 22
            chosen = i == self.selected
            if chosen:
                pygame.draw.rect(surface, PALETTE["deep"], (108, y - 2, 204, 20))
                cursor(surface, 110, y + 6, PALETTE["gold"], frame)
            draw_creature(surface, monster.spec, (130, y + 17), 16, "hurt" if monster.fainted else "idle")
            tone = PALETTE["white"] if self.hurt(monster) else PALETTE["muted"]
            text(surface, f"{i + 1}. {monster.name[:10]}", (144, y), 9, tone)
            status = "FAINTED" if monster.fainted else ("HEALTHY" if not self.hurt(monster)
                                                        else f"{monster.hp}/{monster.max_hp}")
            text(surface, status, (308, y), 8, PALETTE["coral"] if monster.fainted else PALETTE["cream"],
                 align="right")
            meter(surface, 144, y + 11, 160, 4, monster.hp, monster.max_hp, PALETTE["mint"], warn=True)
        wrapped(surface, self.message, (112, 124, 196, 50), 8, PALETTE["muted"], 9, 5)

    def _draw_nurse(self, surface):
        moods = self.info.get("nurse_moods", {})
        nurse = clinic_image(f"nurse_{moods.get(self.mood, 0)}")
        panel(surface, (104, 28, 212, 150), PALETTE["night"])
        if nurse:
            surface.blit(nurse, (110, 32))
        text(surface, "NURSE HANA", (204, 34), 11, PALETTE["gold"])
        wrapped(surface, self.message, (204, 48, 106, 66), 9, PALETTE["white"], 10, 7)
        for i in range(self.questions):
            done = i < self.asked
            lit = i < self.correct
            color = PALETTE["mint"] if lit else (PALETTE["coral"] if done else PALETTE["deep"])
            pygame.draw.circle(surface, color, (212 + i * 14, 124), 5)
        text(surface, "CHARGE", (256, 120), 8, PALETTE["muted"])

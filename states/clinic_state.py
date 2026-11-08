"""The MATHMON RECOVERY CENTER (bug report: "restore health by solving maths problems").

Nurse Hana powers the Recovery Chamber with maths. A round is up to three questions (the AI picks
the learner's most useful topic). Every correct answer heals each party monster by 34% of its
max HP - reviving fainted ones - and moves the chamber animation forward; a wrong answer still
heals 10% and shows the worked explanation, because the clinic should never feel like a penalty.
Three right answers fully restore the team. Unfinished? Start another round straight away.
All numbers live in data/rules.json ("clinic").
"""
import json

import pygame

from config import PALETTE, ROOT
from game import audio
from game.creatures import draw_creature
from game.question_panel import QuestionPanel
from game.ui import meter, panel, text, wrapped
from monsters.monster_data import rules
from states.base import CONFIRM, Screen

CLINIC_DIR = ROOT / "assets" / "sprites" / "clinic"
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
        return {"chamber_stages": [""] * 9, "nurse_moods": {}}


class ClinicScreen(Screen):
    def __init__(self, game):
        super().__init__(game)
        cfg = rules()["clinic"]
        self.questions = int(cfg["questions"])
        self.heal_correct, self.heal_wrong = float(cfg["heal_correct"]), float(cfg["heal_wrong"])
        self.info = manifest()
        self.state = "intro"            # intro | question | result | done
        self.asked = self.correct = 0
        self.stage = 0                  # recovery chamber frame 0-8
        self.panel = None
        self.mood = "welcome"
        self.last_heal = 0
        self.message = ("Welcome to the Mathmon Recovery Center! Solve up to three problems to power the Recovery "
                        "Chamber. Every right answer heals your whole team.")
        if self.all_healthy():
            self.message = "Your team is already in perfect health! Come back after your next adventure."
            self.state, self.mood = "done", "happy"

    # ------------------------------------------------------------------ rules
    def all_healthy(self):
        return all(m.hp >= m.max_hp for m in self.party.party)

    def heal(self, fraction):
        restored = 0
        for monster in self.party.party:
            amount = max(1, round(monster.max_hp * fraction))
            if monster.fainted:
                monster.hp = min(monster.max_hp, amount)
                restored += monster.hp
            else:
                restored += monster.heal(amount)
        self.game.save_party()
        return restored

    def start_round(self):
        self.asked = self.correct = 0
        self.stage = 0
        self.next_question()

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
        if self.panel.correct:
            self.correct += 1
            self.last_heal = self.heal(self.heal_correct)
            self.stage = min(8, self.stage + 3)
            self.mood = "check"
            self.message = f"Chamber charged! Your team recovered {self.last_heal} HP."
            audio.play("heal")
        else:
            self.last_heal = self.heal(self.heal_wrong)
            self.stage = min(8, self.stage + 1)
            self.mood = "listen"
            self.message = (f"Good effort - the chamber still gave your team {self.last_heal} HP. "
                            "Let's look at the next one together.")
        self.panel = None
        if self.correct >= self.questions or self.all_healthy():
            if self.correct >= self.questions:
                self.heal(1.0)   # three right answers always mean a full recovery
            self.stage, self.mood, self.state = 8, "cheer", "done"
            self.message = "Ready for discharge! Your team is fully healed. Take care out there!"
            audio.play("levelup")
        elif self.asked >= self.questions:
            self.state = "result"
            self.message += " Want another round to finish healing?"
        else:
            self.state = "result"

    # ------------------------------------------------------------------ input
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.state != "question":
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
        if key == pygame.K_ESCAPE or (self.state == "done" and key in CONFIRM):
            self.close()
        elif key in CONFIRM:
            if self.state == "intro" or (self.state == "result" and self.asked >= self.questions):
                self.start_round()
            else:
                self.next_question()

    def update(self):
        if self.panel:
            self.panel.update()

    # ------------------------------------------------------------------ drawing
    def draw(self, surface, frame=0):
        footers = {"intro": "ENTER: START   ESC: LEAVE", "result": "ENTER: NEXT PROBLEM   ESC: LEAVE",
                   "done": "ENTER: LEAVE", "question": "TYPE  ENTER: ANSWER  H: HINT  W: EXAMPLE"}
        self.draw_frame(surface, "MATHMON RECOVERY CENTER", PALETTE["mint"], footers[self.state])
        # Recovery chamber (left) and Nurse Hana (right top).
        chamber = clinic_image(f"chamber_{self.stage}")
        panel(surface, (4, 28, 96, 150), PALETTE["night"], PALETTE["mint"])
        if chamber:
            surface.blit(chamber, (7, 31))
        stages = self.info.get("chamber_stages", [])
        if self.stage < len(stages):
            text(surface, stages[self.stage].upper(), (52, 172), 7, PALETTE["mint"], center=True)
        moods = self.info.get("nurse_moods", {})
        nurse = clinic_image(f"nurse_{moods.get(self.mood, 0)}")
        if self.state == "question" and self.panel:
            self.panel.draw(surface, (104, 28, 212, 150), frame, "NURSE HANA'S CHECK-UP")
        else:
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
        # The team's HP along the bottom.
        panel(surface, (4, 182, 312, 34), PALETTE["night"])
        for i, monster in enumerate(self.party.party):
            x = 10 + i * 104
            draw_creature(surface, monster.spec, (x + 10, 212), 18, "hurt" if monster.fainted else "idle")
            text(surface, monster.name[:9], (x + 24, 186), 8, PALETTE["white"])
            meter(surface, x + 24, 198, 70, 5, monster.hp, monster.max_hp, PALETTE["mint"], warn=True)
            text(surface, "FAINTED" if monster.fainted else f"{monster.hp}/{monster.max_hp}", (x + 24, 205), 7,
                 PALETTE["coral"] if monster.fainted else PALETTE["cream"])

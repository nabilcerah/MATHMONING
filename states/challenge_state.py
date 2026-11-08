"""Puzzle gates and quest challenges (GDD 10.2, 11): a short run of verified questions using the
same question flow as battles. Difficulty is chosen by the AI Difficulty Manager from the
learner's profile (GDD 15: adaptive learning influences puzzle difficulty), but the pass rule -
``need`` correct out of the questions - is fixed in data/quests.json."""
import pygame

from config import PALETTE
from game.question_panel import QuestionPanel
from game.ui import panel, text, wrapped
from monsters.monster_data import challenges
from states.base import CONFIRM, Screen


class ChallengeScreen(Screen):
    def __init__(self, game, challenge_id):
        super().__init__(game)
        self.challenge_id = challenge_id
        self.spec = challenges()[challenge_id]
        self.index = 0
        self.correct = 0
        self.panel = None
        self.state = "intro"       # intro | question | done
        self.passed = False

    @property
    def total(self):
        return len(self.spec["questions"])

    def _next_question(self):
        entry = self.spec["questions"][self.index]
        decision = self.game.orchestrator.request_question(self.player_id, entry["topic"], context="challenge",
                                                           subtopic=entry.get("subtopic"))
        self.panel = QuestionPanel(self.game.orchestrator, self.player_id, decision.question, context="challenge",
                                   proactive_hint=decision.tutor, cancellable=False, llm=self.game.llm)
        self.state = "question"

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.state != "question":
            self.handle_key(pygame.K_RETURN)
            return
        super().handle_event(event)

    def handle_key(self, key, unicode=""):
        if self.state == "intro":
            if key in CONFIRM:
                self._next_question()
            elif key == pygame.K_ESCAPE:
                self.close(False)
        elif self.state == "question":
            if self.panel.resolved:
                if key in CONFIRM:
                    self._after_question()
            else:
                self.panel.handle_key(key, unicode)
        elif key in CONFIRM or key == pygame.K_ESCAPE:
            self.close(self.passed)

    def answer(self, text_):
        return self.panel.submit(text_)

    def _after_question(self):
        self.correct += int(self.panel.correct)
        self.index += 1
        remaining = self.total - self.index
        if self.correct >= self.spec["need"] or self.correct + remaining < self.spec["need"] or not remaining:
            self.passed = self.correct >= self.spec["need"]
            self.state = "done"
            self.panel = None
            return
        self._next_question()

    def update(self):
        if self.panel:
            self.panel.update()

    def draw(self, surface, frame=0):
        self.draw_frame(surface, self.spec["title"], PALETTE["sky"],
                        "ENTER: BEGIN   ESC: LATER" if self.state == "intro" else
                        "TYPE  ENTER: ANSWER  H: HINT  W: EXAMPLE (after a miss)")
        text(surface, f"Solved {self.correct}/{self.spec['need']} needed   •   question {min(self.index + 1, self.total)}"
                      f" of {self.total}", (160, 32), 9, PALETTE["cream"], center=True)
        for i in range(self.total):
            color = PALETTE["mint"] if i < self.correct else (PALETTE["gold"] if i == self.index else PALETTE["deep"])
            pygame.draw.circle(surface, color, (160 - (self.total - 1) * 8 + i * 16, 46), 5)
        if self.state == "intro":
            panel(surface, (20, 64, 280, 90), PALETTE["night"])
            wrapped(surface, self.spec.get("intro", ""), (30, 74, 260, 40), 11, PALETTE["white"], 12, 3)
            wrapped(surface, f"Answer {self.spec['need']} of {self.total} correctly. You can use a hint, and you get a "
                             "second try. No timer - take your time.", (30, 116, 260, 36), 9, PALETTE["cream"], 10, 3)
        elif self.state == "question" and self.panel:
            self.panel.draw(surface, (8, 58, 304, 150), frame)
        else:
            panel(surface, (20, 70, 280, 80), PALETTE["night"], PALETTE["mint"] if self.passed else PALETTE["coral"])
            title = "CHALLENGE COMPLETE!" if self.passed else "NOT YET..."
            text(surface, title, (160, 86), 16, PALETTE["mint"] if self.passed else PALETTE["coral"], center=True)
            body = ("The old magic answers your maths. Well done!" if self.passed else
                    "No penalty - practise a little and come back. The AI will pick gentler questions next time.")
            wrapped(surface, body, (34, 104, 252, 40), 10, PALETTE["white"], 11, 3)

"""The QUESTION screen (GDD 26), used by battles, captures, puzzle gates and quest challenges.

Flow (GDD 7.4): first attempt -> (optional hint) -> a second attempt after a wrong answer ->
resolved. After a wrong first answer the AI Tutor explains the likely mistake WITHOUT giving the
answer; the learner may also ask for a worked example on different numbers. Unreadable input
("abc") never costs an attempt. No timer: the learner always has time to think.
"""
import pygame

from ai.schemas import TutorResponse, validate_tutor
from combat import battle_rules
from game import audio
from game.visual_hint import draw_visual, hint_visual
from config import PALETTE
from game.ui import panel, text, wrap_lines, wrapped
from mathematics import curriculum

ALLOWED = set("0123456789.-/:+*()^= xyabnXY")


class QuestionPanel:
    def __init__(self, orchestrator, player_id, question, max_attempts=2, allow_hint=True, allow_worked=True,
                 context="battle", proactive_hint=None, cancellable=True, llm=None):
        self.orchestrator, self.player_id, self.question = orchestrator, player_id, question
        self.max_attempts = max_attempts
        self.allow_hint, self.allow_worked = allow_hint, allow_worked
        self.context, self.cancellable, self.llm = context, cancellable, llm
        self.answer = ""
        self.attempts = []
        self.used_hint = False
        self.worked_example = False
        self.hint_text = ""
        self.worked_text = ""
        self.feedback = proactive_hint.text if proactive_hint else ""
        self.proactive = proactive_hint is not None
        self.state = "answering"
        self.outcome = None
        self.explanation = ""
        self.recommendation = ""
        self.shake = 0
        self.future = None
        self.visual = hint_visual(question) if proactive_hint else None   # struggling learners see it at once
        self.visual_age = 0

    # ------------------------------------------------------------------ properties
    @property
    def resolved(self):
        return self.state == "resolved"

    @property
    def correct(self):
        return self.outcome not in (None, battle_rules.FAILED)

    @property
    def can_hint(self):
        return self.allow_hint and not self.used_hint and not self.resolved

    @property
    def can_worked(self):
        return self.allow_worked and not self.worked_example and bool(self.attempts) and not self.resolved

    # ------------------------------------------------------------------ input
    def handle_key(self, key, unicode=""):
        """Returns "resolved", "cancel" or None."""
        if self.resolved:
            return None
        if key == pygame.K_ESCAPE:
            return "cancel" if self.cancellable and not self.attempts else None
        if key == pygame.K_BACKSPACE:
            self.answer = self.answer[:-1]
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self.submit(self.answer)
        elif key == pygame.K_h and unicode.lower() == "h":
            self.request_hint()
        elif key == pygame.K_w and unicode.lower() == "w" and self.can_worked:
            self.request_worked()
        elif unicode and unicode in ALLOWED and len(self.answer) < 20:
            self.answer += unicode
        return None

    def request_hint(self):
        if not self.can_hint:
            self.feedback = "You've already used this question's hint." if self.used_hint else self.feedback
            return
        self.used_hint = True
        decision = self.orchestrator.handle({"type": "hint_request", "player_id": self.player_id,
                                             "question": self.question, "level": 1 if self.attempts else 0})
        self.hint_text = decision.message
        self.visual = hint_visual(self.question) or self.visual
        self.visual_age = 0
        audio.play("select")

    def request_worked(self):
        self.worked_example = True
        decision = self.orchestrator.handle({"type": "worked_example", "player_id": self.player_id,
                                             "question": self.question})
        self.worked_text = decision.message
        # Show the worked example as a picture too (it uses different numbers, so it may finish the sum).
        prompt = decision.message.split(": ", 1)[-1]
        example = type("Example", (), {"prompt": prompt, "topic": self.question.topic})()
        self.visual = hint_visual(example) or self.visual
        self.visual_age = 0

    def submit(self, answer):
        answer = str(answer).strip()
        if not answer:
            return None
        result = self.question.check(answer)
        self.answer = ""
        if not result.readable:
            self.feedback = result.reason          # unreadable input never costs an attempt
            self.shake = 10
            return None
        self.attempts.append(answer)
        if result.correct:
            return self._resolve(battle_rules.outcome_for(True, len(self.attempts), self.used_hint))
        if len(self.attempts) >= self.max_attempts:
            return self._resolve(battle_rules.FAILED)
        self.shake = 14
        audio.play("wrong")
        decision = self.orchestrator.handle({"type": "wrong_attempt", "player_id": self.player_id,
                                             "question": self.question, "submitted": answer})
        self.feedback = (result.reason + " " if result.reason else "") + decision.message
        return None

    def _resolve(self, outcome):
        self.outcome, self.state = outcome, "resolved"
        audio.play("wrong" if outcome == battle_rules.FAILED else "correct")
        decision = self.orchestrator.handle({
            "type": "answer_resolved", "player_id": self.player_id, "question": self.question,
            "outcome": outcome, "used_hint": self.used_hint, "attempts_used": len(self.attempts),
            "attempts": list(self.attempts), "worked_example": self.worked_example, "context": self.context})
        self.decision = decision
        self.explanation = decision.tutor.text if decision.tutor else self.question.explanation
        if decision.recommendation or (decision.message and decision.message != self.explanation):
            self.recommendation = decision.message
        if outcome == battle_rules.FAILED and self.llm is not None and getattr(self.llm, "available", False):
            self.future = self.llm.explain_async(self.question, self.attempts[-1], self.explanation)
        return "resolved"

    def update(self):
        self.visual_age += 1
        if self.shake:
            self.shake -= 1
        if self.future is not None and self.future.done():
            try:
                candidate = self.future.result()
                if candidate and candidate != self.explanation:
                    self.explanation = validate_tutor(TutorResponse("explanation", candidate, source="llm")).text
            except Exception:
                pass   # malformed or unsafe LLM text: keep the offline explanation
            self.future = None

    # ------------------------------------------------------------------ drawing
    def draw(self, surface, rect, frame=0, title=None):
        x, y, w, h = rect
        border = PALETTE["mint"] if self.resolved and self.correct else (
            PALETTE["coral"] if self.resolved else PALETTE["gold"])
        panel(surface, rect, PALETTE["night"], border)
        q = self.question
        header = title or f"{curriculum.label(q.topic).upper()}  •  {curriculum.DIFFICULTY_LABELS[q.difficulty].upper()}"
        text(surface, header, (x + 7, y + 5), 9, PALETTE["gold"])
        if not self.resolved:
            left = self.max_attempts - len(self.attempts)
            text(surface, f"TRIES {left}/{self.max_attempts}", (x + w - 7, y + 5), 9, PALETTE["muted"], align="right")
            vis_w = 118 if self.visual else 0
            inner = w - 14 - (vis_w + 4 if vis_w else 0)
            if vis_w:   # the picture IS the hint: it takes the right-hand side of the panel
                draw_visual(surface, self.visual, (x + w - vis_w - 5, y + 15, vis_w, h - 20), self.visual_age)
                bulb = PALETTE["gold"] if frame % 30 < 20 else PALETTE["cream"]
                pygame.draw.circle(surface, bulb, (x + w - vis_w - 2, y + 17), 4)
                pygame.draw.rect(surface, PALETTE["muted"], (x + w - vis_w - 4, y + 21, 4, 2))
            size = 14 if len(q.prompt) <= 22 and inner > 150 else 11 if len(q.prompt) <= 60 else 10
            lines = wrapped(surface, q.prompt, (x + 7, y + 16, inner, 30), size, PALETTE["white"], size + 1, 3)
            box_y = y + 18 + lines * (size + 1)
            jiggle = ((self.shake % 4) - 1.5) * 2 if self.shake else 0
            box_w = min(120, inner)
            pygame.draw.rect(surface, PALETTE["coral"] if self.shake else PALETTE["ink"], (x + 6 + jiggle, box_y, box_w, 17))
            pygame.draw.rect(surface, PALETTE["ink"], (x + 7 + jiggle, box_y + 1, box_w - 2, 15))
            caret = "_" if frame % 50 < 28 else " "
            text(surface, "> " + self.answer + caret, (x + 11 + jiggle, box_y + 3), 12, PALETTE["cream"])
            options = []
            if self.can_hint:
                options.append("H: HINT")
            if self.can_worked:
                options.append("W: EXAMPLE")
            if vis_w:
                text(surface, "   ".join(options), (x + 7, box_y + 20), 9, PALETTE["sky"])
                info_y = box_y + (31 if options else 21)
            else:
                text(surface, "   ".join(options), (x + 132, box_y + 4), 9, PALETTE["sky"])
                info_y = box_y + 21
            message = self.worked_text or self.hint_text or self.feedback
            if vis_w and not self.attempts:
                message = self.hint_text.split(". ")[0] if self.hint_text else ""   # a short caption, not a paragraph
            color = PALETTE["sky"] if (self.worked_text or self.hint_text) else (
                PALETTE["mint"] if self.proactive and not self.attempts else PALETTE["cream"])
            if self.feedback and (self.hint_text or self.worked_text) and self.attempts:
                message = f"{self.feedback}  {self.hint_text or self.worked_text}"
            if message:
                room = max(1, (y + h - info_y - 2) // 10)
                wrapped(surface, message, (x + 7, info_y, inner, room * 10), 9, color, 10, room)
        else:
            verdict = {"first_try": "CORRECT!", "after_hint": "CORRECT (WITH A HINT)", "second_attempt":
                       "CORRECT ON THE SECOND TRY", "failed": "NOT THIS TIME"}[self.outcome]
            text(surface, verdict, (x + 7, y + 17), 12, PALETTE["mint"] if self.correct else PALETTE["coral"])
            if not self.correct:
                text(surface, f"Answer: {q.answer}", (x + w - 7, y + 18), 10, PALETTE["gold"], align="right")
            body = self.explanation
            if self.recommendation:
                body = f"{body}  AI: {self.recommendation}"
            lines = wrap_lines(body, w - 14, 9)
            room = max(1, (h - 44) // 10)
            wrapped(surface, body, (x + 7, y + 31, w - 14, room * 10), 9, PALETTE["white"], 10, room)
            if frame % 50 < 34:
                text(surface, "ENTER: CONTINUE", (x + w - 7, y + h - 12), 9, PALETTE["cream"], align="right")
            del lines

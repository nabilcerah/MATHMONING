"""Agent 4 - AI Tutor (GDD 14).

* Progressive hints: a nudge, then a strategy, then the first step - never the answer.
* Contextual feedback on a wrong answer: if the answer matches a known misconception, say which
  idea went wrong and how to fix it; otherwise point back to the first step.
* Worked examples on DIFFERENT numbers, and a full explanation once the question is resolved.
* Language adapts to the learner: shorter for strong learners, smaller steps for strugglers.

Everything here works offline. When a live provider is configured, the orchestrator may replace
an explanation with an LLM one, but only after it passes ai.schemas.validate_tutor.
"""
from ai.agent_base import Agent
from ai.schemas import TutorResponse, validate_tutor
from mathematics.answer_validator import parse_number
from mathematics.explanations import gentle_feedback
from mathematics.question_templates import MISCONCEPTIONS

ENCOURAGEMENT = {
    "first_try": "Brilliant - right first time!",
    "after_hint": "Well done - you used the hint and got there!",
    "second_attempt": "You fixed it on the second try - that's real learning.",
    "failed": "That one was tricky. Mistakes are how we learn - let's look at it together.",
}


class TutorAgent(Agent):
    name = "tutor"

    def hint(self, question, level=0, analysis=None):
        hints = list(getattr(question, "hints", ()) or [getattr(question, "hint", "")])
        level = max(0, min(level, len(hints) - 1))
        text = hints[level]
        if analysis is not None and analysis.status == "weakness" and level == 0 and len(hints) > 1:
            text = f"{hints[0]} Then: {hints[1]}"   # a struggling learner gets the strategy straight away
        prefix = "Let's take it one step at a time. " if analysis is not None and analysis.status == "weakness" else ""
        try:
            return validate_tutor(TutorResponse("hint", prefix + text, level), question)
        except Exception:
            return TutorResponse("hint", "Break it into smaller steps and do one operation at a time.", level)

    def misconception_for(self, question, submitted):
        mapping = getattr(question, "misconceptions", {}) or {}
        if submitted in mapping:
            return mapping[submitted]
        value = parse_number(submitted)
        if value is None:
            return ""
        for wrong, tag in mapping.items():
            if parse_number(wrong) == value:
                return tag
        return ""

    def feedback(self, question, submitted, analysis=None):
        """After a wrong first attempt: name the likely misconception without giving the answer."""
        tag = self.misconception_for(question, str(submitted).strip())
        if tag in MISCONCEPTIONS:
            label, advice = MISCONCEPTIONS[tag]
            text = f"Not quite - it looks like a slip with {label}. {advice}"
        else:
            first = (getattr(question, "hints", None) or [getattr(question, "hint", "")])[0]
            text = f"Not quite. Check your first step: {first}"
        if analysis is not None and analysis.status == "weakness":
            text += " Take your time - you have one more try."
        response = TutorResponse("feedback", text, 0)
        try:
            return validate_tutor(response, question)
        except Exception:
            return TutorResponse("feedback", "Not quite. Read the question again and try one more time.", 0)

    def worked_example(self, example):
        steps = " ".join(example["steps"])
        text = f"Here's one like it: {example['prompt']} {steps}"
        return validate_tutor(TutorResponse("worked_example", text[:400]))

    def explain(self, question, outcome="failed", analysis=None):
        """Shown once the question is resolved, so the full solution is allowed here."""
        explanation = getattr(question, "explanation", "")
        opener = ENCOURAGEMENT.get(outcome, "")
        if analysis is not None and analysis.status in ("strong", "mastered") and outcome != "failed":
            text = opener
        else:
            text = f"{opener} {explanation}".strip()
        return validate_tutor(TutorResponse("explanation", text[:400]))

    def encourage(self, outcome):
        return validate_tutor(TutorResponse("encouragement", ENCOURAGEMENT.get(outcome, "Keep going!")))

    # Pre-GDD interface (Arena / older screens).
    EXAMPLES = {
        "addition": "For example, 8 + 5: make 10 by moving 2 from the 5, then add the 3 left over.",
        "subtraction": "For example, 15 − 7: count up from 7 to 15; the distance is the difference.",
        "multiplication": "For example, 6 × 4: split 6 into 5 + 1, then add 5 × 4 and 1 × 4.",
        "division": "For example, 24 ÷ 6: ask how many groups of 6 make 24.",
        "algebra": "For example, 2x + 3 = 11: subtract 3 on both sides, then divide both sides by 2.",
    }

    def mentor(self, question, profile=None):
        example = self.EXAMPLES.get(question.topic, "Try undoing one operation at a time and keep both sides balanced.")
        return f"Here is a similar example: {example} Now spot the pattern in your question: {question.hint} You can do this!"

    def legacy_feedback(self, question, correct):
        return gentle_feedback(question, correct)

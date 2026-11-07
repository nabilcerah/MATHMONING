"""Reusable offline tutor language."""


def gentle_feedback(question, correct):
    if correct:
        return f"Nice thinking! {question.explanation}"
    return f"Good try. {question.hint} Let's use that idea for another one."

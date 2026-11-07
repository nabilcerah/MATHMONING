"""Patient tutor responses with a hint-first offline path."""
from mathematics.explanations import gentle_feedback


class TutorAgent:
    EXAMPLES = {
        "addition": "For example, 8 + 5: make 10 by moving 2 from the 5, then add the 3 left over.",
        "subtraction": "For example, 15 − 7: count up from 7 to 15; the distance is the difference.",
        "multiplication": "For example, 6 × 4: split 6 into 5 + 1, then add 5 × 4 and 1 × 4.",
        "division": "For example, 24 ÷ 6: ask how many groups of 6 make 24.",
        "algebra": "For example, 2x + 3 = 11: subtract 3 on both sides, then divide both sides by 2.",
    }

    def hint(self, question):
        return f"Hint: {question.hint}"

    def explain(self, question, submitted=None):
        prefix = "That's a useful attempt. " if submitted is not None else "Let's look at the idea. "
        return prefix + question.explanation

    def feedback(self, question, correct):
        return gentle_feedback(question, correct)

    def mentor(self, question, profile=None):
        profile = profile or {}
        topic = profile.get(question.topic, {})
        example = self.EXAMPLES.get(question.topic, "Try undoing one operation at a time and keep both sides balanced.")
        if topic.get("recent_accuracy", 0) < 0.5 and topic.get("attempted", 0) >= 3:
            return f"We can take this one step at a time. {example} Now try the same idea here: {question.hint}"
        return f"Here is a similar example: {example} Now spot the pattern in your question: {question.hint} You can do this!"

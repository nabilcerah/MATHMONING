"""Evidence-based difficulty changes; one success never raises difficulty."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DifficultyDecision:
    level: str
    reason: str


class DifficultyManager:
    LEVELS = ("easy", "intermediate", "advanced")

    def choose(self, performance=None, fallback="easy"):
        performance = performance or {}
        current = performance.get("last_difficulty", fallback)
        if current not in self.LEVELS:
            current = "easy"
        index = self.LEVELS.index(current)
        attempted = performance.get("attempted", 0)
        recent = performance.get("recent_accuracy", performance.get("accuracy", 0.5))
        overall = performance.get("accuracy", recent)
        mastery = performance.get("mastery", 0)
        if attempted >= 3 and (recent < 0.45 or overall < 0.4):
            index = max(0, index - 1)
            reason = "Recent practice suggests a gentler step will help."
        elif attempted >= 8 and recent >= 0.8 and overall >= 0.72 and mastery >= 65:
            index = min(len(self.LEVELS) - 1, index + 1)
            reason = "Consistent accuracy shows readiness for a bigger challenge."
        else:
            reason = "Keeping the challenge steady while we build a reliable pattern."
        return DifficultyDecision(self.LEVELS[index], reason)

"""Structured agent outputs (GDD 14) and their validators (GDD 17: 'validate every structured
agent response'). An invalid result raises SchemaError; the orchestrator then falls back to the
deterministic offline path, so a malformed response can never reach the game engine."""
from dataclasses import asdict, dataclass, field

from mathematics.curriculum import DIFFICULTIES

ANALYSIS_STATUSES = ("insufficient_evidence", "weakness", "developing", "strong", "mastered")
TUTOR_KINDS = ("hint", "feedback", "explanation", "worked_example", "encouragement")
MAX_TUTOR_TEXT = 420
# Words a tutor message must never contain (GDD 17.9: no insulting or age-inappropriate replies).
BLOCKED_WORDS = ("stupid", "dumb", "idiot", "lazy", "useless", "pathetic", "hate", "shut up", "loser", "failure")


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class AnalysisResult:
    topic: str
    status: str
    evidence_count: int
    mastery_score: int
    recent_accuracy: float
    hint_rate: float
    identified_weakness: str = ""      # misconception tag, e.g. "isolating_variables"
    weakness_label: str = ""
    recommendation: str = ""           # e.g. "guided_linear_equations"
    summary: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class DifficultyDecision:
    level: str
    reason: str
    previous: str = ""


@dataclass(frozen=True)
class TutorResponse:
    kind: str
    text: str
    level: int = 0
    source: str = "offline"


@dataclass(frozen=True)
class QuestRecommendation:
    quest_id: str
    title: str
    reason: str
    topics: tuple = ()
    priority: int = 0


@dataclass
class OrchestratorDecision:
    event: str
    objective: str
    agents: list = field(default_factory=list)
    trace: list = field(default_factory=list)       # human-readable record of each workflow step
    question: object = None
    difficulty: DifficultyDecision = None
    analysis: AnalysisResult = None
    tutor: TutorResponse = None
    recommendation: QuestRecommendation = None
    message: str = ""
    decision_id: int = None
    extra: dict = field(default_factory=dict)

    def step(self, text):
        self.trace.append(text)

    def summary(self):
        data = {"event": self.event, "objective": self.objective, "agents": self.agents, "trace": self.trace,
                "message": self.message}
        if self.question is not None:
            data["question"] = self.question.to_dict() if hasattr(self.question, "to_dict") else str(self.question)
        if self.difficulty:
            data["difficulty"] = asdict(self.difficulty)
        if self.analysis:
            data["analysis"] = self.analysis.to_dict()
        if self.recommendation:
            data["recommendation"] = asdict(self.recommendation)
        if self.tutor:
            data["tutor"] = asdict(self.tutor)
        return data


# ------------------------------------------------------------------------------- validators
def validate_analysis(result):
    if not isinstance(result, AnalysisResult):
        raise SchemaError("analysis must be an AnalysisResult")
    if result.status not in ANALYSIS_STATUSES:
        raise SchemaError(f"unknown analysis status {result.status!r}")
    if not 0 <= result.mastery_score <= 100 or result.evidence_count < 0:
        raise SchemaError("mastery must be 0-100 and evidence non-negative")
    if not 0 <= result.recent_accuracy <= 1 or not 0 <= result.hint_rate <= 1:
        raise SchemaError("rates must be between 0 and 1")
    return result


def validate_difficulty(decision):
    if not isinstance(decision, DifficultyDecision) or decision.level not in DIFFICULTIES:
        raise SchemaError(f"invalid difficulty decision {decision!r}")
    return decision


def validate_question(question):
    """Structure AND truth: the stored answer must pass the independent validator."""
    for name in ("question_id", "topic", "difficulty", "prompt", "answer", "answer_type"):
        if not getattr(question, name, ""):
            raise SchemaError(f"question is missing {name}")
    if question.difficulty not in DIFFICULTIES:
        raise SchemaError("question difficulty out of range")
    if not question.check(question.answer).correct:
        raise SchemaError("question answer failed independent validation")
    if hasattr(question, "verified") and not question.verified():
        raise SchemaError("question answer is not proven by the mathematics engine")
    return question


def safe_text(text):
    text = " ".join(str(text or "").split())
    lowered = text.lower()
    return bool(text) and len(text) <= MAX_TUTOR_TEXT and not any(word in lowered for word in BLOCKED_WORDS)


def reveals(text, answer):
    """True if ``text`` states ``answer`` as a standalone value (hints must not)."""
    import re
    answer = str(answer).strip()
    if not answer:
        return False
    return re.search(rf"(?<![\w./:]){re.escape(answer)}(?![\w/:]|\.\d)", str(text)) is not None


def validate_tutor(response, question=None):
    if not isinstance(response, TutorResponse) or response.kind not in TUTOR_KINDS:
        raise SchemaError("invalid tutor response")
    if not safe_text(response.text):
        raise SchemaError("tutor text failed the safety/length check")
    if response.kind in ("hint", "feedback") and question is not None and reveals(response.text, question.answer)             and not reveals(getattr(question, "prompt", ""), question.answer):
        raise SchemaError("a hint must not reveal the answer")
    return response


def validate_recommendation(recommendation, known_quests):
    if recommendation is None:
        return None
    if not isinstance(recommendation, QuestRecommendation):
        raise SchemaError("invalid recommendation")
    if recommendation.quest_id and recommendation.quest_id not in known_quests:
        raise SchemaError(f"recommended an unknown quest {recommendation.quest_id!r}")
    if not safe_text(recommendation.reason):
        raise SchemaError("recommendation text failed the safety check")
    return recommendation

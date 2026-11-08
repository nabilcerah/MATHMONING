"""GDD 9.4: mastery is the average learning score of the last 20 assessed questions in a topic.

    Learning scores: 1.0 unaided, 0.75 after a hint, 0.5 after a worked example, 0 when wrong.
    Mastery = average x 100.

Bands: Foundation 0-39, Developing 40-69, Proficient 70-84, Mastered 85-100 - but "Mastered" needs
at least 10 assessed questions, and a topic with too little evidence is reported as such rather
than as weak (GDD: insufficient evidence must be shown separately from low mastery).
"""
from dataclasses import dataclass

from monsters.monster_data import rules

# Below this many assessed questions a score is shown, but labelled as still gathering evidence.
MIN_EVIDENCE_FOR_BAND = 5


@dataclass(frozen=True)
class MasteryStatus:
    score: int
    evidence: int
    band: str           # Foundation / Developing / Proficient / Mastered / Not started / Gathering evidence
    sufficient: bool    # enough evidence to treat the band as real

    @property
    def label(self):
        if self.evidence == 0:
            return "Not started"
        if not self.sufficient:
            return f"Gathering evidence ({self.evidence}/{MIN_EVIDENCE_FOR_BAND})"
        return self.band


def window():
    return int(rules()["mastery"]["window"])


def mastery_score(learning_scores):
    """Average of the most recent ``window`` scores, as 0-100."""
    recent = list(learning_scores)[-window():]
    if not recent:
        return 0
    return round(sum(recent) / len(recent) * 100)


def band_for(score, evidence):
    cfg = rules()["mastery"]
    band = cfg["bands"][0][1]
    for threshold, name in cfg["bands"]:
        if score >= threshold:
            band = name
    if band == "Mastered" and evidence < cfg["mastered_min_evidence"]:
        band = "Proficient"
    return band


def status(score, evidence):
    if evidence == 0:
        return MasteryStatus(0, 0, "Not started", False)
    return MasteryStatus(score, evidence, band_for(score, evidence), evidence >= MIN_EVIDENCE_FOR_BAND)

"""Agent 2 - Learning Analyst (GDD 14).

Reads the stored question history and learning profile and turns them into an AnalysisResult:
mastery and confidence, recent accuracy, hint use, and any REPEATED misconception (the same
tagged wrong answer at least twice). With too little evidence it says so instead of calling the
topic weak.
"""
from collections import Counter

from ai.agent_base import Agent
from ai.schemas import AnalysisResult, validate_analysis
from mathematics import curriculum, mastery_manager
from mathematics.question_templates import MISCONCEPTIONS

# Remediation plan codes per topic (used by the Game Master and shown in the AI log).
GUIDED = {"algebra": "guided_linear_equations", "fractions": "guided_fractions", "ratios": "guided_ratios",
          "geometry": "guided_area_and_angles", "integers": "guided_negative_numbers",
          "sequences": "guided_patterns", "addition": "guided_addition", "subtraction": "guided_subtraction",
          "multiplication": "guided_times_tables", "division": "guided_division"}
WEAK_MASTERY = 40          # below this (with enough evidence) a topic is a demonstrated weakness
WEAK_RECENT = 0.4          # or: recent accuracy below this over the last few questions


class LearningAnalyst(Agent):
    name = "learning_analyst"

    def __init__(self, repository):
        self.repository = repository

    def analyse(self, player_id, topic):
        topic = curriculum.mastery_topic(topic)
        profile = self.repository.learning_profile(player_id).get(topic, {})
        history = self.repository.question_history(player_id, topic, limit=12)
        evidence = int(profile.get("evidence", 0))
        mastery = int(profile.get("mastery", 0))
        recent = history[:8]
        recent_accuracy = sum(row["correct"] for row in recent) / len(recent) if recent else 0.0
        hint_rate = sum(row["used_hint"] for row in recent) / len(recent) if recent else 0.0
        mistakes = Counter(row["misconception"] for row in history[:10] if not row["correct"] and row["misconception"])
        # Two-attempt questions log a misconception even when the second try was right.
        mistakes.update(row["misconception"] for row in history[:10] if row["correct"] and row["misconception"])
        weakness, count = (mistakes.most_common(1)[0] if mistakes else ("", 0))
        if count < 2:
            weakness = ""   # one slip is not a pattern
        label = MISCONCEPTIONS.get(weakness, ("", ""))[0]
        name = curriculum.label(topic)
        if evidence < mastery_manager.MIN_EVIDENCE_FOR_BAND:
            status = "insufficient_evidence"
            summary = f"Only {evidence} {name} question(s) so far - not enough to judge yet."
        elif mastery < WEAK_MASTERY or (len(recent) >= 4 and recent_accuracy < WEAK_RECENT):
            status = "weakness"
            summary = f"{name} is a current weakness (mastery {mastery}, {round(recent_accuracy * 100)}% recently)."
        elif mastery >= 85 and evidence >= 10:
            status = "mastered"
            summary = f"{name} is mastered (mastery {mastery} over {evidence} questions)."
        elif mastery >= 70:
            status = "strong"
            summary = f"{name} is proficient (mastery {mastery})."
        else:
            status = "developing"
            summary = f"{name} is developing (mastery {mastery})."
        if weakness:
            summary += f" Repeated mistake: {label}."
        recommendation = GUIDED.get(topic, "") if status == "weakness" or weakness else ""
        return validate_analysis(AnalysisResult(topic, status, evidence, mastery, round(recent_accuracy, 3),
                                                round(hint_rate, 3), weakness, label, recommendation, summary))

    def overview(self, player_id, topics=None):
        """Strongest and developing topics for the profile screen."""
        profile = self.repository.learning_profile(player_id)
        topics = topics or curriculum.MASTERY_TOPICS
        known = [(t, profile[t]) for t in topics if t in profile and profile[t]["sufficient"]]
        strongest = [t for t, s in sorted(known, key=lambda item: -item[1]["mastery"]) if s["mastery"] >= 70][:3]
        developing = [t for t, s in sorted(known, key=lambda item: item[1]["mastery"]) if s["mastery"] < 70][:3]
        untested = [t for t in topics if t not in profile or not profile[t]["sufficient"]]
        return {"strongest": strongest, "developing": developing, "untested": untested}

    def weakest(self, player_id, topics):
        """The topic most in need of practice among ``topics`` (weakness first, then least evidence)."""
        results = [self.analyse(player_id, topic) for topic in topics]
        order = {"weakness": 0, "insufficient_evidence": 1, "developing": 2, "strong": 3, "mastered": 4}
        return min(results, key=lambda r: (order[r.status], r.mastery_score, r.evidence_count))

"""Deterministic maths question engine for the advanced monster battles.

Every answer is computed by the generator and then re-proved (exact Fraction arithmetic or a
substitution check) before a question is shown. No LLM is involved in creating or marking answers.
"""
from mathematics.question_engine.engine import (GENERATORS, LABELS, TOPICS, GenerationError, QuestionEngine,
                                                canonical_topic, topic_label, verify_draft)
from mathematics.question_engine.model import LEVEL_NAMES, Question, fmt, parse_number

__all__ = ["GENERATORS", "LABELS", "TOPICS", "GenerationError", "QuestionEngine", "Question", "canonical_topic",
           "topic_label", "verify_draft", "LEVEL_NAMES", "fmt", "parse_number"]

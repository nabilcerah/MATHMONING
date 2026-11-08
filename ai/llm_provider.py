"""GDD 16, Modes B and C: an optional Anthropic-backed tutor voice.

* Requests run on a worker thread (never on the game loop) with a 12 s timeout and no retries.
* Only the maths question, the learner's answer and the verified solution are sent - never the
  player's name or any other personal data (GDD 17.7-17.8).
* The model never decides anything mechanical: its text is a tutor explanation that the
  orchestrator validates (ai.schemas.validate_tutor) before showing; on any failure the offline
  text is used instead.

Mode is chosen with MATHMON_AI_MODE = offline | live | hybrid (default hybrid). Live and hybrid
both need ANTHROPIC_API_KEY; without it the game silently behaves as offline.
"""
import os
import re
from concurrent.futures import Future

from config import ANTHROPIC_MODEL, ROOT, WEB

MODES = ("offline", "live", "hybrid")


def _done(value):
    """An already-finished future: no thread needed (the browser build has no threads)."""
    future = Future()
    future.set_result(value)
    return future


class LLMProvider:
    TIMEOUT = 12.0

    def __init__(self):
        self._executor = None
        if WEB:
            # Never ship an API key inside a public web page; the offline tutor is used instead.
            self.api_key, self.model, self.mode = "", "", "offline"
            return
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
        except ImportError:
            pass
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.model = os.getenv("ANTHROPIC_MODEL", ANTHROPIC_MODEL)
        mode = os.getenv("MATHMON_AI_MODE", "hybrid").strip().lower()
        self.mode = mode if mode in MODES else "hybrid"

    @property
    def available(self):
        return bool(self.api_key) and self.mode != "offline"

    @property
    def label(self):
        if not self.available:
            return "OFFLINE AI"
        return "LIVE AI TUTOR" if self.mode == "live" else "HYBRID AI"

    @property
    def executor(self):
        if self._executor is None:
            from concurrent.futures import ThreadPoolExecutor
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mathmon-tutor")
        return self._executor

    def _client(self):
        from anthropic import Anthropic
        return Anthropic(api_key=self.api_key, timeout=self.TIMEOUT, max_retries=0)

    @staticmethod
    def _text(response):
        return " ".join(block.text for block in response.content if getattr(block, "type", "") == "text")

    # ------------------------------------------------------------------ tutor explanation
    def explain_async(self, question, submitted, offline_fallback):
        """A short explanation after the question is resolved. Resolves to text (fallback on error)."""
        if not self.available:
            return _done(offline_fallback)
        return self.executor.submit(self._request, question, submitted, offline_fallback)

    def _request(self, question, submitted, fallback):
        try:
            response = self._client().messages.create(
                model=self.model, max_tokens=180,
                system=("You are a warm, patient maths tutor for a secondary-school learner (age 12-17) inside a "
                        "monster-collecting game. In at most 3 short sentences, explain the method for the problem, "
                        "pointing at the step where the learner's answer likely went wrong. Never shame the learner. "
                        "Use the verified solution only to check your reasoning."),
                messages=[{"role": "user", "content": f"Problem: {question.prompt}\nLearner's answer: {submitted}\n"
                                                      f"Verified answer: {question.answer}\n"
                                                      f"Verified method: {question.explanation}"}],
            )
            text = " ".join(self._text(response).split())[:400]
            return text or fallback
        except Exception:
            return fallback

    # ------------------------------------------------------------------ worked steps
    def solve_async(self, question, offline_steps):
        """Worked steps for a question the learner could not finish (the answer IS revealed here)."""
        if not self.available:
            return _done(offline_steps)
        return self.executor.submit(self._solve, question, offline_steps)

    def _solve(self, question, fallback):
        try:
            response = self._client().messages.create(
                model=self.model, max_tokens=300,
                system=("You are a warm maths tutor. Solve the question in 3 or 4 very short steps (one line each, "
                        "under 18 words). The last step must state the final answer. Output only the steps."),
                messages=[{"role": "user", "content": f"Question: {question.prompt}\nVerified answer: {question.answer}"}],
            )
            steps = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
                     for line in self._text(response).splitlines() if line.strip()]
            steps = [s[:120] for s in steps if s][:5]
            # Only trust the model's steps if they reach the verified answer.
            if steps and question.answer in steps[-1]:
                return steps
            return fallback
        except Exception:
            return fallback

    def close(self):
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

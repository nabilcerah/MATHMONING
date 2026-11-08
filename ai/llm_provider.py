"""Optional asynchronous Anthropic provider with offline-safe fallback."""
import os
import re
from concurrent.futures import Future

from config import ROOT, WEB


def _done(value):
    """An already-finished future: no thread needed (the browser build has no threads)."""
    future = Future()
    future.set_result(value)
    return future


class LLMProvider:
    def __init__(self):
        self._executor = None
        if WEB:
            # Never ship an API key inside a public web page; the offline tutor is used instead.
            self.api_key, self.model = "", ""
            return
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
        except ImportError:
            pass
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    @property
    def available(self):
        return bool(self.api_key)

    @property
    def executor(self):
        if self._executor is None:
            from concurrent.futures import ThreadPoolExecutor
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mathmon-tutor")
        return self._executor

    def explain_async(self, question, submitted, offline_fallback):
        if not self.available:
            return _done(offline_fallback)
        return self.executor.submit(self._request, question, submitted, offline_fallback)

    def _request(self, question, submitted, fallback):
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key, timeout=12.0, max_retries=0)
            response = client.messages.create(
                model=self.model, max_tokens=180,
                system="You are a patient maths tutor for a secondary-school learner. Give a hint, then one analogous worked example, and ask what the learner would try next. Do not state the answer to the supplied problem. Never shame the learner. The verified solution is for checking your reasoning only.",
                messages=[{"role": "user", "content": f"Problem: {question.prompt}\nStudent answer: {submitted}\nVerified answer (do not reveal): {question.answer}\nVerified explanation (for checking only): {question.explanation}\nGive a brief, encouraging hint and analogous example."}],
            )
            text = " ".join(block.text for block in response.content if getattr(block, "type", "") == "text")
            text = " ".join(text.split())[:700]
            return text or fallback
        except Exception:
            return fallback

    def solve_async(self, question, offline_steps):
        """Worked steps for a question the learner could not finish (the answer IS revealed here).

        Resolves to a list of short steps; falls back to ``offline_steps`` without a key or on error.
        """
        if not self.available:
            return _done(offline_steps)
        return self.executor.submit(self._solve, question, offline_steps)

    def _solve(self, question, fallback):
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key, timeout=12.0, max_retries=0)
            response = client.messages.create(
                model=self.model, max_tokens=300,
                system=("You are a warm maths tutor for a child aged 8-12 who tried a question three times. "
                        "Solve it with them in 3 or 4 very short steps (one line each, under 18 words), "
                        "using friendly strategies like splitting into tens and ones. The last step must state "
                        "the final answer. Output only the steps, one per line, with no numbering or extra text."),
                messages=[{"role": "user", "content": f"Question: {question.prompt}\nVerified answer: {question.answer}"}],
            )
            text = "\n".join(block.text for block in response.content if getattr(block, "type", "") == "text")
            # Drop only a *leading* bullet or "1." / "2)" marker; the answer at the end must survive.
            steps = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip() for line in text.splitlines() if line.strip()]
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

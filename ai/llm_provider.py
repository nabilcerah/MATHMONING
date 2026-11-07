"""Optional asynchronous Anthropic provider with offline-safe fallback."""
import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from config import ROOT


class LLMProvider:
    def __init__(self):
        load_dotenv(ROOT / ".env")
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mathmon-tutor")

    @property
    def available(self):
        return bool(self.api_key)

    def explain_async(self, question, submitted, offline_fallback):
        if not self.available:
            future = self.executor.submit(lambda: offline_fallback)
            return future
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

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)

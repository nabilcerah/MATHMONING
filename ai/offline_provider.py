"""GDD 16, Mode A: the offline provider. It answers every request the live provider can, using
the deterministic tutor text, so the game behaves identically without a network or API key."""
from concurrent.futures import Future


def done(value):
    future = Future()
    future.set_result(value)
    return future


class OfflineProvider:
    available = False
    mode = "offline"

    def explain_async(self, question, submitted, offline_fallback):
        return done(offline_fallback)

    def solve_async(self, question, offline_steps):
        return done(offline_steps)

    def close(self):
        pass

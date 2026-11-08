"""GDD 22: the central State Manager.

One main loop (game_manager.GameManager.run_async) owns events, updates, rendering and frame
timing. The State Manager decides which state receives them. Full-screen states (menu, overworld,
battle) are named; overlay screens (trainer menu, party, sanctuary, bag, shop, quests, profile,
evolution, puzzle challenges, pause) are pushed on a stack above the current state and receive
input until they close. There is never a second pygame loop.
"""

STATES = ("menu", "confirm_new", "name", "avatar", "starter", "overworld", "battle", "profile", "settings",
          "worldmap", "puzzle", "arena", "trials", "mbattle", "recovery")


class StateManager:
    def __init__(self, initial="menu"):
        self.state = initial
        self.stack = []          # overlay screens, top = last
        self.history = [initial]

    def change(self, state):
        if state not in STATES:
            raise ValueError(f"unknown state {state!r}")
        self.state = state
        self.history.append(state)
        self.history = self.history[-20:]

    @property
    def overlay(self):
        return self.stack[-1] if self.stack else None

    def push(self, screen, on_close=None):
        screen._on_close = on_close
        self.stack.append(screen)
        return screen

    def clear(self):
        self.stack.clear()

    def handle_event(self, event):
        """Give ``event`` to the top overlay. Returns True if an overlay consumed it."""
        screen = self.overlay
        if screen is None:
            return False
        screen.handle_event(event)
        self._pop_closed()
        return True

    def update(self):
        screen = self.overlay
        if screen is None:
            return False
        screen.update()
        self._pop_closed()
        return True

    def covers_base(self):
        """True when an opaque overlay hides the full-screen state underneath."""
        return any(screen.opaque for screen in self.stack)

    def draw(self, surface, frame):
        """Draw from the top-most opaque overlay upwards (lower screens are hidden anyway)."""
        start = 0
        for index, screen in enumerate(self.stack):
            if screen.opaque:
                start = index
        if self.stack and self.stack[start].opaque:
            from game import ui
            ui.begin_frame()   # discard text queued by whatever is underneath
        for screen in self.stack[start:]:
            screen.draw(surface, frame)

    def _pop_closed(self):
        while self.stack and self.stack[-1].closed:
            screen = self.stack.pop()
            callback = getattr(screen, "_on_close", None)
            if callback:
                callback(screen)

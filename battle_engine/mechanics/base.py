"""The plug-in interface every battle mechanic implements.

A monster's JSON lists its mechanics, e.g. ``{"type": "shield", "hp_ratio": 0.3}``; the engine
creates one object per entry and calls these hooks at fixed points of the turn. Hooks have safe
defaults, so a mechanic only overrides what it changes.
"""


class Mechanic:
    TYPE = ""
    EFFECTS = ()          # ability "effect" ids this mechanic performs (raise_shield, split...)

    def __init__(self, engine, params):
        self.engine = engine
        self.params = params
        self.active = bool(params.get("active", True))

    def p(self, key, default):
        return self.params.get(key, default)

    @property
    def name(self):
        return self.engine.defn.name

    # -- battle start / phases ------------------------------------------------
    def setup(self):
        return []

    def on_phase(self, phase):
        return []

    # -- questions --------------------------------------------------------------
    def question_request(self):
        """Return a QuestionRequest to take over the next question, or None."""
        return None

    def forces_question(self):
        """True when question_request() will take over the next question (no topic choice)."""
        return False

    def question_level_offset(self):
        return 0

    def choice_count(self, count):
        return count

    def typed_only(self):
        return False

    # -- the player's hit ---------------------------------------------------------
    def modify_hit(self, hit, question, correct, request, elapsed):
        """Adjust multipliers/defence before the hit is resolved."""

    def absorb(self, hit, question, correct, request):
        """After resolution: move damage from HP into shields/barriers. Return events."""
        return []

    def after_answer(self, question, correct, hit, request, forgiven):
        return []

    # -- the monster's turn ---------------------------------------------------------
    def ai_options(self):
        """Extra Decisions the AI may take this turn."""
        return []

    def ability_score(self, ability):
        """Score for an ability whose effect this mechanic owns (None = not usable now)."""
        return None

    def perform(self, effect, ability):
        return []

    def before_monster_turn(self):
        """Return (events, consumed). consumed=True replaces the monster's normal action."""
        return [], False

    def modify_monster_hit(self, hit, ability):
        """Adjust an attack on the player (append to hit.extras)."""

    def end_round(self):
        return []

    # -- UI -------------------------------------------------------------------------
    def badges(self):
        return []

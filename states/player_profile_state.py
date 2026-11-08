"""PLAYER PROFILE (GDD 26): topic mastery, totals, learning history, strongest and developing
topics, AI recommendations and the AI decision log. LEFT/RIGHT flips between the three pages."""
from config import PALETTE
from game.ui import meter, panel, text, wrapped
from mathematics import curriculum
from mathematics.mastery_manager import MIN_EVIDENCE_FOR_BAND
from states.base import LEFT, RIGHT, Screen

PAGES = ("MASTERY", "HISTORY", "AI LOG")


class ProfileScreen(Screen):
    def __init__(self, game):
        super().__init__(game)
        self.page = 0
        self.profile = self.repo.learning_profile(self.player_id)
        self.summary = self.repo.history_summary(self.player_id)
        self.history = self.repo.question_history(self.player_id, limit=9)
        self.overview = game.orchestrator.analyst.overview(self.player_id)
        decision = game.orchestrator.recommendations(self.player_id, game.party_level(), game.seals_done())
        self.advice = decision.message
        self.objectives = decision.extra.get("objectives", [])
        self.boss_advice = decision.extra.get("boss_advice", "")
        # Agent 6: when a live AI provider is set up, Claude plans in the background (tool calls).
        self.plan_future = game.orchestrator.start_planning(self.player_id, game.party_level(), game.seals_done())
        self.planner_status = "thinking..." if game.orchestrator.planner.available else "off (rules only)"
        self._load_decisions()

    def _load_decisions(self):
        decisions, seen = [], set()
        for row in self.repo.recent_decisions(self.player_id, 30):
            if row["event"] in seen and row["event"] in ("recommend", "battle_end"):
                continue   # one of each routine entry; every question/answer decision is shown
            seen.add(row["event"])
            decisions.append(row)
        self.decisions = decisions[:6]

    def update(self):
        super().update()
        if self.plan_future is None or not self.plan_future.done():
            return
        plan, self.plan_future = self.plan_future.result(), None
        if plan is None:
            self.planner_status = "no plan (using the rules)"
            return
        decision = self.game.orchestrator.apply_plan(self.player_id, plan)
        self.advice = decision.message
        self.objectives = plan.objectives or self.objectives
        self.planner_status = f"plan ready - focus {curriculum.label(plan.focus_topic)} ({len(plan.tool_calls)} tool calls)"
        self._load_decisions()

    def items(self):
        return []

    def handle_key(self, key, unicode=""):
        if key in LEFT:
            self.page = (self.page - 1) % len(PAGES)
        elif key in RIGHT:
            self.page = (self.page + 1) % len(PAGES)
        else:
            super().handle_key(key, unicode)

    def draw(self, surface, frame=0):
        name = self.game.player.name
        self.draw_frame(surface, f"{name.upper()}'S LEARNING PROFILE",
                        footer="LEFT/RIGHT: " + " / ".join(PAGES) + "   ESC: BACK")
        for i, label in enumerate(PAGES):
            text(surface, label, (40 + i * 120, 30), 9, PALETTE["gold"] if i == self.page else PALETTE["muted"], center=True)
        [self._mastery, self._history, self._ai_log][self.page](surface)

    def _mastery(self, surface):
        accuracy = round(self.summary["accuracy"] * 100)
        text(surface, f"Questions: {self.summary['attempted']}   Correct: {self.summary['correct']} ({accuracy}%)"
                      f"   Hints used: {self.summary['hints']}", (8, 40), 9, PALETTE["white"])
        for index, topic in enumerate(curriculum.MASTERY_TOPICS):
            x = 6 + (index % 2) * 157
            y = 54 + (index // 2) * 22
            stats = self.profile.get(topic)
            panel(surface, (x, y, 151, 19), PALETTE["night"])
            text(surface, curriculum.label(topic), (x + 5, y + 3), 9, PALETTE["cream"])
            if not stats:
                text(surface, "not started", (x + 146, y + 3), 8, PALETTE["muted"], align="right")
                continue
            sufficient = stats["evidence"] >= MIN_EVIDENCE_FOR_BAND
            label = stats["band"] if sufficient else f"needs evidence {stats['evidence']}/{MIN_EVIDENCE_FOR_BAND}"
            text(surface, f"{stats['mastery']}  {label}", (x + 146, y + 3), 8,
                 PALETTE["gold"] if sufficient else PALETTE["muted"], align="right")
            meter(surface, x + 5, y + 13, 141, 4, stats["mastery"], 100,
                  PALETTE["mint"] if sufficient else PALETTE["muted"])
        strongest = ", ".join(curriculum.label(t) for t in self.overview["strongest"]) or "- (keep practising)"
        developing = ", ".join(curriculum.label(t) for t in self.overview["developing"]) or "-"
        text(surface, f"STRONGEST: {strongest}", (8, 166), 9, PALETTE["mint"])
        text(surface, f"DEVELOPING: {developing}", (8, 177), 9, PALETTE["coral"])
        panel(surface, (4, 188, 312, 32), PALETTE["night"], PALETTE["sky"])
        wrapped(surface, "AI: " + self.advice, (10, 192, 300, 24), 9, PALETTE["white"], 10, 2)

    def _history(self, surface):
        text(surface, "RECENT QUESTIONS", (8, 40), 9, PALETTE["gold"])
        if not self.history:
            text(surface, "No questions answered yet.", (8, 54), 9, PALETTE["muted"])
        for i, row in enumerate(self.history):
            y = 52 + i * 13
            mark = "OK" if row["correct"] else "X"
            extras = (" hint" if row["used_hint"] else "") + (" 2nd" if row["attempts_used"] >= 2 else "")
            text(surface, mark, (8, y), 9, PALETTE["mint"] if row["correct"] else PALETTE["coral"])
            text(surface, f"{row['prompt'][:42]}", (24, y), 8, PALETTE["white"])
            text(surface, f"{curriculum.SHORT.get(row['topic'], '?')}{extras}", (314, y), 8, PALETTE["muted"], align="right")
        panel(surface, (4, 172, 312, 48), PALETTE["night"], PALETTE["gold"])
        text(surface, "LEARNING OBJECTIVES (AI GAME MASTER)", (10, 175), 8, PALETTE["gold"])
        for i, goal in enumerate(self.objectives[:3]):
            text(surface, f"- {goal}", (10, 186 + i * 10), 8, PALETTE["white"])

    def _ai_log(self, surface):
        text(surface, f"AI MODE: {self.game.llm.label}   AI PLANNER: {self.planner_status}", (8, 40), 8, PALETTE["sky"])
        y = 52
        if not self.decisions:
            text(surface, "The AI hasn't made any decisions yet - start a battle!", (8, y), 9, PALETTE["muted"])
        for row in self.decisions[:3]:
            decision = row["decision"]
            text(surface, f"#{row['decision_id']} {row['event']}: {row['objective'][:40]}", (8, y), 9, PALETTE["gold"])
            y += 11
            start = 1 if row["event"] == "agent_plan" else 2   # show the planner's first tool call
            for step in decision.get("trace", [])[start:start + 4]:
                used = wrapped(surface, step, (14, y, 296, 18), 8, PALETTE["white"], 9, 2)
                y += 9 * used
                if y > 176:
                    break
            y += 3
            if y > 176:
                break
        panel(surface, (4, 188, 312, 32), PALETTE["night"], PALETTE["sky"])
        wrapped(surface, "Boss check: " + self.boss_advice, (10, 192, 300, 24), 9, PALETTE["white"], 10, 2)

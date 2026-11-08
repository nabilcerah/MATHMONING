"""QUEST LOG (GDD 11): main, side and exploration quests with their current step, rewards and the
AI Game Master's recommendation (advice only - it never changes a quest)."""
from config import PALETTE
from game.ui import panel, text, wrapped
from monsters.monster_data import quests
from states.base import Screen

CATEGORY_COLORS = {"main": "gold", "side": "sky", "exploration": "mint"}


class QuestScreen(Screen):
    def __init__(self, game):
        super().__init__(game)
        manager = game.quests
        self.entries = manager.active() + manager.completed()
        recommendation = game.orchestrator.recommendations(self.player_id, game.party_level(), game.seals_done())
        self.advice = recommendation.message
        self.recommended = recommendation.recommendation.quest_id if recommendation.recommendation else ""

    def items(self):
        return self.entries

    def rows(self):
        return 34, 15, 4, 130

    def draw(self, surface, frame=0):
        self.draw_frame(surface, "QUEST LOG")
        manager = self.game.quests
        if not self.entries:
            text(surface, "No quests yet. Talk to people in Starter Village!", (10, 40), 10, PALETTE["muted"])
        labels = []
        for quest_id in self.entries:
            quest = quests()[quest_id]
            mark = "(done) " if manager.status(quest_id) == "completed" else ("* " if quest_id == self.recommended else "")
            labels.append(f"{mark}{quest['title'][:20]}")
        self.draw_list(surface, labels, frame, 34, 15, 4, 128)
        panel(surface, (4, 186, 312, 34), PALETTE["night"], PALETTE["sky"])
        text(surface, "AI GAME MASTER", (10, 189), 8, PALETTE["sky"])
        wrapped(surface, self.advice, (10, 199, 300, 20), 9, PALETTE["white"], 10, 2)
        if not self.entries:
            return
        quest_id = self.entries[min(self.selected, len(self.entries) - 1)]
        quest = quests()[quest_id]
        panel(surface, (138, 30, 178, 150), PALETTE["night"])
        color = PALETTE[CATEGORY_COLORS.get(quest["category"], "gold")]
        text(surface, quest["title"], (144, 34), 10, color)
        text(surface, quest["category"].upper() + " QUEST", (144, 46), 8, PALETTE["muted"])
        lines = wrapped(surface, quest["summary"], (144, 57, 166, 40), 8, PALETTE["white"], 9, 4)
        y = 60 + lines * 9
        step = manager.step_index(quest_id)
        completed = manager.status(quest_id) == "completed"
        for index, entry in enumerate(quest["steps"]):
            done = completed or index < step
            current = index == step and not completed
            if index > step and not completed:
                text(surface, "• ???", (146, y), 8, PALETTE["muted"])
            else:
                mark = "+" if done else ">"
                c = PALETTE["mint"] if done else (PALETTE["gold"] if current else PALETTE["muted"])
                used = wrapped(surface, f"{mark} {entry['text']}", (146, y, 162, 20), 8, c, 9, 2)
                y += (used - 1) * 9
            y += 10
            if y > 160:
                break
        rewards = quest.get("rewards", {})
        parts = ([f"{rewards['exp']} EXP"] if rewards.get("exp") else []) + \
                ([f"{rewards['coins']}c"] if rewards.get("coins") else []) + \
                [f"{k} x{v}" for k, v in rewards.get("items", {}).items()]
        wrapped(surface, "Reward: " + ", ".join(parts), (144, 166, 166, 14), 8, PALETTE["gold"], 9, 1)

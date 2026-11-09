"""GDD 11: deterministic quests. Steps advance only from game events and saved world flags;
rewards are fixed in data/quests.json and granted in one database transaction.

The AI Game Master may read ``available()``/``active()`` to RECOMMEND quests, but nothing it
returns can change a step, a requirement or a reward.
"""
from monsters.monster_data import challenges, quests


class QuestManager:
    def __init__(self, repository, player_id, flags=None):
        self.repository = repository
        self.player_id = player_id
        self._flags = flags   # callable returning the current set of world flags
        self.states = repository.quest_states(player_id)

    # ------------------------------------------------------------------ views
    def flags(self):
        return set(self._flags()) if self._flags else self.repository.world_flags(self.player_id)

    @staticmethod
    def definition(quest_id):
        return quests()[quest_id]

    def status(self, quest_id):
        return self.states.get(quest_id, {}).get("status", "not_started")

    def active(self):
        return [qid for qid in quests() if self.status(qid) == "active"]

    def completed(self):
        return [qid for qid in quests() if self.status(qid) == "completed"]

    def available(self):
        """Quests the player has not started yet (what the Game Master may recommend)."""
        return [qid for qid in quests() if self.status(qid) == "not_started"]

    def step_index(self, quest_id):
        return int(self.states.get(quest_id, {}).get("progress", {}).get("step", 0))

    def current_step(self, quest_id):
        steps = self.definition(quest_id)["steps"]
        index = self.step_index(quest_id)
        return steps[index] if index < len(steps) else None

    def step_text(self, quest_id):
        if self.status(quest_id) == "completed":
            return "Completed!"
        step = self.current_step(quest_id)
        if not step:
            return ""
        done, total = self.step_progress(quest_id)
        return f"{step['text']} ({done}/{total})" if total else step["text"]

    def step_progress(self, quest_id):
        """(done, total) for steps you complete bit by bit - battles, captures, chests, seals - else (0, 0)."""
        step = self.current_step(quest_id) or {}
        counters = self.states.get(quest_id, {}).get("progress", {}).get("counters", {})
        kind = step.get("type")
        if kind == "win_battles":
            return min(counters.get("wins", 0) + counters.get("captures", 0), step["count"]), step["count"]
        if kind == "capture":
            return min(counters.get("captures", 0), step["count"]), step["count"]
        if kind == "flags_all":
            flags = self.flags()
            return sum(1 for flag in step["flags"] if flag in flags), len(step["flags"])
        if kind == "open_chests":
            opened = sum(1 for flag in self.flags() if flag.startswith("opened:"))
            return min(opened, step["count"]), step["count"]
        return 0, 0

    @staticmethod
    def unlocked_by(flag):
        """The quest step that sets ``flag`` (e.g. a boss), as short text - for 'LOCKED: ...' prompts."""
        for quest in quests().values():
            for step in quest.get("steps", []):
                if step.get("type") == "flag" and step.get("flag") == flag:
                    return step["text"].split(" in ")[0].split(" at ")[0].rstrip(".")
            if flag in quest.get("rewards", {}).get("flags", []):
                return f"Finish {quest['title'].title()}"
        return ""

    def challenge(self, challenge_id):
        return challenges()[challenge_id]

    # ------------------------------------------------------------------ changes
    def start(self, quest_id):
        if self.status(quest_id) != "not_started":
            return []
        self._save(quest_id, "active", {"step": 0, "counters": {}})
        messages = [f"New quest: {self.definition(quest_id)['title']}"]
        return messages + self._advance(quest_id, None, {})

    def start_auto_quests(self):
        messages = []
        for quest_id, quest in quests().items():
            if quest.get("auto_start"):
                messages += self.start(quest_id)
        return messages

    def notify(self, event, **data):
        """Report a game event: talk(npc), battle_won, capture, visit(area), challenge(id), chest, flag.
        Returns (messages, completed_quest_ids)."""
        messages = []
        if event == "talk":
            for quest_id, quest in quests().items():
                if quest.get("giver") == data.get("npc") and self.status(quest_id) == "not_started":
                    messages += self.start(quest_id)
        if event == "interact":
            for quest_id, quest in quests().items():
                if quest.get("giver") == data.get("object") and self.status(quest_id) == "not_started":
                    messages += self.start(quest_id)
        for quest_id in self.active():
            messages += self._advance(quest_id, event, data)
        done = [qid for qid in quests() if self.states.get(qid, {}).get("just_completed")]
        for quest_id in done:
            self.states[quest_id].pop("just_completed", None)
        return messages, done

    def _step_met(self, step, event, data, counters, flags):
        kind = step["type"]
        if kind == "talk":
            if step.get("met_ok") and f"met:{step['npc']}" in flags:
                return True   # already met earlier, e.g. before the quest log existed
            return event == "talk" and data.get("npc") == step["npc"]
        if kind == "win_battles":
            # Catching a MathMon is winning that battle too (bug report: catches did not count). Saves made
            # before the fix already hold their catches here, so they count as soon as the game loads.
            return counters.get("wins", 0) + counters.get("captures", 0) >= step["count"]
        if kind == "capture":
            return counters.get("captures", 0) >= step["count"]
        if kind == "capture_species":
            return event == "capture" and data.get("species") in (step["species"], *step.get("also", []))
        if kind == "visit":
            return f"visited:{step['area']}" in flags
        if kind == "challenge":
            return f"challenge:{step['id']}" in flags
        if kind == "flags_all":
            return all(flag in flags for flag in step["flags"])
        if kind == "flag":
            return step["flag"] in flags
        if kind == "open_chests":
            return sum(1 for flag in flags if flag.startswith("opened:")) >= step["count"]
        return False

    def _advance(self, quest_id, event, data):
        state = self.states[quest_id]
        progress = state["progress"]
        counters = progress.setdefault("counters", {})
        if event in ("battle_won", "trial_won"):
            counters["wins"] = counters.get("wins", 0) + 1
        elif event == "capture":
            counters["captures"] = counters.get("captures", 0) + 1
        quest = self.definition(quest_id)
        flags = self.flags()
        messages, moved = [], False
        while progress["step"] < len(quest["steps"]):
            step = quest["steps"][progress["step"]]
            if not self._step_met(step, event, data, counters, flags):
                break
            progress["step"] += 1
            counters.clear()
            event = None   # one event satisfies at most one event-driven step
            moved = True
        if progress["step"] >= len(quest["steps"]):
            return messages + self._complete(quest_id, progress)
        if moved:
            messages.append(f"{quest['title']}: {self.step_text(quest_id)}")
        self._save(quest_id, "active", progress)
        return messages

    def _complete(self, quest_id, progress):
        quest = self.definition(quest_id)
        rewards = quest.get("rewards", {})
        if not self.repository.complete_quest(self.player_id, quest_id, progress, rewards):
            return []
        self.states[quest_id] = {"status": "completed", "progress": progress, "just_completed": True}
        parts = []
        if rewards.get("exp"):
            parts.append(f"{rewards['exp']} EXP")
        if rewards.get("coins"):
            parts.append(f"{rewards['coins']} coins")
        parts += [f"{name} x{count}" for name, count in rewards.get("items", {}).items()]
        return [f"Quest complete: {quest['title']}! Reward: {', '.join(parts) or 'thanks'}."]

    def _save(self, quest_id, status, progress):
        self.states[quest_id] = {"status": status, "progress": progress}
        self.repository.save_quest(self.player_id, quest_id, status, progress)

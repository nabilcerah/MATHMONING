"""The story system: which scene plays when, the current chapter, and the Codex.

Pure Python (no pygame) and fully data-driven (data/story/*.json). Everything the story
remembers is a world flag, so it saves and restores with the existing save data:

    scene:<id>          a scene has been seen          chapter_seen:<id>  its title card was shown
    lore:<id>           a codex entry is unlocked       record:<id>        a historical record was read
    choice:<name>       an important choice was made    ending:<id>        how the story ended

The game reports events (talk, visit, interact, challenge, boss_before, boss_after, record, flag,
enter_world, opening, ending); ``scene_for`` answers with the scene to show, or None.
"""
import json
from functools import lru_cache

from config import ROOT
from monsters.monster_data import has_species, species

STORY_DIR = ROOT / "data" / "story"
RECORDS_FOR_TRUE_ENDING = 12


@lru_cache(maxsize=None)
def data(name):
    return json.loads((STORY_DIR / f"{name}.json").read_text(encoding="utf-8"))


def characters():
    return data("characters")["characters"]


def categories():
    return data("characters")["categories"]


def scenes():
    return data("scenes")["scenes"]


def chapters():
    return data("chapters")["chapters"]


def lore():
    return data("lore")


def bestiary():
    return data("bestiary")["species"]


class StoryManager:
    def __init__(self, has_flag, set_flag):
        """``has_flag(flag)`` and ``set_flag(flag)`` read and persist world flags."""
        self.has = has_flag
        self._set = set_flag

    # ================================================================== chapters
    def chapter(self):
        current = None
        for chapter in chapters():
            if self.has(chapter["starts"]) and not (chapter["ends"] and self.has(chapter["ends"])):
                current = chapter
        return current or chapters()[0]

    def chapter_by_id(self, chapter_id):
        return next(c for c in chapters() if c["id"] == chapter_id)

    def pending_chapter_card(self):
        """The current chapter, if its title card hasn't been shown yet."""
        chapter = self.chapter()
        if self.has(chapter["starts"]) and not self.has(f"chapter_seen:{chapter['id']}"):
            return chapter
        return None

    def mark_card_shown(self, chapter_id):
        self.set_flag(f"chapter_seen:{chapter_id}")

    # ================================================================== scenes
    def scene_for(self, event, **info):
        """The highest-priority scene whose trigger matches this event and whose conditions hold."""
        best = None
        for order, (scene_id, scene) in enumerate(scenes().items()):
            trigger = scene.get("trigger", {})
            if trigger.get("event") != event:
                continue
            if any(info.get(key) != value for key, value in trigger.items() if key != "event"):
                continue
            if scene.get("once", True) and self.has(f"scene:{scene_id}"):
                continue
            if any(not self.has(flag) for flag in scene.get("requires", [])):
                continue
            if any(self.has(flag) for flag in scene.get("excludes", [])):
                continue
            if scene.get("chapter") and scene["chapter"] != self.chapter()["id"]:
                continue
            rank = (scene.get("priority", 0), -order)
            if best is None or rank > best[0]:
                best = (rank, scene_id)
        return best[1] if best else None

    def scene(self, scene_id):
        """A scene by id, including the generated ones (records and MathMon discoveries)."""
        if scene_id.startswith("record:"):
            return self.record_scene(scene_id.split(":", 1)[1])
        if scene_id.startswith("discover:"):
            return self.discovery_scene(scene_id.split(":", 1)[1])
        return dict(scenes()[scene_id], id=scene_id)

    def record_scene(self, record_id):
        entry = lore()["entries"][record_id]
        return {"id": f"record:{record_id}", "category": "record", "title": entry["title"],
                "lines": [{"s": "inscription", "t": page} for page in entry["pages"]],
                "set": [f"record:{record_id}"], "lore": [record_id], "once": False}

    def discovery_scene(self, species_id):
        spec = species(species_id)
        info = bestiary().get(species_id, {})
        lines = [{"s": "narrator", "t": f"New MathMon discovered: {spec.name}! A Codex entry has been added."}]
        if info.get("concept") and self.has("numlink"):
            lines.append({"s": "numlink", "t": f"{spec.name}! {info['concept']}"})
        return {"id": f"discover:{species_id}", "category": "discovery", "lines": lines,
                "set": [f"discovered:{species_id}"], "once": False}

    def option_visible(self, option):
        return all(self.has(flag) for flag in option.get("requires", []))

    # ================================================================== effects
    def set_flag(self, flag):
        if not self.has(flag):
            self._set(flag)
            if flag.startswith("record:"):
                self._count_records()
            return True
        return False

    def _count_records(self):
        found = sum(1 for entry_id, entry in lore()["entries"].items()
                    if entry.get("section") == "records" and entry_id != "record_journal"
                    and self.has(f"record:{entry_id}"))
        if found >= RECORDS_FOR_TRUE_ENDING:
            self.set_flag("records:twelve")

    def apply(self, effects):
        """Apply a scene's or a choice's effects. Returns (new_flags, actions, quest_to_start)."""
        new = []
        for flag in effects.get("set", []):
            if self.set_flag(flag):
                new.append(flag)
        for lore_id in effects.get("lore", []):
            if self.set_flag(f"lore:{lore_id}"):
                new.append(f"lore:{lore_id}")
        actions = [effects["action"]] if effects.get("action") else []
        return new, actions, effects.get("quest")

    def finish(self, scene):
        """Mark a scene seen and apply its own effects."""
        if scene["id"] and not scene["id"].startswith(("record:", "discover:")):
            self.set_flag(f"scene:{scene['id']}")
        return self.apply(scene)

    # ================================================================== codex
    def records_found(self):
        return [entry_id for entry_id, entry in lore()["entries"].items()
                if entry.get("section") == "records" and self.has(f"record:{entry_id}")]

    def entry_visible(self, entry_id, entry):
        return self.has(entry.get("unlock") or f"lore:{entry_id}")

    def codex(self, section, seen_species=(), caught_species=()):
        """[(title, [(text or None if locked)])] for a codex section."""
        if section == "monsters":
            return self._monster_entries(seen_species, caught_species)
        if section == "story":
            return self._story_entries()
        out = []
        for entry_id, entry in lore()["entries"].items():
            if entry.get("section") != section or not self.entry_visible(entry_id, entry):
                continue
            parts = []
            for part in entry["parts"]:
                flag = part.get("unlock")
                parts.append(part["text"] if (flag is None or self.has(flag)) else None)
            out.append((entry["title"], parts))
        return out

    def _monster_entries(self, seen, caught):
        out = []
        for species_id, info in bestiary().items():
            if not has_species(species_id) or species_id not in seen:
                continue
            spec = species(species_id)
            title = spec.title or spec.name
            known = [f"Concept: {info['concept']}", f"Habitat: {info['habitat']}", f"Behaviour: {info['behaviour']}"]
            deep = [f"Relationships: {info['relationships']}", f"History: {info['history']}", f"Story: {info['role']}"]
            have = species_id in caught or spec.boss
            out.append((title, known + [text if have else None for text in deep]))
        return out

    def _story_entries(self):
        out = []
        for chapter in chapters():
            if not self.has(chapter["starts"]):
                continue
            parts = [f"Objective: {chapter['objective']}", chapter["summary"]]
            if chapter.get("ending"):
                parts.append(chapter["ending"] if chapter["ends"] and self.has(chapter["ends"]) else None)
            out.append((f"{chapter['number']}: {chapter['title']}", parts))
        ending = lore()["entries"]["ending"]
        if self.has("ending:done"):
            out.append((ending["title"], [p["text"] for p in ending["parts"] if self.has(p["unlock"])]))
        return out

    def section_titles(self):
        return lore()["section_titles"]

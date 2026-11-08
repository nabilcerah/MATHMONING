"""The lore and story system: data integrity, the dialogue screen, story progression, the Codex,
quests with lore links, save/load, and a full playthrough of the final chapter to every ending."""
import tempfile
import unittest

from tests.story_helpers import finish_story

import pygame  # noqa: E402  (story_helpers sets the SDL dummy drivers first)

from game.game_manager import GameManager
from monsters.monster_data import challenges, has_species, quests, species_ids
from states.codex_state import ChapterCard, CodexScreen
from states.scene_state import SceneScreen
from world import story_manager as sm
from world.story_manager import StoryManager

E = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, unicode="", mod=0)


def flags_story(initial=()):
    flags = set(initial)
    return StoryManager(flags.__contains__, flags.add), flags


class StoryDataTests(unittest.TestCase):
    def test_every_reference_in_the_story_data_exists(self):
        entries, speakers, cats = sm.lore()["entries"], sm.characters(), sm.categories()
        chapter_ids = {c["id"] for c in sm.chapters()}
        for scene_id, scene in sm.scenes().items():
            with self.subTest(scene=scene_id):
                self.assertIn(scene.get("category", "npc"), cats)
                blocks = [scene] + (scene.get("choices") or {}).get("options", [])
                for block in blocks:
                    for line in block.get("lines", []) + block.get("after", []):
                        self.assertIn(line["s"], speakers)
                        self.assertTrue(line["t"].strip())
                    for lore_id in block.get("lore", []):
                        self.assertIn(lore_id, entries)
                    if block.get("quest"):
                        self.assertIn(block["quest"], quests())
                    action = block.get("action") or ""
                    if action.startswith("challenge:"):
                        self.assertIn(action.split(":", 1)[1], challenges())
                    for flag in block.get("requires", []):
                        if flag.startswith("record:"):
                            self.assertIn(flag.split(":", 1)[1], entries)
                if scene.get("chapter"):
                    self.assertIn(scene["chapter"], chapter_ids)
                if scene.get("chapter_card"):
                    self.assertIn(scene["chapter_card"], chapter_ids)

    def test_quests_link_to_lore_and_have_every_kind(self):
        kinds = {q.get("category") for q in quests().values()}
        for kind in ("main", "side", "exploration", "history", "mathmon", "secret"):
            self.assertIn(kind, kinds)
        for quest_id, quest in quests().items():
            for lore_id in quest.get("lore", []):
                self.assertIn(lore_id, sm.lore()["entries"], quest_id)

    def test_every_mathmon_has_lore_and_none_were_renamed(self):
        bestiary = sm.bestiary()
        for species_id, info in bestiary.items():
            self.assertTrue(has_species(species_id), species_id)
            for field in ("concept", "habitat", "behaviour", "relationships", "history", "role"):
                self.assertTrue(info.get(field), (species_id, field))
        for species_id in species_ids():
            self.assertIn(species_id, bestiary)

    def test_every_speaker_has_a_portrait_or_a_text_style(self):
        for speaker_id, info in sm.characters().items():
            self.assertIn("name", info, speaker_id)

    def test_no_audio_narration(self):
        """Story is text only: no voice, TTS or narration audio in the story data or screens."""
        import pathlib
        text = "".join(p.read_text(encoding="utf-8") for p in
                       [pathlib.Path(sm.__file__), pathlib.Path("states/scene_state.py"),
                        pathlib.Path("states/codex_state.py")])
        for word in ("pyttsx", "gTTS", "speech", "voice"):
            self.assertNotIn(word, text)


class DialogueScreenTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.surface = pygame.Surface((320, 240))
        self.story, self.flags = flags_story({"game:started"})

    def scene(self, scene_id):
        return SceneScreen(None, self.story, self.story.scene(scene_id))

    def test_typewriter_reveals_then_advances(self):
        screen = self.scene("opening")
        first = screen.line
        self.assertFalse(screen.revealed)
        screen.draw(self.surface, 0)                     # draws a partly typed line
        screen.handle_key(pygame.K_RETURN)               # first press: show the whole line
        self.assertTrue(screen.revealed)
        self.assertIs(screen.line, first)
        screen.handle_key(pygame.K_RETURN)               # second press: next line
        self.assertIsNot(screen.line, first)

    def test_skip_jumps_to_the_choice_and_choices_change_flags(self):
        screen = self.scene("burnt_log_choice")
        screen.handle_key(pygame.K_ESCAPE)
        self.assertTrue(screen.in_choice)
        screen.draw(self.surface, 0)
        labels = [o["label"] for o in screen.options()]
        self.assertEqual(len(labels), 2)
        screen.choose(1)                                 # keep it secret
        while not screen.closed:
            screen.age = 10 ** 6
            screen.handle_key(pygame.K_RETURN)
        self.assertIn("choice:kept_secret", self.flags)
        self.assertNotIn("choice:confronted", self.flags)
        self.assertIn("scene:burnt_log_choice", self.flags)

    def test_explore_choices_can_be_asked_then_left(self):
        screen = self.scene("prologue_village")
        screen.handle_key(pygame.K_ESCAPE)
        options = screen.options()
        self.assertEqual(options[-1].get("exit"), True)
        screen.choose(0)                                 # "What is the Numera?"
        self.assertIn("lore:numera", self.flags)
        screen.handle_key(pygame.K_ESCAPE)               # skip the answer, back to the menu
        self.assertTrue(screen.in_choice)
        screen.choose(len(screen.options()) - 1)         # "Let's begin!"
        while not screen.closed:
            screen.age = 10 ** 6
            screen.handle_key(pygame.K_RETURN)
        self.assertIn("chapter:prologue_done", self.flags)
        self.assertIn("lore:numera", screen.result["flags"] + ["lore:numera"])

    def test_locked_options_are_hidden(self):
        screen = self.scene("final_choice")
        screen.handle_key(pygame.K_ESCAPE)
        self.assertEqual(len(screen.options()), 2)       # the true ending needs the journal and 12 records
        self.flags.update({"record:record_journal", "records:twelve"})
        self.assertEqual(len(screen.options()), 3)

    def test_every_scene_and_category_draws(self):
        for scene_id in list(sm.scenes())[:60] + ["record:record_burnt_log", "discover:DIVOWL"]:
            with self.subTest(scene=scene_id):
                screen = self.scene(scene_id)
                for _ in range(3):
                    screen.update()
                    screen.draw(self.surface, 0)
                screen.handle_key(pygame.K_ESCAPE)
                if not screen.closed:
                    screen.draw(self.surface, 0)


class StoryProgressTests(unittest.TestCase):
    def test_chapters_follow_the_boss_flags(self):
        story, flags = flags_story()
        self.assertEqual(story.chapter()["id"], "prologue")
        expected = [("game:started", "prologue"), ("chapter:prologue_done", "ch1"), ("boss:numerex", "ch2"),
                    ("boss:guardian", "ch3"), ("boss:dragon", "ch4"), ("boss:overlord", "final"),
                    ("ending:done", "epilogue")]
        for flag, chapter in expected:
            flags.add(flag)
            self.assertEqual(story.chapter()["id"], chapter, flag)

    def test_scenes_play_once_and_respect_conditions(self):
        story, flags = flags_story({"game:started"})
        self.assertEqual(story.scene_for("enter_world"), "prologue_village")
        story.finish(story.scene("prologue_village"))
        self.assertIsNone(story.scene_for("enter_world"))
        self.assertEqual(story.scene_for("talk", npc="rowan"), "prof_ch1")
        flags.add("boss:numerex")
        self.assertEqual(story.scene_for("talk", npc="rowan"), "prof_ch2")
        self.assertIsNone(story.scene_for("talk", npc="vera"))           # not until the final chapter

    def test_twelve_records_unlock_the_true_ending(self):
        story, flags = flags_story()
        records = [e for e, v in sm.lore()["entries"].items()
                   if v.get("section") == "records" and e != "record_journal"]
        self.assertGreaterEqual(len(records), 12)
        for record_id in records[:11]:
            story.set_flag(f"record:{record_id}")
        self.assertNotIn("records:twelve", flags)
        story.set_flag(f"record:{records[11]}")
        self.assertIn("records:twelve", flags)

    def test_codex_entries_unlock_part_by_part(self):
        story, flags = flags_story({"game:started"})
        names = [title for title, _ in story.codex("characters")]
        self.assertNotIn("Vera Tallow", names)
        flags.add("lore:the_professor")
        professor = dict(story.codex("characters"))["Professor Archibald Numeris"]
        self.assertTrue(professor[0])
        self.assertIn(None, professor)                    # his secrets are still locked
        flags.update({"lore:vera", "vera:revealed"})
        vera = dict(story.codex("characters"))["Vera Tallow"]
        self.assertTrue(vera[1])
        monsters = story.codex("monsters", seen_species={"DIVOWL"}, caught_species=set())
        self.assertEqual(len(monsters), 1)
        self.assertIn(None, monsters[0][1])               # deeper lore needs a capture
        caught = story.codex("monsters", seen_species={"DIVOWL"}, caught_species={"DIVOWL"})
        self.assertNotIn(None, caught[0][1])
        story_entries = story.codex("story")
        self.assertEqual(story_entries[0][0].split(":")[0], "PROLOGUE")


class StoryGameTests(unittest.TestCase):
    """Through the real GameManager: the opening, triggers, records, quests, saves and endings."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = self.folder.name + "/story.sqlite3"
        self.game = GameManager(database_path=self.path)

    def tearDown(self):
        self.game.llm.close()
        self.folder.cleanup()

    def new_game(self):
        game = self.game
        game.player_name = "Sam"
        game.state = "avatar"
        game._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0))
        self.assertEqual(game.state, "starter")
        self.assertEqual(finish_story(game), ["opening"])
        game._create_new_player()
        return finish_story(game)

    def stand_next_to(self, cell):
        world = self.game.world
        x, y = cell
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            if world.world.is_walkable((x + dx, y + dy)):
                world.avatar.x, world.avatar.y = world.world.cell_to_feet((x + dx, y + dy))
                world.avatar.facing = (-dx, -dy)
                world.update()
                return finish_story(self.game)
        self.fail(f"nothing walkable next to {cell}")

    def use(self, target_id, pick=None):
        world = self.game.world
        if target_id in world.objects:
            self.stand_next_to(world.objects[target_id]["pos"])
        else:
            npc = next(n for n in world.npcs if n.id == target_id)
            npc.state, npc.wait, npc.path = "working", 10 ** 6, []
            self.stand_next_to(npc.cell())
        self.assertEqual(world.target_id(), target_id)
        self.game._overworld_key(E)
        shown = []
        for _ in range(20):
            shown += finish_story(self.game, pick)
            if not world.dialogue:
                break
            world.dialogue.age = 10 ** 6
            self.game._overworld_key(E)
        return shown

    def solve_challenge(self):
        screen = self.game.states.overlay
        self.assertEqual(type(screen).__name__, "ChallengeScreen")
        screen.handle_key(pygame.K_RETURN)
        while screen.state == "question":
            screen.answer(screen.panel.question.answer)
            screen.handle_key(pygame.K_RETURN)
        self.assertTrue(screen.passed)
        screen.handle_key(pygame.K_RETURN)
        self.game._update()

    # ------------------------------------------------------------------ tests
    def test_new_game_opening_prologue_and_chapter_cards(self):
        shown = self.new_game()
        game = self.game
        self.assertEqual(shown, ["card:prologue", "prologue_village", "card:ch1"])
        for flag in ("scene:opening", "lore:creation", "game:started", "chapter:prologue_done", "numlink"):
            self.assertTrue(game.world.has_flag(flag), flag)
        self.assertEqual(game.story.chapter()["id"], "ch1")
        # The Professor now talks about chapter 1, and offers a practice battle.
        asked = []

        def practice_then_leave(options):
            asked.append(1)
            return 2 if len(asked) == 1 else len(options) - 1
        self.assertEqual(self.use("rowan", pick=practice_then_leave), ["prof_ch1"])
        self.assertEqual(game.state, "battle")

    def test_records_codex_and_the_locked_drawer(self):
        self.new_game()
        game = self.game
        self.assertEqual(self.use("counting_stone"), ["record:record_counting_stone"])
        self.assertTrue(game.world.has_flag("record:record_counting_stone"))
        self.assertIn("record_counting_stone", game.story.records_found())
        # The Professor's lab, through the door in the village.
        game._travel_to_map("village_lab", (6, 7))
        finish_story(game)
        self.assertEqual(self.use("lab_notes"), ["record:record_professor_notes"])
        self.assertEqual(self.use("locked_drawer"), [])           # locked: no key yet
        self.assertFalse(game.world.has_flag("record:record_journal"))
        game.world.set_flag("item:lab_key")
        self.assertEqual(self.use("locked_drawer"), ["record:record_journal"])
        # The Codex shows the records and draws every section.
        screen = game.open_screen("codex")
        surface = pygame.Surface((320, 240))
        titles = []
        for _ in range(len(game.story.section_titles()) + 1):
            screen.draw(surface, 0)
            titles.append(screen.section)
            screen.handle_key(pygame.K_RIGHT)
        records = dict(game.story.codex("records"))
        self.assertIn("The Professor's Journal", " ".join(records))
        self.assertIsInstance(screen, CodexScreen)

    def test_quest_with_a_mathmon_step(self):
        self.new_game()
        game = self.game
        self.assertIn("tobi_lost", self.use("tobi"))
        self.assertEqual(game.quests.status("missing_mathmon"), "active")
        game._start_battle(__import__("monsters.monster_factory", fromlist=["create"]).create("DIVOWL", 2))
        game.battle.battle.outcome, game.battle.battle.awaiting = "captured", "over"
        game.battle.closed = True
        game._update()
        finish_story(game)
        self.assertEqual(game.quests.step_index("missing_mathmon"), 1)

    def test_story_progress_saves_and_restores(self):
        self.new_game()
        game = self.game
        self.use("counting_stone")
        game.world.set_flag("boss:numerex")
        game._refresh_boss_gate()
        game._enter_world()
        shown = finish_story(game)
        self.assertIn("card:ch2", shown)
        game.save_all()
        again = GameManager(database_path=self.path)
        try:
            again._continue_game()
            self.assertEqual(finish_story(again), [])                # nothing replays after loading
            self.assertEqual(again.story.chapter()["id"], "ch2")
            self.assertTrue(again.world.has_flag("record:record_counting_stone"))
            self.assertTrue(again.world.has_flag("lore:the_professor"))
        finally:
            again.llm.close()

    def test_saves_from_before_the_story_skip_the_prologue(self):
        self.new_game()
        game = self.game
        pid = game.player.player_id
        game.world.set_flag("boss:numerex")
        game.save_all()
        # Simulate a save from before the story existed: only gameplay flags remain.
        for prefix in ("scene:", "lore:", "chapter", "game:", "numlink", "record:"):
            game.repository.clear_world_flags(pid, prefix)
        again = GameManager(database_path=self.path)
        try:
            again._continue_game()
            shown = finish_story(again)
            self.assertNotIn("prologue_village", shown)
            self.assertNotIn("card:prologue", shown)
            self.assertEqual(again.story.chapter()["id"], "ch2")
        finally:
            again.llm.close()

    def final_chapter(self):
        self.new_game()
        game = self.game
        for flag in ("boss:numerex", "boss:guardian", "boss:dragon", "boss:overlord", "vera:revealed", "final:open"):
            game.world.set_flag(flag)
        game._travel_to_map("chronos_dimension", tuple(game.world.world.data.get("start", (0, 0))))
        finish_story(game)
        vera = [n for n in game.world.npcs if n.id == "vera"]
        self.assertEqual(len(vera), 1)                              # she waits at the Engine
        self.assertEqual(self.use("vera"), ["final_engine"])
        self.solve_challenge()
        return game

    def test_final_chapter_and_each_ending(self):
        for ending, index in (("sealed", 0), ("open", 1)):
            with self.subTest(ending=ending):
                self.tearDown()
                self.setUp()
                game = self.final_chapter()
                shown = finish_story(game, pick=index)
                self.assertEqual(shown[:2], ["final_choice", f"ending_{ending}"])
                self.assertTrue(game.world.has_flag(f"ending:{ending}"))
                self.assertTrue(game.world.has_flag("ending:done"))
                self.assertEqual(game.story.chapter()["id"], "epilogue")
                self.assertEqual(game.quests.status("the_last_calculation"), "completed")
                self.assertNotIn("vera", [n.id for n in game.world.npcs])   # she has gone home

    def test_true_ending_needs_the_journal_and_twelve_records(self):
        game = self.final_chapter()
        screen = game.states.overlay
        self.assertIsInstance(screen, SceneScreen)
        screen.handle_key(pygame.K_ESCAPE)
        self.assertEqual(len(screen.options()), 2)
        records = [e for e, v in sm.lore()["entries"].items() if v.get("section") == "records"]
        for record_id in records:
            game.story.set_flag(f"record:{record_id}")
        self.assertEqual(len(screen.options()), 3)
        shown = finish_story(game, pick=2)
        self.assertEqual(shown[:2], ["final_choice", "ending_theorem"])
        self.assertTrue(game.world.has_flag("ending:theorem"))

    def test_chapter_card_draws(self):
        self.new_game()
        card = ChapterCard(self.game, sm.chapters()[1])
        surface = pygame.Surface((320, 240))
        for _ in range(60):
            card.update()
            card.draw(surface, 0)
        self.assertFalse(card.closed)
        card.handle_key(pygame.K_RETURN)
        self.assertTrue(card.closed)


if __name__ == "__main__":
    unittest.main()

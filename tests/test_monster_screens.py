"""The Trials hall, the advanced battle screen and the sliced sprite animations."""
import json
import os
import random
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from battle_engine.monster_data import load_all
from config import ROOT
from database.database import Database
from database.player_repository import PlayerRepository
from game import monster_sprites
from game.animation import SpriteAnimator
from game.monster_battle import MonsterBattleScreen
from game.player import Player
from game.trials_screen import TrialsScreen

pygame.init()


class SpriteTests(unittest.TestCase):
    def test_every_monster_has_nine_sliced_frames_in_rows(self):
        for defn in load_all().values():
            info = json.loads((ROOT / "assets" / "sprites" / "monsters" / defn.sprite / "manifest.json").read_text())
            self.assertEqual(info["layout"], "rows")
            self.assertEqual(len(info["poses"]), 9)
            self.assertEqual(info["animations"], {"idle": [0, 1, 2], "walk": [3, 4, 5], "attack": [6, 7, 8]})

    def test_animator_plays_idle_walk_attack_from_real_frames(self):
        animator = SpriteAnimator("VOLTBYTE")
        seen = set()
        for _ in range(120):
            seen.add(animator.index())
            animator.update()
        self.assertEqual(seen, {0, 1, 2})
        animator.play("attack")
        frames = set()
        for _ in range(60):
            frames.add(animator.index())
            animator.update()
        self.assertTrue({6, 7, 8} <= frames | {8})
        self.assertEqual(animator.animation, "idle")  # one-shot returns to idle
        # Poses with no frames on the sheet fall back to a real frame (never an invented one).
        self.assertEqual(monster_sprites.pose_index("VOLTBYTE", "hurt"), 0)

    def test_animation_speed_is_configurable(self):
        slow, fast = SpriteAnimator("NULLSHADE", {"idle": 2}), SpriteAnimator("NULLSHADE", {"idle": 30})
        for _ in range(30):
            slow.update()
            fast.update()
        self.assertNotEqual(slow.index(), fast.index())


class ScreenTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repo = PlayerRepository(Database(self.folder.name + "/t.sqlite3"))
        pid = self.repo.create_player("T", "PYRON", 60)
        self.player = Player("T", "PYRON", 12, 80, 80, 0, 16, 60, pid)
        self.repo.save_player(self.player)
        self.surface = pygame.Surface((320, 240))

    def tearDown(self):
        self.folder.cleanup()

    def test_trials_screen_browses_and_picks_a_challenge(self):
        trials = TrialsScreen(self.repo, self.player)
        for key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_e, pygame.K_q, pygame.K_LEFT, pygame.K_UP):
            trials.handle_key(key)
            trials.update()
            trials.draw(self.surface, 1)
        trials.selected = len(trials.monsters) - 1  # Infinity Zero starts locked
        trials.handle_key(pygame.K_RETURN)
        self.assertFalse(trials.closed)
        self.assertIn("Defeat", trials.notice)
        trials.selected = 0
        trials.handle_key(pygame.K_RETURN)
        self.assertEqual(trials.challenge, (trials.monsters[0].id, 1))

    def test_every_monster_battle_runs_and_draws_to_the_end(self):
        for monster_id in load_all():
            screen = MonsterBattleScreen(self.repo, self.player, monster_id, 3 if monster_id == "infinity_zero" else 1,
                                         random.Random(2))
            screen.engine.player.hp = screen.engine.player.max_hp = 999
            frames = 0
            while not screen.closed and frames < 6000:
                screen.update()
                screen.draw(self.surface, frames)
                frames += 1
                state = screen.state
                if state in ("menu", "topic", "result", "over"):
                    screen.handle_key(pygame.K_RETURN)
                elif state == "events":
                    screen.handle_key(pygame.K_RETURN)
                elif state == "question":
                    engine = screen.engine
                    if screen.typing:
                        screen.typed = engine.question.answer.replace(",", "")
                        screen.handle_key(pygame.K_RETURN)
                    else:
                        screen.choice = next(i for i, c in enumerate(engine.choices) if engine.question.check(c))
                        screen.handle_key(pygame.K_RETURN)
            self.assertTrue(screen.closed, monster_id)
            self.assertEqual(screen.engine.outcome, "won", monster_id)
            self.assertIsNotNone(screen.reward)
        records = self.repo.monster_records(self.player.player_id)
        self.assertEqual(len(records), len(load_all()))
        self.assertGreater(self.repo.trainer_progress(self.player.player_id)["level"], 1)

    def test_mathdex_trials_page_shows_trial_records(self):
        from game.mathdex import MathDex
        self.repo.save_monster_record(self.player.player_id, {"monster_id": "crystalgon", "rank": 3, "wins": 2,
                                                              "losses": 0, "best_turns": 6})
        dex = MathDex(self.repo, self.player)
        dex.handle_key(pygame.K_e)
        self.assertEqual(dex.page, 1)
        self.assertEqual(len(dex.trial_monsters), len(load_all()))
        crystalgon = next(m for m in dex.trial_monsters if m.id == "crystalgon")
        self.assertEqual(dex.trial_record(crystalgon)["rank"], 3)
        for index in range(len(dex.trial_monsters)):
            dex.trial_selected = index
            dex.draw(self.surface, index)
        dex.handle_key(pygame.K_RIGHT)
        dex.handle_key(pygame.K_RETURN)
        self.assertIn("Trials hall", dex.notice)
        dex.handle_key(pygame.K_q)
        self.assertEqual(dex.page, 0)
        dex.draw(self.surface, 1)

    def test_skills_log_typed_mode_potion_and_flee(self):
        self.repo.save_trainer_progress(self.player.player_id, 0, 9)
        screen = MonsterBattleScreen(self.repo, self.player, "crystalgon", 1, random.Random(3))
        screen.state = "menu"
        screen.choose("SKILLS")
        screen.handle_key(pygame.K_DOWN)
        screen.handle_key(pygame.K_RETURN)  # Analyse
        self.assertIn("ANALYSE", screen.message)
        screen.choose("ATTACK")
        screen.handle_key(pygame.K_RETURN)
        self.assertEqual(screen.state, "question")
        screen.handle_key(pygame.K_TAB)
        self.assertTrue(screen.typing)
        for char in screen.engine.question.answer:
            screen.handle_key(0, char)
        screen.handle_key(pygame.K_RETURN)
        self.assertTrue(screen.result.correct)
        self.assertIn("Typed answer", [label for label, _ in screen.result.hit.extras])
        screen.draw(self.surface, 1)
        screen.handle_key(pygame.K_l)
        self.assertTrue(screen.show_log)
        screen.draw(self.surface, 2)
        screen.handle_key(pygame.K_ESCAPE)
        screen.state = "menu"
        screen.engine.player.hp -= 20
        screen.choose("POTION")
        self.assertIn("restores", screen.message)
        screen.state = "menu"
        screen.choose("FLEE")
        self.assertTrue(screen.closed)


if __name__ == "__main__":
    unittest.main()

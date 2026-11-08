"""End-to-end smoke test: menu -> new game -> overworld -> a full battle -> screens -> quit."""
from tests.story_helpers import finish_story
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from game.game_manager import GameManager
from monsters import monster_factory


def finish_battle(battle, answer_right=True, limit=400):
    for _ in range(limit):
        if battle.closed:
            return
        if battle.state == "question":
            panel = battle.panel
            if panel.resolved:
                battle.handle_key(pygame.K_RETURN)
            else:
                battle.answer(panel.question.answer if answer_right else "99999")
        elif battle.state == "menu":
            battle.choose_action("FIGHT")
        elif battle.state == "moves":
            usable = [m for m in battle.moves() if battle.battle.move_usable(m)[0]]
            battle.choose_move(usable[0].move_id)
        elif battle.state == "party":
            battle.switch_to(next(i for i, m in enumerate(battle.party.party) if not m.fainted))
        else:
            battle.handle_key(pygame.K_RETURN)
        battle.update()


class GameSmokeTests(unittest.TestCase):
    def test_full_loop_from_title_to_battle_and_quit(self):
        with tempfile.TemporaryDirectory() as folder:
            game = GameManager(database_path=folder + "/smoke.sqlite3")
            try:
                for state in ("menu", "name", "avatar", "starter", "settings"):
                    game.state = state
                    game._draw()
                game.starter_selected = 3          # CHRONOX
                game._create_new_player()
                finish_story(game)
                self.assertEqual(game.state, "overworld")
                self.assertEqual([m.species_id for m in game.party.party], ["CHRONOX"])
                self.assertIn("fading_numera", game.quests.active())
                start_x = game.world.avatar.x
                for _ in range(10):
                    game.world.update(1, 0)
                self.assertGreater(game.world.avatar.x, start_x)
                game._draw()

                game._start_battle(monster_factory.create("VOLTIX", 1))
                self.assertEqual(game.state, "battle")
                game._draw()
                finish_battle(game.battle)
                game._update()
                self.assertEqual(game.state, "overworld")
                self.assertEqual(finish_story(game), ["discover:VOLTIX"])
                lead = game.party.lead
                self.assertTrue(lead.exp > 0 or lead.level > 1)
                self.assertGreater(game.repository.coins(game.player.player_id), 100)
                summary = game.repository.history_summary(game.player.player_id)
                self.assertGreater(summary["attempted"], 0)
                self.assertTrue(game.repository.recent_decisions(game.player.player_id, 5))

                for name in ("party", "bag", "quests", "mathdex", "profile", "shop", "sanctuary", "evolution"):
                    screen = game.open_screen(name)
                    game._draw()
                    screen.close()
                    game._update()
                self.assertIsNone(game.states.overlay)

                original_event_get = pygame.event.get
                pygame.event.get = lambda: [pygame.event.Event(pygame.QUIT)]
                try:
                    with self.assertRaises(SystemExit) as exit_result:
                        game.run()
                    self.assertEqual(exit_result.exception.code, 0)
                finally:
                    pygame.event.get = original_event_get
            finally:
                game.llm.close()
                pygame.quit()

    def test_defeat_returns_to_the_recovery_center_without_losing_anything(self):
        with tempfile.TemporaryDirectory() as folder:
            game = GameManager(database_path=folder + "/defeat.sqlite3")
            try:
                game._create_new_player()
                finish_story(game)
                caught_before = game.repository.capture_records(game.player.player_id)
                game._start_battle(monster_factory.create("GEOMAX", 15))
                finish_battle(game.battle, answer_right=False, limit=2000)
                self.assertEqual(game.battle.outcome, "defeated")
                game._update()
                self.assertEqual(game.state, "recovery")
                self.assertEqual(game.player.world, "village_recovery")
                self.assertTrue(all(m.hp == m.max_hp for m in game.party.party))
                after = game.repository.capture_records(game.player.player_id)
                self.assertEqual({k: v["captured"] for k, v in after.items() if v["captured"]},
                                 {k: v["captured"] for k, v in caught_before.items()})
                self.assertEqual(len(game.party.party), 1)
                game._draw()
            finally:
                game.llm.close()


if __name__ == "__main__":
    unittest.main()

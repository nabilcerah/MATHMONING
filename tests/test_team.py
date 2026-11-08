import os
import random
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from ai.orchestrator import AgentOrchestrator
from database.database import Database
from database.player_repository import PlayerRepository
from game.battle import Battle
from game.creatures import WILD_BY_NAME, WILD_LEVELS, leveled_stats, matchup
from game.player import Player
from game.team import Team

pygame.init()
ENTER = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0)
DOWN = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, unicode="", mod=0)


class TeamTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repository = PlayerRepository(Database(self.folder.name + "/team.sqlite3"))
        player_id = self.repository.create_player("Trainer", "PYRON", 34)
        self.player = Player("Trainer", "PYRON", 5, 50, 50, 0, 16, 60, player_id)
        self.repository.save_player(self.player)
        self.orchestrator = AgentOrchestrator(self.repository)
        self.pid = player_id

    def tearDown(self):
        self.folder.cleanup()

    def capture(self, species, level):
        # Same order as a real capture: the team gains the member, then the MathDex flag is set.
        Team(self.repository, self.player).add(species, level)
        self.repository.set_world_flag(self.pid, f"dex_friend:{species}")

    def battle(self, enemy, level=3, leader=None):
        if leader:
            self.repository.clear_world_flags(self.pid, "companion:")
            self.repository.set_world_flag(self.pid, f"companion:{leader}")
        battle = Battle(self.player, self.repository, self.orchestrator, None, WILD_BY_NAME[enemy],
                        random.Random(2), level)
        battle.PUZZLE_CHANCE = 0
        return battle

    def hit(self, battle, topic="addition"):
        battle._start_question(topic)
        battle.answer = battle.question.answer
        before = battle.enemy_hp
        battle._submit()
        battle.state = "menu"
        return before - battle.enemy_hp

    # ------------------------------------------------------------------ levels
    def test_each_member_has_its_own_level_and_old_captures_join(self):
        self.capture("VOLTIX", 3)
        self.repository.set_world_flag(self.pid, "dex_friend:DIVOWL")  # captured before levels existed
        team = Team(self.repository, self.player)
        self.assertEqual([team.name_of(m) for m in team.members], ["PYRON", "DIVOWL", "VOLTIX"])
        self.assertEqual(team.find("VOLTIX").level, 3)
        self.assertEqual(team.find("DIVOWL").level, 4)  # one below the partner's 5
        self.assertEqual(team.max_level, 5)

    def test_exp_goes_to_the_monster_that_fought(self):
        self.capture("VOLTIX", 2)
        battle = self.battle("DIVOWL", leader="VOLTIX")
        self.assertEqual(battle.player_spec.name, "VOLTIX")
        partner_exp = self.player.exp
        self.hit(battle)
        voltix = Team(self.repository, self.player).find("VOLTIX")
        self.assertGreater(voltix.exp + voltix.level * 100, 2 * 100)
        self.assertEqual(self.player.exp, partner_exp)

    def test_capture_joins_at_the_wild_level(self):
        battle = self.battle("DIVOWL", level=6)
        battle.enemy_hp = 1
        battle._start_bond()
        for _ in range(2):
            battle.answer = battle.question.answer
            battle._submit()
        self.assertEqual(battle.outcome, "befriended")
        member = Team(self.repository, self.player).find("DIVOWL")
        self.assertEqual(member.level, 6)
        self.assertEqual(member.max_hp, leveled_stats(WILD_BY_NAME["DIVOWL"], 6)[0])

    def test_wild_level_scales_enemy_stats(self):
        low, high = self.battle("VOLTIX", 1), self.battle("VOLTIX", 9)
        self.assertGreater(high.enemy_max_hp, low.enemy_max_hp)
        self.assertGreater(high.enemy_attack, low.enemy_attack)

    # ------------------------------------------------------------------ nemesis
    def test_nemesis_changes_damage_both_ways(self):
        self.assertEqual(matchup("PYRON", "DIVOWL"), "strong")
        self.assertEqual(matchup("PYRONYX", "AQUABIT"), "weak")
        strong_battle = self.battle("DIVOWL")
        neutral = self.hit(self.battle("FRACTELLA"))
        strong = self.hit(strong_battle)
        self.assertGreater(strong, neutral)
        self.assertIn("Super effective", strong_battle.feedback)
        # Taking damage: GEOMAX (strong vs VOLTIX) takes less than PYRON would.
        self.capture("VOLTIX", 5)
        geo_player = Player("G", "GEOMAX", 5, 50, 50, 0, 16, 60, self.pid)
        voltix_vs_geo = Battle(geo_player, self.repository, self.orchestrator, None, WILD_BY_NAME["VOLTIX"],
                               random.Random(1), 5)
        self.repository.clear_world_flags(self.pid, "companion:")
        voltix_vs_geo.fighter = voltix_vs_geo.team.player
        voltix_vs_geo.player_spec = voltix_vs_geo._leader()
        self.assertEqual(voltix_vs_geo.matchup, "strong")
        hp = geo_player.hp
        voltix_vs_geo._enemy_turn()
        self.assertLessEqual(hp - geo_player.hp, round(voltix_vs_geo.enemy_attack * 0.7) + 1)

    # ------------------------------------------------------------------ switching
    def test_switching_uses_your_turn(self):
        self.capture("VOLTIX", 4)
        battle = self.battle("FRACTELLA")
        battle.selected = battle.actions().index("TEAM")
        battle._choose_action()
        self.assertEqual(battle.state, "team")
        battle.handle_event(DOWN)
        battle.handle_event(ENTER)
        self.assertNotEqual(battle.player_spec.name, "PYRON")
        self.assertEqual(battle.state, "resolving")  # the enemy gets a move

    def test_a_faint_asks_for_the_next_member_and_a_wipe_is_gentle(self):
        self.capture("VOLTIX", 4)
        battle = self.battle("FRACTELLA", level=5)
        battle.fighter.hp = 1
        battle.enemy_attack = 99
        battle._enemy_turn()
        self.assertEqual(battle.state, "team")
        self.assertTrue(battle.forced_switch)
        battle.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="", mod=0))
        self.assertEqual(battle.state, "team")  # can't back out of a forced choice
        battle.team_selected = 1
        battle.handle_event(ENTER)
        self.assertEqual(battle.player_spec.name, "VOLTIX")
        self.assertEqual(battle.state, "menu")  # stepping in after a faint is free
        battle.fighter.hp = 1
        battle._enemy_turn()
        self.assertEqual(battle.outcome, "defeated")
        team = Team(self.repository, self.player)
        self.assertTrue(all(m.hp >= m.max_hp // 2 for m in team.members))

    def test_a_fainted_leader_sits_out_the_next_battle(self):
        self.capture("VOLTIX", 4)
        self.player.hp = 0
        self.repository.save_player(self.player)
        battle = self.battle("FRACTELLA")
        self.assertEqual(battle.player_spec.name, "VOLTIX")

    def test_team_screens_draw(self):
        self.capture("VOLTIX", 4)
        self.capture("DIVOWL", 2)
        surface = pygame.Surface((320, 240))
        battle = self.battle("DIVOWL")
        battle.draw(surface, 0)
        battle.selected = battle.actions().index("TEAM")
        battle._choose_action()
        for _ in range(3):
            battle.draw(surface, 1)
            battle.handle_event(DOWN)
        from game.mathdex import MathDex
        dex = MathDex(self.repository, self.player)
        for index in range(len(dex.entries())):
            dex.selected = index
            dex.draw(surface, index)


class WildLevelTests(unittest.TestCase):
    def test_roamers_spawn_within_their_area_range(self):
        from game.overworld import Overworld
        with tempfile.TemporaryDirectory() as folder:
            repository = PlayerRepository(Database(folder + "/roam.sqlite3"))
            pid = repository.create_player("R", "PYRON", 34)
            world = Overworld(Player("R", "PYRON", 1, 34, 34, 0, 16, 60, pid), random.Random(3), repository)
            for roamer in world.roamers:
                low, high = WILD_LEVELS.get(roamer.zone["area"], (1, 3))
                self.assertTrue(low <= roamer.level <= high, (roamer.zone["area"], roamer.level))


if __name__ == "__main__":
    unittest.main()

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
from game.creatures import BOSS, SHAPES, WILD, WILD_BY_NAME, creature_spec, encounter_for
from game.mathdex import MathDex
from game.overworld import Overworld
from game.player import Player

pygame.init()


class BefriendTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repository = PlayerRepository(Database(self.folder.name + "/bond.sqlite3"))
        player_id = self.repository.create_player("Friendly", "AQUABIT", 38)
        self.player = Player("Friendly", "AQUABIT", 3, 38, 38, 0, 6, 7, player_id)
        self.orchestrator = AgentOrchestrator(self.repository)

    def tearDown(self):
        self.folder.cleanup()

    def battle(self, spec=None):
        return Battle(self.player, self.repository, self.orchestrator, None, spec or WILD_BY_NAME["VOLTIX"],
                      random.Random(7))

    def bond_answer(self, battle, correct):
        battle.answer = battle.question.answer if correct else "-999"
        battle._submit()

    def flags(self):
        return self.repository.world_flags(self.player.player_id)

    def test_befriend_appears_only_when_weakened(self):
        battle = self.battle()
        self.assertIn("dex_seen:VOLTIX", self.flags())
        self.assertNotIn("CAPTURE", battle.actions())
        battle.enemy_hp = int(battle.enemy_max_hp * 0.4)
        self.assertIn("CAPTURE", battle.actions())
        self.assertNotIn("CAPTURE", self.battle(BOSS).actions())

    def test_a_rivals_monster_cannot_be_captured(self):
        battle = self.battle()
        battle.enemy_hp = 1
        self.assertIn("CAPTURE", battle.actions())
        battle.is_trainer = True
        self.assertNotIn("CAPTURE", battle.actions())

    def test_two_correct_answers_win_a_friend(self):
        battle = self.battle()
        battle.enemy_hp = 5
        battle.selected = battle.actions().index("CAPTURE")
        battle._choose_action()
        self.assertEqual(battle.question.topic, "multiplication")  # VOLTIX is a multiplication creature
        self.bond_answer(battle, True)
        self.bond_answer(battle, False)
        self.assertEqual(battle.state, "question")
        self.bond_answer(battle, True)
        self.assertEqual(battle.outcome, "befriended")
        self.assertIn("dex_friend:VOLTIX", self.flags())
        # Already a friend: no second befriend offer for the same species.
        again = self.battle()
        again.enemy_hp = 1
        self.assertNotIn("CAPTURE", again.actions())

    def test_failed_bond_is_gentle_and_can_be_retried_after_an_attack(self):
        battle = self.battle()
        battle.enemy_hp = battle.enemy_max_hp = 200
        battle.enemy_hp = 60
        hp = self.player.hp
        battle._start_bond()
        self.bond_answer(battle, False)
        self.bond_answer(battle, False)
        self.assertEqual(battle.state, "menu")
        self.assertEqual(self.player.hp, hp)  # no counterattack for a failed bond
        self.assertNotIn("CAPTURE", battle.actions())
        battle._start_question("addition")
        battle.answer = battle.question.answer
        battle._submit()
        battle.state = "menu"
        self.assertIn("CAPTURE", battle.actions())

    def test_friends_boost_their_topic(self):
        self.repository.set_world_flag(self.player.player_id, "dex_friend:DIVOWL")
        self.repository.set_world_flag(self.player.player_id, "dex_friend:FRACTELLA")
        battle = self.battle(WILD_BY_NAME["VOLTIX"])
        self.assertAlmostEqual(battle.friend_bonus("division"), 1.2)
        self.assertAlmostEqual(battle.friend_bonus("addition"), 1.0)
        battle.enemy_hp = battle.enemy_max_hp = 999
        battle._start_question("division")
        battle.answer = battle.question.answer
        battle._submit()
        self.assertIn("Team +20%", battle.feedback)

    def test_habitats_and_shapes(self):
        rng = random.Random(3)
        for area in ("meadow", "grove", "ridge"):
            for _ in range(40):
                self.assertIn(area, encounter_for(area, rng).habitat)
        self.assertIn("meadow", encounter_for("camp", rng).habitat)
        for spec in WILD:
            self.assertIn(spec.shape, SHAPES)
            self.assertEqual(creature_spec(spec.name), spec)
        surface = pygame.Surface((64, 64))
        from game.creatures import BOSS, EVOLUTIONS, STARTERS, draw_creature
        from game import monster_sprites
        for spec in list(WILD) + list(STARTERS.values()) + list(EVOLUTIONS.values()) + [BOSS]:
            self.assertTrue(monster_sprites.available(spec.sprite), spec.name)
            self.assertEqual(len(monster_sprites.manifest(spec.sprite)["poses"]), 9)
            for pose in ("idle", "attack", "hurt", "happy"):
                draw_creature(surface, spec, (32, 60), 40, pose, flip=True, tint=(255, 255, 255))

    def test_choosing_a_leader_never_removes_your_partner(self):
        self.repository.set_world_flag(self.player.player_id, "dex_friend:VOLTIX")
        dex = MathDex(self.repository, self.player)
        surface = pygame.Surface((320, 240))
        dex.draw(surface, 0)
        self.assertIs(dex.entries()[0], dex.partner)  # the starter is always listed first
        self.assertEqual(dex.leader, "AQUABIT")
        dex.selected = 1  # VOLTIX
        dex.handle_key(pygame.K_RETURN)
        self.assertEqual(dex.leader, "VOLTIX")
        world = Overworld(self.player, random.Random(1), self.repository)
        self.assertEqual(world.companion_spec().name, "VOLTIX")
        # The leader is the one that battles.
        self.assertEqual(self.battle().player_spec.name, "VOLTIX")
        dex.handle_key(pygame.K_RETURN)  # choosing the leader again keeps it leading
        self.assertEqual(dex.leader, "VOLTIX")
        self.assertIn("already leading", dex.notice)
        dex.selected = 0  # back to the partner
        dex.handle_key(pygame.K_RETURN)
        self.assertEqual(dex.leader, "AQUABIT")
        world.refresh_flags()
        self.assertEqual(world.companion_spec().name, "AQUABIT")
        self.assertEqual(self.battle().player_spec.name, "AQUABIT")
        self.assertIn("dex_friend:VOLTIX", self.flags())  # VOLTIX is still on the team
        dex.selected = 4  # CHRONOX, not captured
        dex.handle_key(pygame.K_RETURN)
        self.assertIn("Capture it first", dex.notice)
        self.assertEqual(dex.leader, "AQUABIT")
        for key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_LEFT, pygame.K_UP):
            dex.handle_key(key)
            dex.draw(surface, 1)
        dex.handle_key(pygame.K_ESCAPE)
        self.assertTrue(dex.closed)

    def test_captured_leaders_have_skills_that_map_to_topics(self):
        from game.creatures import WILD
        for spec in WILD:
            self.assertGreaterEqual(len(spec.skills), 2, spec.name)
            for skill in spec.skills:
                self.assertIn(skill, Battle.TOPIC_FOR_SKILL, skill)

    def test_avatar_choice_and_character_sprites(self):
        from game import monster_sprites
        for name in ("ALEX", "LUNA", "PROFESSOR_NUMERIS", "REX"):
            self.assertTrue(monster_sprites.available(f"characters/{name}"), name)
            self.assertEqual(len(monster_sprites.manifest(f"characters/{name}")["poses"]), 9)
        self.assertEqual(Overworld(self.player, random.Random(1), self.repository).avatar.sheet, "characters/ALEX")
        self.repository.set_world_flag(self.player.player_id, "avatar:LUNA")
        world = Overworld(self.player, random.Random(1), self.repository)
        self.assertEqual(world.avatar.sheet, "characters/LUNA")
        surface = pygame.Surface((320, 240))
        world.draw(surface, 3)  # avatar, Professor Numeris and Rex all draw from their sheets

    def test_old_saves_and_companions_still_load(self):
        from game.creatures import canonical_name
        self.assertEqual(canonical_name("PYROX"), "PYRON")
        self.assertEqual(creature_spec("TERRABIT").name, "GEOMAX")
        self.assertEqual(creature_spec("PYROX", 8).name, "PYRONYX")
        self.repository.set_world_flag(self.player.player_id, "companion:MOSSNIP")  # removed species
        world = Overworld(self.player, random.Random(1), self.repository)
        self.assertEqual(world.companion_spec().name, "AQUABIT")

    def test_bond_screens_draw(self):
        surface = pygame.Surface((320, 240))
        battle = self.battle()
        battle.enemy_hp = 3
        battle.draw(surface, 0)
        battle._start_bond()
        self.bond_answer(battle, True)
        battle.draw(surface, 1)
        self.bond_answer(battle, True)
        for frame in range(5):
            battle.update()
            battle.draw(surface, frame)


if __name__ == "__main__":
    unittest.main()

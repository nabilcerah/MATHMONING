"""GDD 30 Definition of Done, driven through the real GameManager: start a game, follow the main
quest through the ruins' puzzle gates to the boss, finish the side quests (including the bridge
that unlocks a new area and the crystal that awakens the Evolution Shrine), evolve, save, restore."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from game.game_manager import GameManager
from monsters.monster_factory import create
from tests.test_game_smoke import finish_battle

E = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, unicode="", mod=0)


class RegionFlowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = self.folder.name + "/flow.sqlite3"
        self.game = GameManager(database_path=self.path)
        self.game.player_name = "Ada"
        self.game._create_new_player()
        self.game.rng.seed(3)

    def tearDown(self):
        self.game.llm.close()
        self.folder.cleanup()

    # ------------------------------------------------------------------ helpers
    def stand_next_to(self, cell):
        world = self.game.world
        x, y = cell
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            if world.world.is_walkable((x + dx, y + dy)):
                world.avatar.x, world.avatar.y = world.world.cell_to_feet((x + dx, y + dy))
                world.avatar.facing = (-dx, -dy)
                world.update()
                return
        self.fail(f"nothing walkable next to {cell}")

    def press(self):
        self.game._overworld_key(E)

    def talk_through(self, target_id, choose_first=True):
        """Interact and click through the dialogue; returns once it closes (choosing option 1)."""
        world = self.game.world
        if target_id in world.objects:
            self.stand_next_to(world.objects[target_id]["pos"])
        else:
            npc = next(n for n in world.npcs if n.id == target_id)
            npc.state, npc.wait, npc.path = "working", 10 ** 6, []
            self.stand_next_to(npc.cell())
        self.assertEqual(world.target_id(), target_id)
        self.press()
        for _ in range(20):
            if not world.dialogue:
                return
            world.dialogue.age = 10 ** 6
            if world.dialogue.choices and world.dialogue.on_last_page and not choose_first:
                world.dialogue.selected = len(world.dialogue.choices) - 1
            self.press()

    def solve_open_challenge(self):
        screen = self.game.states.overlay
        screen.handle_key(pygame.K_RETURN)
        while screen.state == "question":
            screen.answer(screen.panel.question.answer)
            screen.handle_key(pygame.K_RETURN)
        self.assertTrue(screen.passed)
        screen.handle_key(pygame.K_RETURN)
        self.game._update()
        self.assertIsNone(self.game.states.overlay)

    def win(self, enemy, kind="wild"):
        game = self.game
        game._start_battle(enemy, kind)
        finish_battle(game.battle, limit=3000)
        game._update()
        return game

    # ------------------------------------------------------------------ the region
    def test_number_forest_from_start_to_boss_victory(self):
        game = self.game
        quests = game.quests
        self.assertEqual(quests.step_text("fading_numera"), "Meet Professor Numeris in Starter Village.")
        self.talk_through("rowan", choose_first=False)          # tutorial pages, then "Not now"
        self.assertEqual(quests.step_index("fading_numera"), 1)
        # A strong team so the test is about the flow, not grinding.
        for monster in game.party.party:
            monster.add_exp(5000)
        game.party.add(create("GEOMAX", 12))
        game.party.add(create("CHRONOX", 12))
        game.save_party()
        self.win(create("VOLTIX", 2))
        self.assertEqual(quests.step_index("fading_numera"), 2)
        game.world.teleport((70, 104))                            # the ruins
        self.assertEqual(game.world.area_id, "ridge")
        self.assertEqual(quests.step_index("fading_numera"), 3)
        # The arch stays sealed until the three puzzle gates are solved.
        self.talk_through("arch")
        self.assertIsNone(game.battle)
        for seal in ("seal_add", "seal_mul", "seal_frac"):
            self.talk_through(seal)
            self.assertEqual(type(game.states.overlay).__name__, "ChallengeScreen")
            self.solve_open_challenge()
        self.assertTrue(game.seals_done())
        self.assertEqual(quests.step_index("fading_numera"), 4)
        coins = game.repository.coins(game.player.player_id)
        self.talk_through("arch")                                 # "Face the beast!"
        self.assertEqual(game.state, "battle")
        self.assertEqual(game.battle.battle.kind, "boss")
        self.assertFalse(game.battle.battle.can_run)
        self.assertFalse(game.battle.battle.can_capture)
        finish_battle(game.battle, limit=4000)
        self.assertEqual(game.battle.outcome, "won")
        game._update()
        self.assertTrue(game.world.has_flag("boss:numerex"))
        self.assertEqual(quests.status("fading_numera"), "completed")
        self.assertTrue(game.world.has_flag("region:number_forest_complete"))
        self.assertGreaterEqual(game.repository.coins(game.player.player_id), coins + 300)
        self.stand_next_to(game.world.objects["portal_realm"]["pos"])
        self.assertIn("travel", game.world.prompt())               # the next region is open
        # Save and restore the adventure.
        game.save_all()
        again = GameManager(database_path=self.path)
        try:
            again._continue_game()
            self.assertEqual(again.quests.status("fading_numera"), "completed")
            self.assertEqual([m.species_id for m in again.party.party], [m.species_id for m in game.party.party])
            self.assertEqual(again.world.area_id, "ridge")
        finally:
            again.llm.close()

    def test_side_quests_unlock_the_bridge_and_the_evolution_shrine(self):
        game = self.game
        quests = game.quests
        # THE LOST NUMBERS: stones only answer once Mira has asked for help.
        self.talk_through("stone_1")
        self.assertIsNone(game.states.overlay)
        self.talk_through("mira")
        self.assertEqual(quests.status("lost_numbers"), "active")
        for stone in ("stone_1", "stone_2", "stone_3"):
            self.talk_through(stone)
            self.solve_open_challenge()
        potions = game.repository.inventory(game.player.player_id)["Health Potion"]
        self.talk_through("mira")
        self.assertEqual(quests.status("lost_numbers"), "completed")
        self.assertEqual(game.repository.inventory(game.player.player_id)["Health Potion"], potions + 3)
        # THE BROKEN BRIDGE: the desert is cut off until Bram's sums are done.
        desert = (104, 23)
        self.assertFalse(game.world.world.find_path(game.world.world.spawn, desert))
        game.world.teleport((88, 33))
        self.talk_through("bram")                                  # starts the quest and offers the plans
        self.assertEqual(type(game.states.overlay).__name__, "ChallengeScreen")
        self.solve_open_challenge()
        self.assertEqual(quests.status("broken_bridge"), "completed")
        self.assertTrue(game.world.world.find_path(game.world.world.spawn, desert))
        self.assertEqual(game.repository.inventory(game.player.player_id)["Stone Charm"], 1)
        # THE CRYSTAL SEAL gives the Evolution Crystal that wakes the shrine.
        game.world.teleport((1, 1))
        self.talk_through("evolution_shrine")
        self.assertIsNone(game.states.overlay)                     # dark without the crystal
        self.talk_through("crystal_seal")
        self.solve_open_challenge()
        self.assertEqual(quests.status("crystal_seal"), "completed")
        self.talk_through("evolution_shrine")
        shrine = game.states.overlay
        self.assertEqual(type(shrine).__name__, "EvolutionScreen")
        lead = game.party.party[0]
        shrine.activate(0)                                          # level 1: not eligible yet
        self.assertIn("Not yet", shrine.notice)
        lead.add_exp(4000)
        shrine.profile = {lead.mastery_topic: {"mastery": 80, "evidence": 12}}
        shrine.activate(0)
        self.assertTrue(shrine.confirming)                         # the player still has to choose
        shrine.handle_key(pygame.K_y)
        self.assertEqual(lead.evolution_stage, 2)
        saved = game.repository.load_party(game.player.player_id).party[0]
        self.assertEqual(saved.species_id, lead.species_id)
        self.assertEqual(saved.level, lead.level)


if __name__ == "__main__":
    unittest.main()

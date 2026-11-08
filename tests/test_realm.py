import os
import random
import tempfile
import unittest
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from game.creatures import BOSS, WILD_BY_NAME, encounter_for
from game.world_map import load_map

pygame.init()
E = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, unicode="", mod=0)


def reachable(world, start):
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nxt not in seen and world.is_walkable(nxt):
                seen.add(nxt)
                queue.append(nxt)
    return seen


class RealmMapTests(unittest.TestCase):
    def test_realm_is_fully_connected(self):
        world = load_map("crystal_realm")
        seen = reachable(world, world.spawn)
        for entry in world.data["interactables"]:
            x, y = entry["pos"]
            self.assertTrue(any(c in seen for c in ((x, y + 1), (x, y - 1), (x + 1, y), (x - 1, y))), entry["id"])
        for area in world.data["areas"]:
            self.assertIn(tuple(area["travel"]), seen, area["id"])
        for zone in world.data["encounters"]:
            x0, y0, w, h = zone["rect"]
            self.assertTrue(all((x, y) in seen for x in range(x0, x0 + w) for y in range(y0, y0 + h)), zone["rect"])

    def test_portals_arrive_on_reachable_ground(self):
        forest, realm = load_map(), load_map("crystal_realm")
        to_realm = next(e for e in forest.data["interactables"] if e["kind"] == "portal")
        home = next(e for e in realm.data["interactables"] if e["kind"] == "portal")
        self.assertIn(tuple(to_realm["arrive"]), reachable(realm, realm.spawn))
        self.assertIn(tuple(home["arrive"]), reachable(forest, forest.spawn))

    def test_secret_creature_is_never_a_random_encounter(self):
        rng = random.Random(1)
        for area in ("glimmer", "shardgrove", "starfall", "meadow", "nowhere"):
            for _ in range(200):
                self.assertNotEqual(encounter_for(area, rng).name, "GRAPHION")


class RealmGameTests(unittest.TestCase):
    def setUp(self):
        from game.game_manager import GameManager
        self.folder = tempfile.TemporaryDirectory()
        self.path = self.folder.name + "/realm.sqlite3"
        self.game = GameManager(database_path=self.path)
        self.game.player_name = "Explorer"
        self.game._create_new_player()

    def tearDown(self):
        self.game.llm.close()
        self.folder.cleanup()

    def stand_at(self, object_id):
        world = self.game.world
        x, y = world.objects[object_id]["pos"]
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            if world.world.is_walkable((x + dx, y + dy)):
                world.avatar.x, world.avatar.y = world.world.cell_to_feet((x + dx, y + dy))
                world.avatar.facing = (-dx, -dy)
                world.update()
                return
        self.fail(f"no space next to {object_id}")

    def use(self):
        self.game._overworld_key(E)
        if self.game.world.dialogue:
            self.game.world.dialogue.age = 10 ** 6

    def test_portal_wakes_after_numerex_and_travel_is_saved(self):
        game = self.game
        self.stand_at("portal_realm")
        self.assertIn("dormant", game.world.prompt())
        self.use()
        self.assertIn("dormant", game.world.dialogue.pages[0])
        game.world.close_dialogue()
        # Beat NUMEREX: the battle result sets the boss flag.
        game._start_battle(BOSS)
        game.battle.outcome, game.battle.closed = "won", True
        game._update()
        self.assertTrue(game.world.has_flag(game.BOSS_FLAG))
        self.stand_at("portal_realm")
        self.use()
        self.use()  # "Step through"
        self.assertEqual(game.world.world.map_id, "crystal_realm")
        self.assertEqual(game.player.world, "crystal_realm")
        self.assertIn(game.world.area_id, ("plaza", "bridges"))
        # Fog is tracked per map.
        self.assertTrue(any(f.startswith("chunk@crystal_realm:") for f in game.world.flags))
        # Continuing the save puts you back in the realm.
        from game.game_manager import GameManager
        again = GameManager(database_path=self.path)
        try:
            again._continue_game()
            self.assertEqual(again.world.world.map_id, "crystal_realm")
        finally:
            again.llm.close()
        # And the realm portal leads home.
        self.stand_at("portal_home")
        self.use()
        self.use()
        self.assertEqual(game.world.world.map_id, "number_forest")
        self.assertEqual(game.world.area_id, "ridge")

    def test_graphion_appears_only_after_the_star_chart(self):
        game = self.game
        game.player.world = "crystal_realm"
        game._enter_world()
        world = game.world
        self.assertFalse([r for r in world.roamers if r.spec.name == "GRAPHION"])
        world.set_flag("secret:starchart")
        for _ in range(31):
            world.update()
        graphions = [r for r in world.roamers if r.spec.name == "GRAPHION"]
        self.assertEqual(len(graphions), 1)
        self.assertEqual(world.world.area_at(world.world.to_cell(graphions[0].x, graphions[0].y - 2))[0], "starfall")

    def test_crystal_monsters_never_ask_easy_questions(self):
        game = self.game
        game._start_battle(WILD_BY_NAME["PRISMVOLT"])
        for _ in range(25):
            game.battle._start_question()
            self.assertNotEqual(game.battle.question.difficulty, "easy")
        game._start_battle(WILD_BY_NAME["GRAPHION"])
        for _ in range(10):
            game.battle._start_question()
            self.assertEqual(game.battle.question.difficulty, "advanced")

    def test_realm_screens_draw(self):
        from game.mathdex import MathDex
        from game.worldmap_screen import WorldMapScreen
        game = self.game
        game.player.world = "crystal_realm"
        game._enter_world()
        surface = pygame.Surface((320, 240))
        for frame in range(3):
            game.world.update(1, 0)
            game.world.draw(surface, frame)
        WorldMapScreen(game.world).draw(surface, 0)
        dex = MathDex(game.repository, game.player)
        for index in range(len(dex.entries())):
            dex.selected = index
            dex.draw(surface, index)


if __name__ == "__main__":
    unittest.main()

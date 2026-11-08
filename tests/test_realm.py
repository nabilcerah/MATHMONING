import os
import random
import tempfile
import unittest
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from game.world_map import load_map
from monsters import monster_factory
from world.encounter_manager import EncounterManager

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
        to_realm = next(e for e in forest.data["interactables"] if e["kind"] == "portal" and not e.get("door"))
        home = next(e for e in realm.data["interactables"] if e["kind"] == "portal")
        self.assertIn(tuple(to_realm["arrive"]), reachable(realm, realm.spawn))
        self.assertIn(tuple(home["arrive"]), reachable(forest, forest.spawn))

    def test_secret_creature_is_never_a_random_encounter(self):
        manager = EncounterManager(random.Random(1))
        for area in ("glimmer", "shardgrove", "meadow", "nowhere"):
            for _ in range(200):
                self.assertNotEqual(manager.pick(area)[0], "GRAPHION")
        self.assertTrue(EncounterManager.is_safe("starfall"))


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

    def win_boss(self):
        game = self.game
        game._start_battle(monster_factory.create("NUMEREX_BOSS", 10), "boss")
        game.battle.battle.enemy.hp = 0
        game.battle.battle.outcome, game.battle.battle.awaiting = "won", "over"
        game.battle.closed = True
        game._update()

    def test_portal_wakes_after_the_boss_and_travel_is_saved(self):
        game = self.game
        self.stand_at("portal_realm")
        self.assertIn("dormant", game.world.prompt())
        self.use()
        self.assertIn("dark", game.world.dialogue.pages[0])
        game.world.close_dialogue()
        self.win_boss()
        self.assertTrue(game.world.has_flag(game.BOSS_FLAG))
        self.stand_at("portal_realm")
        self.use()
        self.use()  # "Step through"
        self.assertEqual(game.world.world.map_id, "crystal_realm")
        self.assertEqual(game.player.world, "crystal_realm")
        self.assertIn(game.world.area_id, ("plaza", "bridges"))
        self.assertTrue(any(f.startswith("chunk@crystal_realm:") for f in game.world.flags))
        from game.game_manager import GameManager
        again = GameManager(database_path=self.path)
        try:
            again._continue_game()
            self.assertEqual(again.world.world.map_id, "crystal_realm")
        finally:
            again.llm.close()
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

    def test_crystal_realm_never_asks_foundation_questions(self):
        game = self.game
        game.player.world = "crystal_realm"
        game._enter_world()
        game._start_battle(monster_factory.create("PRISMVOLT", 11))
        battle = game.battle
        move = battle.moves()[0].move_id
        for _ in range(12):
            battle.choose_move(move)
            self.assertNotEqual(battle.panel.question.difficulty, "foundation")
            battle.handle_key(pygame.K_ESCAPE)

    def test_realm_screens_draw(self):
        from game.worldmap_screen import WorldMapScreen
        from states.dex_state import DexScreen
        game = self.game
        game.player.world = "crystal_realm"
        game._enter_world()
        surface = pygame.Surface((320, 240))
        for frame in range(3):
            game.world.update(1, 0)
            game.world.draw(surface, frame)
        WorldMapScreen(game.world).draw(surface, 0)
        dex = DexScreen(game)
        for index in range(len(dex.items())):
            dex.selected = index
            dex.draw(surface, index)


if __name__ == "__main__":
    unittest.main()

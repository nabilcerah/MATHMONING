import os
import random
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from database.database import Database
from database.player_repository import PlayerRepository
from game.overworld import Overworld
from game.player import Player
from game.world_map import load_map

pygame.init()


class OverworldTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repository = PlayerRepository(Database(self.folder.name + "/world.sqlite3"))
        player_id = self.repository.create_player("Walker", "PYROX", 34)
        record = self.repository.load_player()
        self.player = Player(record.name, record.creature, 1, 20, 34, 0, record.x, record.y, player_id)
        self.world = Overworld(self.player, random.Random(4), self.repository)

    def tearDown(self):
        self.folder.cleanup()

    def place(self, cell, facing):
        self.world.avatar.x, self.world.avatar.y = self.world.world.cell_to_feet(cell)
        self.world.avatar.facing = facing
        self.world.update()

    def face(self, cell):
        """Stand on a free tile next to ``cell`` and face it."""
        x, y = cell
        for (dx, dy) in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            front = (x + dx, y + dy)
            if self.world.world.is_walkable(front) and front != (x, y):
                self.place(front, (-dx, -dy))
                return front
        raise AssertionError(f"no free tile next to {cell}")

    def object_pos(self, object_id):
        return tuple(self.world.objects[object_id]["pos"])

    def press(self, key=pygame.K_e):
        return self.world.handle_key(key)

    def finish_dialogue(self):
        for _ in range(12):
            if not self.world.dialogue:
                return
            self.press()

    def test_every_waypoint_object_and_spawn_is_reachable(self):
        world = load_map()
        spawn = world.spawn
        for name, cell in world.waypoints.items():
            self.assertTrue(world.is_walkable(cell), name)
            self.assertTrue(world.find_path(spawn, cell) or cell == spawn, name)
        for entry in world.data["interactables"]:
            x, y = entry["pos"]
            fronts = [(x, y + 1), (x, y - 1), (x + 1, y), (x - 1, y)]
            self.assertTrue(any(world.is_walkable(c) and (world.find_path(spawn, c) or c == spawn) for c in fronts),
                            entry["id"])

    def test_walls_block_smooth_movement(self):
        self.place(self.world.world.spawn, (0, -1))
        for _ in range(120):
            self.world.update(-1, 0)
        # Walking into the village houses and the lake never leaves walkable ground.
        cell = self.world.avatar.cell()
        self.assertTrue(self.world.world.is_walkable(cell))
        for _ in range(200):
            self.world.update(0, -1)
        self.assertTrue(self.world.world.is_walkable(self.world.avatar.cell()))

    def test_chest_gives_item_only_once_and_persists(self):
        before = self.repository.inventory(self.player.player_id)["EXP Booster"]
        self.face(self.object_pos("chest_ridge"))
        self.assertEqual(self.world.target_id(), "chest_ridge")
        self.press()
        self.finish_dialogue()
        self.press()
        self.finish_dialogue()
        self.assertEqual(self.repository.inventory(self.player.player_id)["EXP Booster"], before + 1)
        reopened = Overworld(self.player, random.Random(1), self.repository)
        self.assertTrue(reopened.has_flag("opened:chest_ridge"))

    def test_talking_to_rowan_offers_a_battle(self):
        rowan = next(n for n in self.world.npcs if n.id == "rowan")
        rowan.state, rowan.wait = "working", 10 ** 6
        self.face(rowan.cell())
        self.assertEqual(self.world.target_id(), "rowan")
        self.press()
        self.assertEqual(rowan.state, "talking")
        self.press()  # reveal the typed text
        self.assertEqual(self.press(), "battle")
        self.assertIsNone(self.world.dialogue)
        self.assertNotEqual(rowan.state, "talking")

    def test_riddle_rewards_the_correct_answer_once(self):
        tamsin = next(n for n in self.world.npcs if n.id == "tamsin")
        tamsin.state, tamsin.wait = "working", 10 ** 6
        crystals = self.repository.inventory(self.player.player_id)["Learning Crystal"]
        self.face(tamsin.cell())
        self.assertEqual(self.world.target_id(), "tamsin")
        self.press()
        self.press()
        self.press(pygame.K_DOWN)  # "24"
        self.press()
        self.finish_dialogue()
        self.assertTrue(self.world.has_flag("riddle:tamsin"))
        self.assertEqual(self.repository.inventory(self.player.player_id)["Learning Crystal"], crystals + 1)

    def test_spring_restores_hp(self):
        self.face(self.object_pos("spring"))
        self.assertEqual(self.world.target_id(), "spring")
        self.press()
        self.assertEqual(self.player.hp, self.player.max_hp)

    def test_tall_grass_can_trigger_encounters(self):
        self.world.encounter_grace = 0
        events = []
        self.place((58, 71), (1, 0))  # the crop rows of Whisper Fields
        self.assertTrue(self.world.world.is_encounter((58, 71)))
        for i in range(2400):
            direction = -1 if (i // 60) % 2 == 0 else 1
            events.append(self.world.update(direction, 0))
        self.assertIn("encounter", events)

    def test_npcs_follow_their_routines(self):
        pip = next(n for n in self.world.npcs if n.id == "pip")
        start = (pip.x, pip.y)
        self.world.avatar.x, self.world.avatar.y = self.world.world.cell_to_feet(self.world.world.spawn)
        for _ in range(60 * 12):
            self.world.update()
        self.assertNotEqual((pip.x, pip.y), start)

    def test_overworld_draws_with_dialogue_and_bubbles(self):
        surface = pygame.Surface((320, 240))
        self.world.npcs[0].say("Hello!")
        self.world.draw(surface, 5)
        self.face(self.object_pos("sign_village"))
        self.press()
        for frame in range(3):
            self.world.update()
            self.world.draw(surface, frame)


class RoamerAndMapTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repository = PlayerRepository(Database(self.folder.name + "/roam.sqlite3"))
        player_id = self.repository.create_player("Catcher", "PYRON", 34)
        self.player = Player("Catcher", "PYRON", 3, 34, 34, 0, 16, 60, player_id)
        self.world = Overworld(self.player, random.Random(5), self.repository)

    def tearDown(self):
        self.folder.cleanup()

    def test_roamers_live_in_their_grass_and_match_its_habitat(self):
        self.assertGreaterEqual(len(self.world.roamers), len(self.world.zones))
        for _ in range(600):
            self.world.update()
        for roamer in self.world.roamers:
            cell = self.world.world.to_cell(roamer.x, roamer.y - 2)
            self.assertTrue(self.world.world.is_encounter(cell), roamer.spec.name)
            from game.creatures import WILD
            habitats = {area for spec in WILD for area in spec.habitat}
            # Zones in a habitat area spawn its residents; anywhere else falls back to meadow creatures.
            expected = roamer.zone["area"] if roamer.zone["area"] in habitats else "meadow"
            self.assertIn(expected, roamer.spec.habitat, roamer.spec.name)

    def test_rare_creatures_appear_once_at_a_time(self):
        for seed in range(12):
            world = Overworld(self.player, random.Random(seed), self.repository)
            names = [r.spec.name for r in world.roamers]
            self.assertLessEqual(names.count("CHRONOX"), 1, seed)

    def test_touching_a_roamer_battles_that_species_and_it_respawns(self):
        self.world.encounter_grace = 0
        roamer = self.world.roamers[0]
        roamer.target, roamer.wait = None, 10 ** 6
        self.world.avatar.x, self.world.avatar.y = roamer.x + 4, roamer.y
        self.assertEqual(self.world.update(), "encounter")
        self.assertIs(self.world.encounter_spec, roamer.spec)
        self.assertNotIn(roamer, self.world.roamers)
        count = len(self.world.roamers)
        self.world.respawns[0][0] = 1
        self.world.update()
        self.assertEqual(len(self.world.roamers), count + 1)

    def test_world_map_fog_and_fast_travel(self):
        from game.worldmap_screen import WorldMapScreen
        screen = WorldMapScreen(self.world)
        surface = pygame.Surface((320, 240))
        screen.draw(surface, 0)
        desert = next(i for i, a in enumerate(screen.areas) if a["id"] == "desert")
        screen.selected = desert
        screen.handle_key(pygame.K_RETURN)
        self.assertIn("on foot", screen.notice)  # not visited yet: no travel
        self.assertIsNone(screen.travel_to)
        self.world.set_flag("visited:desert")
        screen = WorldMapScreen(self.world)
        screen.selected = desert
        screen.handle_key(pygame.K_RETURN)
        cell, name = screen.travel_to
        self.world.teleport(cell)
        self.assertEqual(self.world.area_id, "desert")
        for key in (pygame.K_RIGHT, pygame.K_LEFT, pygame.K_DOWN):
            screen.handle_key(key)
            screen.draw(surface, 3)

    def test_fog_of_war_reveals_where_you_walk(self):
        far = (104, 23)  # the desert, far from the village spawn
        self.assertTrue(self.world.explored(self.world.world.spawn))
        self.assertFalse(self.world.explored(far))
        self.world.teleport(far)
        self.assertTrue(self.world.explored(far))
        reopened = Overworld(self.player, random.Random(1), self.repository)
        self.assertTrue(reopened.explored(far))  # saved with the game

    def test_every_travel_point_is_reachable(self):
        world = self.world.world
        for area in world.data["areas"]:
            cell = tuple(area["travel"])
            self.assertTrue(world.is_walkable(cell), area["id"])
            self.assertTrue(world.find_path(world.spawn, cell) or cell == world.spawn, area["id"])
            self.assertEqual(world.area_at(cell)[0], area["id"])


class PaintedWorldTests(unittest.TestCase):
    def test_every_region_is_reachable_from_the_village(self):
        world = load_map()
        reachable = {world.spawn}
        frontier = [world.spawn]
        while frontier:
            x, y = frontier.pop()
            for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nxt not in reachable and world.is_walkable(nxt):
                    reachable.add(nxt)
                    frontier.append(nxt)
        for area_id, name, (x0, y0, w, h) in world.areas:
            tiles = sum(1 for x in range(x0, x0 + w) for y in range(y0, y0 + h) if (x, y) in reachable)
            self.assertGreater(tiles, 50, name)

    def test_old_saves_restart_at_the_village(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = PlayerRepository(Database(folder + "/old.sqlite3"))
            player_id = repository.create_player("Old", "AQUABIT", 38)
            player = Player("Old", "AQUABIT", 6, 38, 38, 0, 34, 23, player_id)  # old tile-map coordinates
            world = Overworld(player, random.Random(2), repository)
            self.assertEqual((player.x, player.y), world.world.spawn)
            player.x, player.y = 37, 70
            again = Overworld(player, random.Random(2), repository)
            self.assertEqual((player.x, player.y), (37, 70))  # migrated saves keep their place


if __name__ == "__main__":
    unittest.main()

"""GDD 2.2 worlds 2-4 (Algebra Cavern, Geometry Kingdom, Chronos Dimension): map integrity, portals,
seals, bosses, quests and a playthrough of each world through the real GameManager."""
import os
import tempfile
import unittest
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from game.world_map import load_map
from mathematics import curriculum
from monsters.monster_data import challenges, encounters, has_species, quests, species
from monsters.monster_factory import create

WORLDS = ("algebra_cavern", "geometry_kingdom", "chronos_dimension")
CHAIN = ("number_forest",) + WORLDS
E = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, unicode="", mod=0)


def reachable(world):
    start = world.spawn
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nxt not in seen and world.is_walkable(nxt):
                seen.add(nxt)
                queue.append(nxt)
    return seen


def open_map(map_id):
    world = load_map(map_id)
    world.apply_flags({"bridge:repaired"})
    return world


class WorldDataTests(unittest.TestCase):
    def test_every_object_npc_and_grass_patch_is_reachable(self):
        for map_id in WORLDS:
            world = open_map(map_id)
            seen = reachable(world)
            for entry in world.data["interactables"]:
                x, y = entry["pos"]
                self.assertTrue(any(c in seen for c in ((x, y + 1), (x, y - 1), (x + 1, y), (x - 1, y))),
                                (map_id, entry["id"]))
            for name, cell in world.waypoints.items():
                self.assertIn(cell, seen, (map_id, name))
            for zone in world.data["encounters"]:
                x0, y0, w, h = zone["rect"]
                self.assertTrue(all((x, y) in seen for x in range(x0, x0 + w) for y in range(y0, y0 + h)), map_id)
            for area in world.data["areas"]:
                self.assertIn(tuple(area["travel"]), seen, (map_id, area["id"]))

    def test_portals_link_the_worlds_in_order_and_arrive_on_reachable_ground(self):
        for map_id in CHAIN + ("crystal_realm",):
            world = open_map(map_id)
            for entry in world.data["interactables"]:
                if entry["kind"] != "portal":
                    continue
                destination = open_map(entry["destination"])
                arrive = tuple(entry["arrive"])
                self.assertIn(arrive, reachable(destination), (map_id, entry["id"], arrive))
        for here, there in zip(CHAIN, CHAIN[1:]):
            targets = {e["destination"]: e for e in open_map(here).data["interactables"] if e["kind"] == "portal"}
            self.assertIn(there, targets, here)
            self.assertTrue(targets[there].get("requires", "").startswith("boss:"), here)

    def test_gates_seals_bosses_and_quests_are_consistent(self):
        for map_id in CHAIN:
            world = open_map(map_id)
            gate = next(e for e in world.data["interactables"] if e["kind"] == "boss_gate")
            self.assertTrue(species(gate["boss"]).boss, map_id)
            self.assertLessEqual(gate["level"], 20)
            objects = {e.get("challenge") for e in world.data["interactables"]}
            for flag in gate["seals"]:
                challenge = flag.split(":", 1)[1]
                self.assertIn(challenge, objects, (map_id, flag))
                self.assertIn(challenge, challenges())
            main = [q for q in quests().values() if q["category"] == "main" and
                    any(step.get("flag") == gate["flag"] for step in q["steps"])]
            self.assertEqual(len(main), 1, map_id)
        npc_ids = {n["id"] for m in CHAIN for n in open_map(m).data["npcs"]}
        object_ids = {e["id"] for m in CHAIN for e in open_map(m).data["interactables"]}
        for quest_id, quest in quests().items():
            if quest.get("giver"):
                self.assertIn(quest["giver"], npc_ids | object_ids, quest_id)

    def test_each_world_has_new_monsters_and_harder_levels(self):
        previous_low = 0
        for areas in (("meadow",), ("glow_tunnels", "echo_hollow"), ("garden_court", "pillar_court"),
                      ("tick_isles", "tock_isles")):
            lows = []
            for area in areas:
                table = encounters()["areas"][area]
                lows.append(table["levels"][0])
                self.assertLessEqual(table["levels"][1], 20)
                for sid, _ in table["table"]:
                    self.assertTrue(has_species(sid), sid)
                    self.assertFalse(species(sid).boss)
                    self.assertTrue(species(sid).sprite, sid)
            self.assertGreater(min(lows), previous_low)
            previous_low = min(lows)
        for sid in ("NULLSHADE", "INFERMATH", "CRYSTALGON", "VOLTBYTE", "GALAXION", "MYCOMORPH", "CHRONOWL",
                    "HEXABYTE", "SPHYNOX", "ARITHMORD"):
            monster = create(sid, 12)
            self.assertTrue(monster.moves(), sid)
            self.assertIn(monster.element, ("Crystal", "Earth", "Dark", "Time"))

    def test_region_topics_follow_the_gdd(self):
        self.assertIn("algebra", curriculum.REGION_TOPICS["algebra_cavern"])
        self.assertIn("geometry", curriculum.REGION_TOPICS["geometry_kingdom"])
        self.assertIn("sequences", curriculum.REGION_TOPICS["chronos_dimension"])


class WorldPlaythroughTests(unittest.TestCase):
    def setUp(self):
        from game.game_manager import GameManager
        self.folder = tempfile.TemporaryDirectory()
        self.game = GameManager(database_path=self.folder.name + "/worlds.sqlite3")
        self.game.player_name = "Explorer"
        self.game._create_new_player()
        for monster in self.game.party.party:
            monster.add_exp(10 ** 6)                     # level 20: the test is about the flow
        self.game.save_party()

    def tearDown(self):
        self.game.llm.close()
        self.folder.cleanup()

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

    def interact(self, target_id):
        world = self.game.world
        if target_id in world.objects:
            self.stand_next_to(world.objects[target_id]["pos"])
        else:
            npc = next(n for n in world.npcs if n.id == target_id)
            npc.state, npc.wait, npc.path = "working", 10 ** 6, []
            self.stand_next_to(npc.cell())
        self.assertEqual(world.target_id(), target_id)
        self.game._overworld_key(E)
        for _ in range(20):
            if not world.dialogue:
                return
            world.dialogue.age = 10 ** 6
            self.game._overworld_key(E)

    def solve_challenge(self):
        screen = self.game.states.overlay
        self.assertEqual(type(screen).__name__, "ChallengeScreen")
        screen.handle_key(pygame.K_RETURN)
        while screen.state == "question":
            floor = screen.spec["questions"][screen.index].get("min_difficulty")
            if floor:   # puzzle gates never ask below their floor
                self.assertGreaterEqual(curriculum.DIFFICULTIES.index(screen.panel.question.difficulty),
                                        curriculum.DIFFICULTIES.index(floor))
            screen.answer(screen.panel.question.answer)
            screen.handle_key(pygame.K_RETURN)
        self.assertTrue(screen.passed)
        screen.handle_key(pygame.K_RETURN)
        self.game._update()

    def beat_boss(self):
        game = self.game
        self.assertEqual(game.state, "battle")
        self.assertEqual(game.battle.battle.kind, "boss")
        game.battle.battle.enemy.hp = 0
        game.battle.battle.outcome, game.battle.battle.awaiting = "won", "over"
        game.battle.closed = True
        game._update()

    def travel(self, portal_id):
        self.interact(portal_id)

    def test_play_through_all_four_worlds(self):
        game = self.game
        game.world.set_flag("boss:numerex")                         # world 1 is covered by test_region_flow
        self.travel("cavern_entrance")
        cases = [
            ("algebra_cavern", "vexa", "unknown_guardian", ["seal_x1", "seal_x2", "seal_x3"], "lab_terminal",
             "algebra_cavern_forward", "geometry_kingdom", 2),
            ("geometry_kingdom", "hypot", "dimension_dragon", ["seal_g1", "seal_g2", "seal_g3"], "garden_plan",
             "geometry_kingdom_forward", "chronos_dimension", 0),
            ("chronos_dimension", "tick", "infinite_overlord", ["seal_t1", "seal_t2", "seal_t3"], "clock_shrine",
             "chronos_dimension_forward", "number_forest", 3),
        ]
        for map_id, npc, quest_id, seals, side, forward, next_map, wins in cases:
            with self.subTest(world=map_id):
                self.assertEqual(game.world.world.map_id, map_id)
                self.assertEqual(game.orchestrator.region, map_id)
                self.assertEqual(game.world.area_id, game.world.world.areas[0][0])   # arrival camp
                self.assertTrue(game.world.encounters.is_safe(game.world.area_id))
                self.interact(npc)
                self.assertEqual(game.quests.status(quest_id), "active")
                for _ in range(wins):
                    game._start_battle(create("PYRON", 10))
                    game.battle.battle.outcome, game.battle.battle.awaiting = "won", "over"
                    game.battle.closed = True
                    game._update()
                if quest_id == "dimension_dragon":
                    travel = next(a for a in game.world.world.data["areas"] if a["id"] == "pillar_court")["travel"]
                    game.world.teleport(tuple(travel))
                # The gate stays shut and the way on stays closed until the seals and the boss are done.
                gate_id = f"{map_id}_gate"
                self.interact(gate_id)
                self.assertNotEqual(game.state, "battle")
                self.interact(forward)
                self.assertEqual(game.world.world.map_id, map_id)
                for seal in seals:
                    self.interact(seal)
                    self.solve_challenge()
                self.assertTrue(game.seals_done())
                self.interact(side)
                self.solve_challenge()
                self.assertEqual(game.quests.status(quest_id), "active")      # still waiting for the boss
                self.interact(gate_id)                                  # "Face ...!"
                boss = game.battle.battle.enemy
                self.assertEqual(boss.species_id, game.boss_gate()["boss"])
                self.assertFalse(game.battle.battle.can_capture)
                self.beat_boss()
                self.assertEqual(game.quests.status(quest_id), "completed")
                self.assertIn(game.boss_gate()["victory"][:20], game.world.message)
                self.travel(forward)
                self.assertEqual(game.world.world.map_id, next_map)
        self.assertTrue(game.world.has_flag("game:complete"))
        self.assertEqual(game.world.area_id, "village")

    def test_defeat_in_a_new_world_wakes_you_at_its_camp(self):
        game = self.game
        game._travel_to_map("geometry_kingdom", (40, 30))
        game._start_battle(create("CRYSTALGON", 15))
        game.battle.battle.outcome, game.battle.battle.awaiting = "defeated", "over"
        game.battle.closed = True
        game._update()
        self.assertEqual(game.state, "recovery")
        self.assertEqual(game.player.world, "geometry_kingdom")
        self.assertEqual((game.player.x, game.player.y), tuple(game.world.world.safe_spot))
        game._draw()

    def test_new_worlds_draw(self):
        game = self.game
        surface = pygame.Surface((320, 240))
        for map_id in WORLDS:
            game._travel_to_map(map_id, tuple(load_map(map_id).spawn))
            for frame in range(3):
                game.world.update(1, 0)
                game.world.draw(surface, frame)
            from game.worldmap_screen import WorldMapScreen
            WorldMapScreen(game.world).draw(surface, 0)


if __name__ == "__main__":
    unittest.main()

"""GDD 28 CAPTURE: probability, success, failure, party and storage capacity, boss restriction."""
import random
import unittest

from combat.battle_manager import BattleError, BattleManager, DictInventory
from monsters import capture_manager
from monsters.monster_factory import create
from monsters.monster_party import MonsterParty, PartyError


class CaptureTests(unittest.TestCase):
    def test_probability_formula_and_clamps(self):
        self.assertEqual(capture_manager.capture_chance(0.2, True), 75)      # GDD example
        self.assertEqual(capture_manager.capture_chance(0.2, False), 60)
        self.assertEqual(capture_manager.capture_chance(1.0, False), 20)
        self.assertEqual(capture_manager.capture_chance(0.0, True), 85)
        self.assertEqual(capture_manager.capture_chance(-5, True), 85)

    def make(self, enemy="VOLTIX", party=None, storage=(), capsules=3, seed=1):
        party = MonsterParty(party or [create("FRACTELLA", 5)], list(storage))
        return BattleManager(party, create(enemy, 3), "wild", None, DictInventory({"Numeris Core": capsules}),
                             random.Random(seed))

    def test_success_adds_to_party_and_failure_consumes_the_capsule(self):
        results = {"captured": 0, "failed": 0}
        for seed in range(30):
            b = self.make(seed=seed)
            b.enemy.hp = 1
            topic = b.begin_capture()
            self.assertEqual(topic, "multiplication")     # VOLTIX's affinity
            events = b.resolve_capture(True)
            self.assertEqual(b.inventory.count("Numeris Core"), 2)
            if b.outcome == "captured":
                results["captured"] += 1
                self.assertIn(b.enemy, b.party.party)
                self.assertIn("You successfully captured VOLTIX!", [e["text"].split(" It ")[0] for e in events])
                self.assertEqual(b.rewards["placed"], "party")
            else:
                results["failed"] += 1
                self.assertEqual(events[-1]["text"], "The monster escaped the Numeris Core!")
                self.assertEqual(b.awaiting, "enemy")
        self.assertGreater(results["captured"], results["failed"])
        self.assertGreater(results["failed"], 0)

    def test_full_party_sends_captures_to_the_sanctuary(self):
        b = self.make(party=[create("FRACTELLA", 5), create("GEOMAX", 5), create("NUMEREX", 5)])
        b.enemy.hp = 1
        b.rng = random.Random(0)
        b.rng.random = lambda: 0.0          # guaranteed success
        b.begin_capture()
        b.resolve_capture(True)
        self.assertEqual(b.rewards["placed"], "storage")
        self.assertIn(b.enemy, b.party.storage)

    def test_no_room_no_capsule_or_boss_blocks_capture(self):
        full = self.make(party=[create("FRACTELLA", 5)] * 3, storage=[create("PYRON", 1)] * 20)
        with self.assertRaises(BattleError):
            full.begin_capture()
        empty = self.make(capsules=0)
        self.assertIn("no Numeris Cores", empty.capture_block_reason())
        party = MonsterParty([create("FRACTELLA", 5)])
        boss = BattleManager(party, create("NUMEREX_BOSS", 10), "boss", None, DictInventory({"Numeris Core": 5}))
        self.assertFalse(boss.can_capture)
        with self.assertRaises(BattleError):
            boss.begin_capture()
        trainer = BattleManager(MonsterParty([create("FRACTELLA", 5)]), create("VOLTIX", 3), "trainer", None,
                                DictInventory({"Numeris Core": 5}))
        self.assertIn("wild", trainer.capture_block_reason())


class PartyTests(unittest.TestCase):
    def test_party_limit_storage_and_transfers(self):
        party = MonsterParty([create("FRACTELLA")])
        self.assertEqual(party.add(create("GEOMAX")), "party")
        self.assertEqual(party.add(create("NUMEREX")), "party")
        self.assertEqual(party.add(create("CHRONOX")), "storage")
        self.assertEqual(len(party.party), 3)
        party.add(create("CHRONOX"))                     # duplicates are allowed
        self.assertEqual(len(party.storage), 2)
        with self.assertRaises(PartyError):
            party.withdraw(0)                            # party full
        incoming, outgoing = party.swap(0, 0)
        self.assertEqual((incoming.species_id, outgoing.species_id), ("CHRONOX", "FRACTELLA"))
        party.deposit(2)
        party.withdraw(0)
        self.assertEqual(len(party.party), 3)
        while not party.storage_full:
            party.add(create("PYRON"))
        self.assertEqual(len(party.storage), 20)
        self.assertTrue(party.storage_full)
        with self.assertRaises(PartyError):
            party.add(create("PYRON"))

    def test_you_always_keep_a_healthy_monster(self):
        party = MonsterParty([create("FRACTELLA"), create("GEOMAX")])
        party.party[1].hp = 0
        with self.assertRaises(PartyError):
            party.deposit(0)
        lone = MonsterParty([create("FRACTELLA")])
        with self.assertRaises(PartyError):
            lone.deposit(0)
        party.set_lead(1)
        self.assertEqual(party.lead.species_id, "FRACTELLA")    # the lead is the first HEALTHY monster


if __name__ == "__main__":
    unittest.main()

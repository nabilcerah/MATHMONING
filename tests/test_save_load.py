"""GDD 23 / 28 DATABASE: player creation, monster storage, party management, question history,
quest progress, shop transactions, legacy-save migration and save/load recovery."""
import random
import sqlite3
import tempfile
import unittest

from database.database import Database
from database.player_repository import PlayerRepository
from mathematics.question_generator import TemplateQuestionGenerator
from monsters.monster_factory import create
from world.quest_manager import QuestManager
from world.shop import Shop


class Base(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = self.folder.name + "/save.sqlite3"
        self.repository = PlayerRepository(Database(self.path))
        self.player_id = self.repository.create_player("Ada", "NUMEREX")

    def tearDown(self):
        self.folder.cleanup()

    def reopen(self):
        return PlayerRepository(Database(self.path))


class SaveLoadTests(Base):
    def test_new_player_has_the_starter_coins_and_items(self):
        party = self.repository.load_party(self.player_id)
        self.assertEqual([m.species_id for m in party.party], ["NUMEREX"])
        self.assertEqual(party.party[0].level, 1)
        self.assertEqual(self.repository.coins(self.player_id), 300)
        self.assertEqual(self.repository.inventory(self.player_id)["Basic Mathball"], 5)
        self.assertEqual(self.repository.capture_records(self.player_id)["NUMEREX"]["captured"], 1)

    def test_party_and_storage_survive_a_restart(self):
        party = self.repository.load_party(self.player_id)
        party.add(create("VOLTIX", 4))
        party.add(create("PYRON", 3))
        party.add(create("PYRON", 6))         # duplicate -> Sanctuary
        party.party[0].hp = 7
        party.set_lead(1)
        self.repository.save_party(self.player_id, party)
        loaded = self.reopen().load_party(self.player_id)
        self.assertEqual([m.species_id for m in loaded.party], ["VOLTIX", "NUMEREX", "PYRON"])
        self.assertEqual([m.level for m in loaded.storage], [6])
        self.assertEqual(loaded.party[1].hp, 7)
        self.assertEqual(self.reopen().load_player().creature, "VOLTIX")   # title screen shows the lead

    def test_question_history_feeds_mastery(self):
        generator = TemplateQuestionGenerator(random.Random(1))
        for score in (1.0, 1.0, 0.75, 0.0):
            q = generator.generate("integers", "foundation")
            self.repository.record_assessment(self.player_id, q, score > 0, score == 0.75, 1, score)
        profile = self.reopen().learning_profile(self.player_id)["integers"]
        self.assertEqual(profile["mastery"], round((1 + 1 + 0.75 + 0) / 4 * 100))
        self.assertEqual(profile["evidence"], 4)
        history = self.repository.question_history(self.player_id, "integers")
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["learning_score"], 0.0)

    def test_quest_progress_and_rewards_persist(self):
        quests = QuestManager(self.repository, self.player_id)
        quests.start_auto_quests()
        self.repository.set_world_flag(self.player_id, "met:rowan")
        messages, _ = quests.notify("battle_won")
        self.assertEqual(quests.step_index("fading_numera"), 1)
        messages, done = quests.notify("battle_won")
        self.assertEqual(quests.step_index("fading_numera"), 2)
        again = QuestManager(self.reopen(), self.player_id)
        self.assertEqual(again.step_index("fading_numera"), 2)
        # Completing a quest grants its fixed rewards exactly once.
        coins = self.repository.coins(self.player_id)
        quests.start("crystal_seal")
        self.repository.set_world_flag(self.player_id, "challenge:crystal_seal")
        messages, done = quests.notify("challenge", id="crystal_seal")
        self.assertEqual(done, ["crystal_seal"])
        self.assertEqual(self.repository.inventory(self.player_id)["Evolution Crystal"], 1)
        quests.notify("challenge", id="crystal_seal")
        self.assertEqual(self.repository.inventory(self.player_id)["Evolution Crystal"], 1)
        self.assertEqual(self.repository.coins(self.player_id), coins)    # crystal seal gives no coins
        self.assertEqual(QuestManager(self.reopen(), self.player_id).status("crystal_seal"), "completed")

    def test_shop_is_transactional(self):
        shop = Shop(self.repository, self.player_id)
        ok, _ = shop.buy("Basic Mathball")
        self.assertTrue(ok)
        self.assertEqual(self.repository.coins(self.player_id), 200)
        for _ in range(2):
            shop.buy("Basic Mathball")
        ok, message = shop.buy("Basic Mathball")
        self.assertFalse(ok)                                  # 0 coins left: nothing changes
        self.assertIn("Not enough", message)
        self.assertEqual(self.repository.coins(self.player_id), 0)
        self.assertEqual(self.repository.inventory(self.player_id)["Basic Mathball"], 8)
        self.assertFalse(shop.buy("Evolution Crystal")[0])   # quest items are never sold

    def test_failed_transactions_roll_back(self):
        party = self.repository.load_party(self.player_id)
        party.add(create("VOLTIX", 4))
        party.party[1].species_id = None     # an impossible row: NOT NULL fails mid-transaction
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save_party(self.player_id, party)
        loaded = self.repository.load_party(self.player_id)
        self.assertEqual([m.species_id for m in loaded.party], ["NUMEREX"])


class LegacyMigrationTests(unittest.TestCase):
    def test_pre_gdd_save_becomes_a_party(self):
        with tempfile.TemporaryDirectory() as folder:
            path = folder + "/old.sqlite3"
            repository = PlayerRepository(Database(path))
            with repository.database.connect() as db:
                db.execute("INSERT INTO players(name, creature, level, hp, max_hp, exp) VALUES ('Old', 'PYROX', 6, 30, 50, 12)")
                pid = db.execute("SELECT player_id FROM players").fetchone()[0]
                for species in ("VOLTIX", "DIVOWL", "FRACTELLA", "GHOSTLY"):
                    db.execute("INSERT INTO team_members(player_id, species, level, exp, hp, max_hp) VALUES (?, ?, 4, 3, 20, 30)",
                               (pid, species))
            party = repository.load_party(pid)
            self.assertEqual([m.species_id for m in party.party], ["PYRON", "VOLTIX", "DIVOWL"])
            self.assertEqual([m.species_id for m in party.storage], ["FRACTELLA"])    # unknown species dropped
            self.assertEqual(party.party[0].level, 6)
            self.assertEqual(repository.coins(pid), 300)
            self.assertEqual(len(repository.load_party(pid).party), 3)              # migrated only once


if __name__ == "__main__":
    unittest.main()


class ItemRenameMigrationTests(unittest.TestCase):
    def test_old_item_names_become_mathmart_items(self):
        with tempfile.TemporaryDirectory() as folder:
            path = folder + "/old_items.sqlite3"
            repository = PlayerRepository(Database(path))
            pid = repository.create_player("Old", "GEOMAX")
            with repository.database.connect() as db:
                db.execute("INSERT INTO inventory(player_id, item, quantity) VALUES (?, 'Health Potion', 4)", (pid,))
                db.execute("INSERT INTO inventory(player_id, item, quantity) VALUES (?, 'Math Capsule', 2)", (pid,))
            bag = PlayerRepository(Database(path)).inventory(pid)
            self.assertEqual(bag["Math Potion"], 3 + 4)
            self.assertEqual(bag["Basic Mathball"], 5 + 2)
            self.assertNotIn("Health Potion", bag)

    def test_mathmart_sells_the_requested_list_at_the_requested_prices(self):
        expected = {"Math Potion": 50, "Energy Potion": 40, "Full Restore": 150, "Basic Mathball": 100,
                    "Advanced Mathball": 250, "Attack Boost": 120, "Defence Boost": 120, "Revive Crystal": 200,
                    "Knowledge Tome": 200, "EXP Star": 300}
        self.assertEqual({name: info["price"] for name, info in Shop.stock()}, expected)

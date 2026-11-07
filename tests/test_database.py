import random
import tempfile
import unittest

from database.database import Database
from database.player_repository import PlayerRepository
from mathematics.question_generator import QuestionGenerator


class DatabaseTests(unittest.TestCase):
    def test_player_inventory_and_learning_data_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            path = folder + "/mathmon.sqlite3"
            repository = PlayerRepository(Database(path))
            player_id = repository.create_player("Mina", "AQUABIT", 38)
            question = QuestionGenerator(random.Random(2)).generate("easy", "addition")
            repository.record_attempt(player_id, question, question.answer, True)
            reopened = PlayerRepository(Database(path))
            self.assertEqual(reopened.load_player().name, "Mina")
            self.assertEqual(reopened.get_learning_profile(player_id)["addition"]["correct"], 1)
            self.assertEqual(repository.inventory(player_id)["Health Potion"], 3)
            self.assertTrue(repository.use_item(player_id, "Health Potion"))
            self.assertEqual(repository.inventory(player_id)["Health Potion"], 2)


if __name__ == "__main__":
    unittest.main()

"""GDD 28 PROGRESSION: EXP, level-up, stat growth, mastery and evolution eligibility."""
import unittest

from combat import battle_rules, reward_manager
from mathematics import mastery_manager
from monsters import evolution_manager
from monsters.monster import exp_to_next, max_level
from monsters.monster_data import species, starter_ids
from monsters.monster_factory import create


class ExpTests(unittest.TestCase):
    def test_exp_table(self):
        self.assertEqual([exp_to_next(level) for level in range(1, 6)], [60, 80, 100, 120, 140])
        self.assertEqual(battle_rules.battle_exp(6), 50)
        self.assertEqual(battle_rules.battle_exp(10, boss=True), 140)

    def test_level_up_grows_stats_and_current_hp(self):
        monster = create("FRACTELLA", 1)
        monster.hp -= 10
        levels = monster.add_exp(60)
        self.assertEqual([l["level"] for l in levels], [2])
        self.assertEqual(monster.exp, 0)
        self.assertEqual(monster.max_hp, 91)
        self.assertEqual(monster.hp, 81)                   # current HP rose by the same 6
        self.assertEqual((monster.attack, monster.defence, monster.speed), (17, 16, 13))

    def test_many_levels_at_once_and_the_cap(self):
        monster = create("GEOMAX", 1)
        monster.add_exp(sum(exp_to_next(level) for level in range(1, 6)) + 5)
        self.assertEqual(monster.level, 6)
        self.assertEqual(monster.exp, 5)
        monster.add_exp(10 ** 6)
        self.assertEqual(monster.level, max_level())
        self.assertEqual(monster.exp, 0)

    def test_shared_exp_skips_fainted_monsters(self):
        party = [create("FRACTELLA", 3), create("GEOMAX", 3), create("NUMEREX", 3)]
        party[2].hp = 0
        results = reward_manager.distribute_exp(party, party[0], 40)
        self.assertEqual([(m.species_id, gained) for m, gained, _ in results], [("FRACTELLA", 40), ("GEOMAX", 14)])

    def test_gdd_starter_stats(self):
        expected = {"FRACTELLA": (85, 15, 14, 12), "GEOMAX": (110, 14, 20, 7), "NUMEREX": (75, 19, 10, 17),
                    "CHRONOX": (85, 16, 13, 15)}
        self.assertEqual(starter_ids(), tuple(expected))
        for sid, stats in expected.items():
            s = species(sid).stats
            self.assertEqual((s["hp"], s["attack"], s["defence"], s["speed"]), stats)


class MasteryTests(unittest.TestCase):
    def test_rolling_window_of_twenty(self):
        self.assertEqual(mastery_manager.mastery_score([]), 0)
        self.assertEqual(mastery_manager.mastery_score([1.0, 0.75, 0.5, 0.0]), 56)
        history = [0.0] * 30 + [1.0] * 20
        self.assertEqual(mastery_manager.mastery_score(history), 100)   # only the last 20 count

    def test_bands_and_evidence(self):
        self.assertEqual(mastery_manager.band_for(30, 12), "Foundation")
        self.assertEqual(mastery_manager.band_for(55, 12), "Developing")
        self.assertEqual(mastery_manager.band_for(80, 12), "Proficient")
        self.assertEqual(mastery_manager.band_for(90, 12), "Mastered")
        self.assertEqual(mastery_manager.band_for(90, 9), "Proficient")   # Mastered needs 10 questions
        status = mastery_manager.status(100, 2)
        self.assertFalse(status.sufficient)
        self.assertIn("Gathering evidence", status.label)               # not shown as weak or strong
        self.assertEqual(mastery_manager.status(0, 0).label, "Not started")

    def test_learning_scores(self):
        self.assertEqual(battle_rules.learning_score("first_try"), 1.0)
        self.assertEqual(battle_rules.learning_score("after_hint"), 0.75)
        self.assertEqual(battle_rules.learning_score("second_attempt", worked_example=True), 0.5)
        self.assertEqual(battle_rules.learning_score("failed", worked_example=True), 0.0)


class EvolutionTests(unittest.TestCase):
    def test_needs_level_and_mastery_and_evidence(self):
        monster = create("FRACTELLA", 12)
        good = {"fractions": {"mastery": 60, "evidence": 10}}
        self.assertTrue(evolution_manager.check(monster, good).eligible)
        self.assertFalse(evolution_manager.check(create("FRACTELLA", 11), good).eligible)
        self.assertFalse(evolution_manager.check(monster, {"fractions": {"mastery": 59, "evidence": 30}}).eligible)
        missing = evolution_manager.check(monster, {"fractions": {"mastery": 90, "evidence": 9}})
        self.assertFalse(missing.eligible)
        self.assertEqual(len(missing.missing), 1)

    def test_evolving_keeps_progress_and_improves_stats_and_moves(self):
        for starter in starter_ids():
            monster = create(starter, 12)
            monster.exp = 33
            monster.hp -= 5
            before = (monster.max_hp, monster.attack, monster.defence)
            preview = evolution_manager.preview(monster)
            self.assertTrue(preview["gained_moves"])
            evolution_manager.evolve(monster)
            self.assertEqual(monster.species_id, species(starter).evolution["into"])
            self.assertEqual((monster.level, monster.exp), (12, 33))
            self.assertEqual(monster.evolution_stage, 2)
            self.assertGreater(monster.max_hp, before[0])
            self.assertGreaterEqual(monster.attack, before[1])
            self.assertEqual(monster.max_hp - monster.hp, 5)
            self.assertFalse(evolution_manager.check(monster, {}).target)   # ready for future stages


if __name__ == "__main__":
    unittest.main()

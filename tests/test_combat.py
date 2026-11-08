"""GDD 28 COMBAT: damage formula, elements, defence, Focus, switching, items, running, fainting, defeat."""
import random
import unittest

from combat import battle_rules, damage_calculator
from combat.battle_manager import BattleError, BattleManager, DictInventory
from combat.enemy_ai import EnemyAI
from monsters import elemental_system
from monsters.monster_factory import create
from monsters.monster_party import MonsterParty


def battle(player="FRACTELLA", enemy="VOLTIX", level=5, enemy_level=5, kind="wild", bag=None, mastery=50, seed=1,
           extra=()):
    party = MonsterParty([create(player, level)] + [create(s, level) for s in extra])
    return BattleManager(party, create(enemy, enemy_level), kind, lambda topic: mastery,
                         DictInventory(bag or {}), random.Random(seed))


class DamageFormulaTests(unittest.TestCase):
    def test_gdd_worked_example(self):
        # (16 + 0.5 x 15) x (100 / 128) x 1.0 x 1.04 x 1.0 = 19.09 -> 19
        # (The GDD text says "approximately 22"; the formula it specifies gives 19.09.)
        result = damage_calculator.calculate(16, 15, 14, 1.0, 70, 1.0)
        self.assertAlmostEqual(result.raw, 23.5 * (100 / 128) * 1.04)
        self.assertEqual(result.amount, 19)

    def test_defence_factor_and_mastery_multiplier(self):
        self.assertAlmostEqual(damage_calculator.defence_factor(0), 1.0)
        self.assertAlmostEqual(damage_calculator.defence_factor(50), 0.5)
        self.assertAlmostEqual(damage_calculator.mastery_multiplier(0), 0.9)
        self.assertAlmostEqual(damage_calculator.mastery_multiplier(100), 1.1)
        stronger = damage_calculator.calculate(20, 20, 5).amount
        weaker = damage_calculator.calculate(20, 20, 40).amount
        self.assertGreater(stronger, weaker)

    def test_answer_multipliers_and_minimum(self):
        self.assertEqual([battle_rules.answer_multiplier(o) for o in battle_rules.OUTCOMES], [1.0, 0.85, 0.75, 0.0])
        self.assertEqual(damage_calculator.calculate(1, 0, 999, 0.75).amount, 1)   # minimum 1 when it lands
        self.assertEqual(damage_calculator.calculate(30, 30, 10, 0.0).amount, 0)   # a miss does nothing

    def test_element_cycle(self):
        for attacker, target in (("Crystal", "Time"), ("Time", "Dark"), ("Dark", "Earth"), ("Earth", "Crystal")):
            self.assertEqual(elemental_system.multiplier(attacker, target), 1.5)
            self.assertEqual(elemental_system.multiplier(target, attacker), 0.75)
            self.assertEqual(elemental_system.message(attacker, target), "It's super effective!")
        self.assertEqual(elemental_system.multiplier("Crystal", "Dark"), 1.0)
        self.assertEqual(elemental_system.message("Crystal", "Dark"), "A normal attack!")
        self.assertEqual(elemental_system.message("Time", "Crystal"), "It's not very effective.")


class BattleFlowTests(unittest.TestCase):
    def test_correct_answer_deals_exact_formula_damage_and_builds_focus(self):
        b = battle("CHRONOX", "AQUABIT")         # Time vs Dark: super effective
        before = b.enemy.hp
        b.choose_move("pattern_swipe")
        events = b.resolve_move("first_try")
        expected = damage_calculator.calculate(16, b.active.attack, b.enemy.defence, 1.0, 50, 1.5).amount
        self.assertEqual(before - b.enemy.hp, expected)
        self.assertEqual(b.focus, 1)
        self.assertIn("super effective", events[0]["text"])
        self.assertEqual(b.awaiting, "enemy")

    def test_wrong_answer_does_nothing_but_the_enemy_still_acts(self):
        b = battle()
        hp = b.enemy.hp
        b.choose_move("crystal_shard")
        b.resolve_move("failed")
        self.assertEqual(b.enemy.hp, hp)
        self.assertEqual(b.focus, 0)
        player_hp = b.active.hp
        b.enemy_turn()
        self.assertLess(b.active.hp, player_hp)

    def test_specials_need_and_spend_focus(self):
        b = battle()
        with self.assertRaises(BattleError):
            b.choose_move("fraction_blast")
        b.focus = 3
        b.choose_move("fraction_blast")
        b.resolve_move("first_try")
        self.assertEqual(b.focus, 1)
        b.awaiting = "action"
        b.focus = 2
        b.choose_move("fraction_blast")
        b.resolve_move("failed")
        self.assertEqual(b.focus, 2)    # a missed special keeps its Focus

    def test_focus_caps_and_resets_each_battle(self):
        b = battle()
        for _ in range(5):
            b.awaiting = "action"
            b.choose_move("crystal_shard")
            b.resolve_move("first_try")
            b.enemy.hp = b.enemy.max_hp
        self.assertEqual(b.focus, 3)
        self.assertEqual(battle().focus, 0)

    def test_support_moves(self):
        b = battle("FRACTELLA", "PYRON")
        b.focus = 3
        b.choose_move("prism_shield")
        b.resolve_move("first_try")
        self.assertTrue(b.player_shield)
        hit = b.enemy_turn()[0]
        self.assertIn("halved", hit["text"])
        self.assertFalse(b.player_shield)
        c = battle("CHRONOX", "PYRON")
        c.focus = 1
        c.choose_move("temporal_shift")
        c.resolve_move("first_try")
        hp = c.active.hp
        self.assertIn("loses its turn", c.enemy_turn()[0]["text"])
        self.assertEqual(c.active.hp, hp)

    def test_switching_uses_the_turn_and_keeps_hp(self):
        b = battle(extra=("GEOMAX",))
        b.active.hp = 20
        b.switch(1)
        self.assertEqual(b.active.species_id, "GEOMAX")
        self.assertEqual(b.party.party[0].hp, 20)
        self.assertEqual(b.awaiting, "enemy")
        b.enemy_turn()
        with self.assertRaises(BattleError):
            b.switch(1)          # already battling

    def test_fainted_monsters_cannot_be_chosen_and_a_faint_forces_a_free_switch(self):
        b = battle(enemy_level=20, extra=("GEOMAX",))
        b.party.party[0].hp = 1
        b.choose_move("crystal_shard")
        b.resolve_move("failed")
        b.enemy_turn()
        self.assertEqual(b.awaiting, "switch")
        with self.assertRaises(BattleError):
            b.switch(0)
        b.switch(1)
        self.assertEqual(b.awaiting, "action")   # replacing a fainted monster is free

    def test_whole_team_fainting_is_a_defeat(self):
        b = battle(enemy_level=20)
        b.active.hp = 1
        b.choose_move("crystal_shard")
        b.resolve_move("failed")
        events = b.enemy_turn()
        self.assertEqual(b.outcome, "defeated")
        self.assertEqual(events[-1]["kind"], "defeat")

    def test_enemy_defeat_ends_the_battle_with_rewards(self):
        b = battle(level=5, enemy_level=4, extra=("GEOMAX",))
        b.enemy.hp = 1
        b.choose_move("crystal_shard")
        b.resolve_move("first_try")
        self.assertEqual(b.outcome, "won")
        self.assertEqual(b.awaiting, "over")
        self.assertEqual(b.rewards["coins"], battle_rules.battle_coins(4))
        gained = {monster.species_id: amount for monster, amount, _ in b.rewards["exp"]}
        self.assertEqual(gained["FRACTELLA"], battle_rules.battle_exp(4))       # 20 + 5 x 4 = 40
        self.assertEqual(gained["GEOMAX"], round(40 * 0.35))                    # shared training

    def test_items_consume_the_turn(self):
        b = battle(bag={"Health Potion": 1, "Focus Crystal": 1, "Revival Crystal": 1}, extra=("GEOMAX",))
        with self.assertRaises(BattleError):
            b.use_item("Health Potion")   # already at full HP
        b.active.hp = 10
        b.use_item("Health Potion")
        self.assertEqual(b.active.hp, 10 + round(b.active.max_hp * 0.3))
        self.assertEqual(b.awaiting, "enemy")
        b.awaiting = "action"
        b.use_item("Focus Crystal")
        self.assertEqual(b.focus, 2)
        b.awaiting = "action"
        b.party.party[1].hp = 0
        b.use_item("Revival Crystal", 1)
        self.assertEqual(b.party.party[1].hp, round(b.party.party[1].max_hp * 0.3))
        self.assertEqual(b.inventory.count("Health Potion"), 0)

    def test_running(self):
        self.assertEqual(battle_rules.escape_chance(10, 10), 50)
        self.assertEqual(battle_rules.escape_chance(30, 0), 90)
        self.assertEqual(battle_rules.escape_chance(0, 30), 20)
        boss = battle(enemy="NUMEREX_BOSS", kind="wild")
        self.assertEqual(boss.kind, "boss")
        with self.assertRaises(BattleError):
            boss.run()
        escapes = 0
        for seed in range(40):
            b = battle(seed=seed)
            events = b.run()
            escapes += events[0]["kind"] == "escape"
            if events[0]["kind"] == "escape_fail":
                self.assertEqual(b.awaiting, "enemy")
        self.assertTrue(0 < escapes < 40)

    def test_enemy_ai_is_deterministic(self):
        enemy = create("NUMEREX_BOSS", 10)
        ai = EnemyAI(boss=True)
        choices = [ai.choose(enemy, turn).move_id for turn in range(1, 6)]
        again = EnemyAI(boss=True)
        self.assertEqual(choices, [again.choose(enemy, turn).move_id for turn in range(1, 6)])
        self.assertIn("arithmetic_crush", choices)
        enemy.hp = 10
        self.assertEqual(EnemyAI(boss=True).choose(enemy, 1).effect, "shield")

    def test_passives(self):
        geo = battle("GEOMAX", "PYRON", mastery=100)
        plain = battle("GEOMAX", "PYRON", mastery=0)
        self.assertLess(geo.incoming_multiplier(geo.active), plain.incoming_multiplier(plain.active))
        frac = battle("FRACTELLA", "PYRON")
        for _ in range(4):
            frac.awaiting = "action"
            frac.choose_move("crystal_shard")
            frac.resolve_move("first_try")
            frac.enemy.hp = frac.enemy.max_hp
        self.assertAlmostEqual(frac.passive_power(frac.active, None), 1.15)


if __name__ == "__main__":
    unittest.main()

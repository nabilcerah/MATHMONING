"""Every advanced monster and battle mechanic, tested on the engine directly (no drawing)."""
import random
import unittest

from battle_engine.balance import BALANCE
from battle_engine.damage import Hit, resolve_player_hit
from battle_engine.engine import BattleEngine, PlayerCombatant
from battle_engine.monster_ai import AIState, Decision
from battle_engine.monster_data import build_stats, load_all
from battle_engine.progression import Trainer, available_ranks, battle_reward, is_unlocked, new_record
from battle_engine.tiers import level_for_rank, tier_for_level

EXPECTED = {"voltbyte", "nullshade", "mycomorph", "crystalgon", "chronowl", "galaxion", "infermath", "equinox",
            "arithmord", "hexabyte", "sphynox", "infinity_zero"}


def make(monster, level=14, seed=1, player_level=None, hp=400):
    player = PlayerCombatant.from_level("Hero", player_level or level, hp, hp, trainer_level=10)
    engine = BattleEngine(monster, level, player, random.Random(seed))
    engine.begin()
    return engine


def right(engine, topic=None, typed=False, elapsed=5):
    q = engine.next_question(topic)
    return engine.answer(q.answer, typed=typed, elapsed=elapsed)


def wrong(engine, topic=None):
    q = engine.next_question(topic)
    bad = next(c for c in q.choices if not q.check(c)) if q.kind == "choice" else "999999"
    return engine.answer(bad)


def no_crits(engine):
    engine.player.crit_chance = 0
    engine.stats.crit_chance = 0


class DataTests(unittest.TestCase):
    def test_all_twelve_monsters_load_with_required_fields(self):
        monsters = load_all()
        self.assertEqual(set(monsters), EXPECTED)
        for defn in monsters.values():
            self.assertTrue(defn.math_speciality and defn.weakness and defn.abilities and defn.special_ability)
            self.assertTrue(defn.mechanics or defn.phases, defn.id)
            for name in ("hp", "attack", "defence", "speed"):
                self.assertIn(name, defn.base_stats)

    def test_tiers_follow_the_level_bands(self):
        for level, tier in ((1, "common"), (9, "common"), (10, "uncommon"), (20, "uncommon"), (21, "rare"),
                            (35, "rare"), (36, "epic"), (49, "epic"), (50, "mythical"), (80, "mythical")):
            self.assertEqual(tier_for_level(level).id, tier, level)

    def test_stats_scale_with_level_and_rarity(self):
        defn = load_all()["crystalgon"]
        low, high = build_stats(defn, 5), build_stats(defn, 45)
        for name in ("max_hp", "attack", "defence", "exp_reward"):
            self.assertGreater(getattr(high, name), getattr(low, name), name)
        self.assertTrue(0 < high.crit_chance <= BALANCE["crit"]["cap"])
        self.assertGreater(high.special_power, high.attack)


class DamageTests(unittest.TestCase):
    def test_formula_and_clamps(self):
        settings = BALANCE["player_damage"]
        hit = resolve_player_hit(Hit(base=1000, weakness_mult=1.5, defence=10), 200, settings)
        self.assertEqual(hit.raw, round(200 * settings["max_fraction_of_max_hp"]))  # no one-shots
        tiny = resolve_player_hit(Hit(base=1, defence=500), 200, settings)
        self.assertEqual(tiny.raw, settings["min_damage"])
        zero = resolve_player_hit(Hit(base=50, answer_mult=0), 200, settings)
        self.assertEqual(zero.raw, 0)

    def test_weakness_beats_neutral_and_wrong_answers_do_no_damage(self):
        weak, plain = make("voltbyte", 12, 3), make("voltbyte", 12, 3)
        no_crits(weak), no_crits(plain)
        a = right(weak, "multiplication").hit.to_hp
        b = right(plain, "addition").hit.to_hp
        self.assertGreater(a, b)
        before = weak.monster_hp
        wrong(weak, "multiplication")
        self.assertEqual(weak.monster_hp, before)

    def test_no_single_answer_defeats_a_fresh_monster(self):
        for monster_id in EXPECTED:
            engine = make(monster_id, 30, 2, player_level=60)
            right(engine)
            self.assertGreater(engine.monster_hp, 0, monster_id)


class ShieldTests(unittest.TestCase):
    def test_crystal_shield_absorbs_and_geometry_breaks_it_faster(self):
        geo, other = make("crystalgon", 14, 4), make("crystalgon", 14, 4)
        no_crits(geo), no_crits(other)
        shield_geo, shield_other = geo.mechanic("shield"), other.mechanic("shield")
        self.assertTrue(shield_geo.up)
        r1 = right(geo, "geometry")
        r2 = right(other, "multiplication")
        self.assertGreater(r1.hit.to_shield, r2.hit.to_shield)
        self.assertLess(r1.hit.to_hp, r1.hit.raw)  # most damage was blocked
        while shield_geo.up:
            right(geo, "angles")
        self.assertTrue(geo.stunned)
        self.assertTrue(any(kind == "shield_break" for kind, _ in geo.log))

    def test_wrong_answers_repair_the_shield(self):
        engine = make("crystalgon", 14, 4)
        no_crits(engine)
        right(engine, "geometry")
        damaged = engine.mechanic("shield").hp
        wrong(engine, "geometry")
        self.assertGreater(engine.mechanic("shield").hp, damaged)

    def test_equinox_shield_only_breaks_with_equations(self):
        engine = make("equinox", 25, 5)
        shield = engine.mechanic("shield")
        right(engine, "multiplication")
        self.assertEqual(shield.hp, shield.max_hp)
        right(engine, "equations")
        self.assertLess(shield.hp, shield.max_hp)


class ChargeTests(unittest.TestCase):
    def charge(self, engine, ability_id):
        return engine._execute(Decision(AIState.PREPARE, engine.defn.ability(ability_id)))

    def test_correct_answer_interrupts_infermath(self):
        engine = make("infermath", 24, 6)
        events = self.charge(engine, "inferno_equation")
        self.assertEqual(events[0].kind, "charge")
        q = engine.next_question()
        self.assertEqual(engine.request.purpose, "interrupt")
        self.assertIn(q.topic, ("algebra", "equations"))
        engine.answer(q.answer)
        self.assertIsNone(engine.pending)
        self.assertTrue(engine.stunned)
        events = engine.monster_turn()
        self.assertEqual(events[0].kind, "stunned")

    def test_wrong_answer_lets_the_charge_hit_harder(self):
        normal = make("infermath", 24, 6)
        normal.ai.observe_first = False
        hp = normal.player.hp
        normal._execute(Decision(AIState.ATTACK, normal.defn.ability("ember_claw")))
        basic = hp - normal.player.hp
        engine = make("infermath", 24, 6)
        self.charge(engine, "inferno_equation")
        wrong(engine)
        hp = engine.player.hp
        events = engine.monster_turn()
        self.assertIn("release", [e.kind for e in events])
        self.assertGreater(hp - engine.player.hp, basic)

    def test_heat_grows_every_round(self):
        engine = make("infermath", 24, 6)
        heat = engine.mechanic("growth")
        for _ in range(3):
            engine.monster_turn()
        self.assertGreaterEqual(heat.stacks, 2)
        self.assertGreater(heat.multiplier, 1.2)

    def test_voltbyte_multistage_and_counter(self):
        engine = make("voltbyte", 14, 7)
        ability = engine.defn.ability("thunder_sequence")
        engine._execute(Decision(AIState.PREPARE, ability))
        wrong(engine)
        events = engine.monster_turn()
        self.assertEqual(events[0].kind, "stage")  # afterimages
        self.assertEqual(engine.pending.stage, 1)
        r = right(engine)
        self.assertIsNone(engine.pending)
        self.assertIn("Counter", [label for label, _ in r.hit.extras])

    def test_voltbyte_multistage_strikes_after_all_stages(self):
        engine = make("voltbyte", 14, 7)
        engine._execute(Decision(AIState.PREPARE, engine.defn.ability("thunder_sequence")))
        wrong(engine)
        engine.monster_turn()
        wrong(engine)
        kinds = [e.kind for e in engine.monster_turn()]
        self.assertIn("release", kinds)
        self.assertIsNone(engine.pending)

    def test_common_voltbyte_has_no_multistage(self):
        engine = make("voltbyte", 5, 7)
        self.assertNotIn("thunder_sequence", [a.id for a in engine.ai.usable()])

    def test_fast_strikes(self):
        engine = make("voltbyte", 14, 7)
        kinds = []
        for _ in range(4):
            kinds += [e.kind for e in engine.monster_turn()]
        self.assertIn("fast", kinds)


class SplitTests(unittest.TestCase):
    def test_mycomorph_splits_and_the_fraction_finds_the_target(self):
        engine = make("mycomorph", 14, 8)
        no_crits(engine)
        split = engine.mechanic("split")
        engine.monster_hp = int(engine.monster_max_hp * 0.52)
        right(engine, "fractions")
        self.assertTrue(split.hidden)
        hp_while_split = engine.monster_hp
        while split.hidden:
            q = engine.next_question()
            self.assertEqual(engine.request.purpose, "split_target")
            target = split.target
            self.assertTrue(q.answer.startswith(target["label"]))
            engine.answer(q.answer)
            self.assertFalse(target["alive"])
        self.assertLess(engine.monster_hp, hp_while_split)  # recoil when it reforms
        self.assertTrue(engine.stunned)

    def test_wrong_spore_is_a_decoy_and_spores_attack(self):
        engine = make("mycomorph", 14, 8)
        split = engine.mechanic("split")
        engine.monster_hp = int(engine.monster_max_hp * 0.5)
        split.after_answer(None, True, None, None, False)
        alive = len(split.alive())
        q = engine.next_question()
        engine.answer(next(c for c in q.choices if not q.check(c)))
        self.assertEqual(len(split.alive()), alive)
        hp = engine.player.hp
        kinds = [e.kind for e in engine.monster_turn()]
        self.assertIn("minion_attack", kinds)
        self.assertLess(engine.player.hp, hp)

    def test_mycomorph_cannot_be_defeated_before_splitting(self):
        engine = make("mycomorph", 14, 8)
        engine.monster_hp = 3
        right(engine, "fractions")
        self.assertGreater(engine.monster_hp, 0)
        self.assertTrue(engine.mechanic("split").hidden)


class TimelineTests(unittest.TestCase):
    def test_pattern_prediction_and_time_window(self):
        engine = make("chronowl", 16, 9)
        no_crits(engine)
        timeline = engine.mechanic("timeline")
        self.assertEqual([a.id for a in timeline.upcoming(3)], ["talon_strike", "talon_strike", "solar_flare"])
        right(engine, "addition")
        r = right(engine, "addition")
        self.assertIn("Foreseen", [label for label, _ in r.hit.extras])
        timeline.perform("time_lock", engine.defn.ability("time_lock"))
        engine.next_question()
        self.assertEqual(engine.request.purpose, "time")
        self.assertEqual(engine.question.topic, "sequences")
        fast = engine.answer(engine.question.answer, elapsed=10)
        self.assertIn("Rewind Strike", [label for label, _ in fast.hit.extras])
        timeline.perform("time_lock", engine.defn.ability("time_lock"))
        engine.next_question()
        slow = engine.answer(engine.question.answer, elapsed=999)
        self.assertGreater(slow.hit.raw, 0)  # late answers still count - no reaction-speed failure
        self.assertNotIn("Rewind Strike", [label for label, _ in slow.hit.extras])

    def test_attacks_follow_the_pattern(self):
        engine = make("chronowl", 16, 9)
        engine.ai.observe_first = False
        engine.cooldowns["time_lock"] = 99
        names = []
        for _ in range(3):
            for event in engine.monster_turn():
                if event.kind == "monster_hit":
                    names.append(event.data["ability"])
        self.assertEqual(names[:3], ["talon_strike", "talon_strike", "solar_flare"])


class OtherMechanicTests(unittest.TestCase):
    def test_nullshade_absorbs_wrong_answers_then_void_pulses(self):
        engine = make("nullshade", 8, 10)
        absorb = engine.mechanic("absorb")
        engine.monster_hp -= 30
        hp = engine.monster_hp
        for _ in range(3):
            wrong(engine)
        self.assertEqual(absorb.stacks, 3)
        self.assertGreater(engine.monster_hp, hp)
        decision = engine.ai.decide()
        self.assertEqual(decision.ability.id, "void_pulse")
        engine._execute(decision)
        self.assertEqual(absorb.stacks, 0)
        right(engine, "negative_numbers")

    def test_nullshade_counters_a_wrong_answer(self):
        engine = make("nullshade", 8, 10)
        engine.turn = 3
        wrong(engine)
        self.assertEqual(engine.ai.decide().state, AIState.COUNTER)

    def test_hexabyte_grows_exponentially_and_exponents_reset_it(self):
        engine = make("hexabyte", 38, 11)
        power = engine.mechanic("growth")
        for _ in range(3):
            power.end_round()
        self.assertAlmostEqual(power.multiplier, 1.3 ** 3)
        right(engine, "multiplication")
        self.assertEqual(power.stacks, 3)
        right(engine, "exponents")
        self.assertEqual(power.stacks, 0)

    def test_galaxion_gravity(self):
        engine = make("galaxion", 30, 12)
        gravity = engine.mechanic("gravity")
        start = gravity.gravity
        engine.monster_turn()
        self.assertEqual(gravity.gravity, start + 1)
        right(engine, "large_numbers")
        self.assertEqual(gravity.gravity, start)
        self.assertEqual(gravity.weaken, 1)

    def test_sphynox_barrier_blocks_until_logic_opens_it(self):
        engine = make("sphynox", 25, 13)
        barrier = engine.mechanic("barrier")
        hp = engine.monster_hp
        locks = barrier.locks
        q = engine.next_question("percentages")
        self.assertEqual(q.topic, "logic")  # the barrier insists on logic
        engine.answer(q.answer)
        self.assertEqual(engine.monster_hp, hp)
        self.assertEqual(barrier.locks, locks - 1)
        while barrier.up:
            right(engine)
        self.assertTrue(engine.stunned)
        right(engine, "percentages")
        self.assertLess(engine.monster_hp, hp)

    def test_arithmord_combo_prediction(self):
        engine = make("arithmord", 30, 14)
        combo = engine.mechanic("operation_combo")
        combo.perform("combo_expression", engine.defn.ability("operation_combo"))
        q = engine.next_question()
        self.assertEqual(engine.request.purpose, "predict")
        self.assertEqual(q.answer, str(combo.combo["value"]))
        engine.answer(q.answer)
        hp = engine.player.hp
        events = engine.monster_turn()
        self.assertEqual(engine.player.hp, hp)  # blocked
        self.assertIn("fizzles", events[0].text)
        combo.perform("combo_expression", engine.defn.ability("operation_combo"))
        wrong(engine)
        hp = engine.player.hp
        engine.monster_turn()
        self.assertLess(engine.player.hp, hp)


class InfinityZeroTests(unittest.TestCase):
    def test_three_phases_cannot_be_skipped_and_change_the_rules(self):
        engine = make("infinity_zero", 40, 15, player_level=80)
        self.assertEqual(engine.phase.current["id"], "distortion")
        self.assertEqual(engine.choice_count(), 5)
        self.assertFalse(engine.mechanic("shield").active)
        engine.monster_hp = engine.phase.next_threshold_hp() + 1
        right(engine)
        self.assertEqual(engine.phase.current["id"], "paradox")
        self.assertTrue(engine.mechanic("shield").up)  # the Paradox barrier
        self.assertIn("combined", engine.phase.topics())
        engine.mechanic("shield").hp = 0
        engine.monster_hp = engine.phase.next_threshold_hp() + 1
        right(engine, "equations")
        self.assertEqual(engine.phase.current["id"], "infinity")
        engine.next_question("mixed_operations")
        self.assertTrue(engine.typed_only())
        self.assertEqual(engine.phase.attacks_per_turn(), 2)
        hits = [e for e in engine._execute(Decision(AIState.ATTACK, engine.defn.ability("void_bite")))
                if e.kind == "monster_hit"]
        self.assertEqual(len(hits), 2)

    def test_damage_stops_at_each_phase_threshold(self):
        engine = make("infinity_zero", 40, 15, player_level=200)
        threshold = engine.phase.next_threshold_hp()
        engine.monster_hp = threshold + 2
        right(engine)
        self.assertEqual(engine.monster_hp, threshold)
        self.assertIsNone(engine.outcome)


class AITests(unittest.TestCase):
    def test_same_seed_same_decisions(self):
        def run(seed):
            engine = make("crystalgon", 14, seed)
            states = []
            for i in range(8):
                (right if i % 3 else wrong)(engine)
                engine.monster_turn()
                states.append(engine.ai.state)
            return states
        self.assertEqual(run(21), run(21))

    def test_ai_states_cover_the_state_machine(self):
        engine = make("crystalgon", 14, 3)
        self.assertEqual(engine.ai.decide().state, AIState.OBSERVE)
        engine.turn = 2
        engine.stunned = 1
        self.assertEqual(engine.ai.decide().state, AIState.STUNNED)
        engine.stunned = 0
        engine.mechanic("shield").hp = 0
        engine.mechanic("shield").turns_down = 5
        self.assertEqual(engine.ai.decide().state, AIState.DEFEND)
        engine.monster_hp = 0
        self.assertEqual(engine.ai.decide().state, AIState.DEFEATED)

    def test_struggling_students_face_fewer_big_charges(self):
        engine = make("infermath", 24, 3)
        charge = engine.defn.ability("inferno_equation")
        engine.answers = [("algebra", True)] * 4
        confident = engine.ai.score(charge)[0]
        engine.answers = [("algebra", False)] * 4
        self.assertLess(engine.ai.score(charge)[0], confident)


class ProgressionTests(unittest.TestCase):
    def test_full_battle_for_every_monster_and_rewards(self):
        for monster_id in EXPECTED:
            engine = make(monster_id, 14 if monster_id != "infinity_zero" else 24, 4)
            for _ in range(60):
                if engine.outcome:
                    break
                right(engine)
                if not engine.outcome:
                    engine.monster_turn()
            self.assertEqual(engine.outcome, "won", monster_id)
            record, trainer = new_record(monster_id), Trainer()
            rank = 2
            reward = battle_reward(engine, rank, record, trainer)
            self.assertTrue(reward.won and reward.first_clear and reward.trainer_xp > 0)
            self.assertEqual(record["rank"], rank)
            if engine.defn.boss:
                self.assertIn("Energy Potion", reward.items)

    def test_mastery_ranks_unlock_one_at_a_time(self):
        defn = load_all()["crystalgon"]
        self.assertEqual(available_ranks(defn, new_record("crystalgon")), [1])
        self.assertEqual(available_ranks(defn, {"rank": 2}), [1, 2, 3])
        boss = load_all()["infinity_zero"]
        self.assertEqual(available_ranks(boss, new_record("infinity_zero"))[0], 3)
        records = {name: {"wins": 1} for name in list(EXPECTED - {"infinity_zero"})[:5]}
        self.assertFalse(is_unlocked(boss, records))
        records[sorted(EXPECTED - {"infinity_zero"} - set(records))[0]] = {"wins": 1}
        self.assertTrue(is_unlocked(boss, records))

    def test_trainer_levels_unlock_skills(self):
        engine = make("voltbyte", 5, 1)
        engine.trainer_level = 1
        self.assertEqual([s.id for s in engine.skills], ["focus"])
        engine.trainer_level = 9
        self.assertEqual(len(engine.skills), 5)
        engine.use_skill("mind_surge")
        r = right(engine)
        self.assertTrue(r.hit.critical)
        engine.use_skill("second_chance")
        r = wrong(engine)
        self.assertTrue(r.forgiven)
        self.assertFalse(engine.last_wrong)

    def test_rank_levels_sit_inside_their_tier(self):
        for rank in range(1, 6):
            for player_level in (1, 15, 60):
                level = level_for_rank(rank, player_level)
                self.assertEqual(tier_for_level(level).rank, rank)


if __name__ == "__main__":
    unittest.main()

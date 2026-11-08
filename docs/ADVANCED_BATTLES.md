# Advanced monster battles (Monster Trials)

Press **T** in the overworld to open the Monster Trials hall. Every monster is a different maths boss.

## Architecture

```
data/monsters/*.json        one file per monster (stats, weakness, abilities, mechanics, phases)
data/balance.json           OPTIONAL overrides for battle_engine/balance.py (any subset of keys)
battle_engine/              rules only - no pygame
  balance.py                every tunable number (tiers, growth, damage multipliers, clamps, XP, animation fps)
  tiers.py                  Common 1-9, Uncommon 10-20, Rare 21-35, Epic 36-49, Mythical 50+
  monster_data.py           JSON loader + stat formulas (base stats at the JSON "level", scaled by level and tier)
  damage.py                 BaseAtk x Answer x Weakness x Critical x extras - Defence, clamped
  monster_ai.py             deterministic state machine (Idle/Observe/Prepare/Attack/Defend/Counter/Special/Stunned/Defeated)
  phases.py                 HP-threshold phases; damage can't skip a phase
  mechanics/                one plug-in per mechanic (shield, growth, absorb, split, timeline, gravity,
                            barrier, operation_combo, fast_strikes, rule_shift)
  engine.py                 BattleEngine: next_question() -> answer() -> monster_turn(), returns Events
  skills.py, progression.py trainer skills, trainer XP/levels, mastery ranks, rewards
mathematics/question_engine/ deterministic questions for 17 topics; every answer re-proved before use
game/monster_battle.py      the battle screen (draws the engine, plays animations, explains results)
game/trials_screen.py       collection / challenge hall
game/animation.py           sprite-sheet animation player + placeholder effects
tools/process_monster_sprites.py   slices the 3x3 sheets (rows: idle, walk, attack)
```

LLMs are never used for answers or damage. Answers are generated and checked with exact `Fraction`
arithmetic; damage and AI decisions are deterministic for a seeded `random.Random`.

## Adding a monster

1. Put its 3x3 sheet in `assets/monsterassets/` (row 1 idle, row 2 walk, row 3 attack).
2. Add it to `SHEETS` and `ROW_LAYOUT` in `tools/process_monster_sprites.py` and run
   `python tools/process_monster_sprites.py NAME --preview`.
3. Copy a file in `data/monsters/` and edit it. Mechanics are listed by `type`; abilities by `type`
   (`attack`, `charge`, `multistage`, `special`, `defend`, `counter`) with optional `min_tier`,
   `phases`, `hp_below`, `cooldown`, `interrupt_topics`, `stages`.
4. Run the tests: `tests/test_advanced_battle.py` checks every monster loads and can be beaten.

## Balancing

Create `data/balance.json` with only what you want to change, e.g.

```json
{"monster_hp_mult": 1.2, "player_damage": {"weakness": 1.75}, "animation": {"speed_scale": 0.8}}
```

The simulation used during development fights every monster at every tier with 100% / 75% / 50%
accurate players; at the defaults a perfect player wins in roughly 4-12 turns, a 75% player
usually wins, and a 50% player usually loses - so improving at maths is what wins.

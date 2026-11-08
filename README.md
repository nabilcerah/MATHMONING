# MATHMON

**Train Your Mind. Evolve Your Power.** An 8-bit monster-collecting RPG where every attack is a maths
question, and an agentic AI personalises the learning. The full design is in [GDD.md](GDD.md); the phase
checklist is in [docs/DEV_CHECKLIST.md](docs/DEV_CHECKLIST.md).

## Play

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python main.py
```

| Key | Action |
|---|---|
| WASD / arrows | Move, choose |
| E / Enter | Talk, interact, confirm |
| Tab | Trainer menu (party, bag, quests, Codex, MathDex, profile, save) |
| Esc | Pause / back |
| 1–4 | Menu shortcuts (battle actions, moves) |
| H / W | Hint / worked example while answering |
| N / T / M | World map / Monster Trials / MathDex |
| F11 | Fullscreen |

Menus also work with the mouse.

## What's in the first region (Number Forest)

- **Choose a starter:** FRACTELLA (Crystal, fractions), GEOMAX (Earth, geometry), NUMEREX (Dark, integers) or
  CHRONOX (Time, algebra/sequences).
- **Battles:** FIGHT / MONSTER / BAG / RUN. Each move asks a question on its topic. First-try answers hit
  hardest, a hint costs a little, and a second try still lands.
- **Collect and train:** Math Capsules capture weakened wild monsters. Your party holds three; the Monster
  Sanctuary stores twenty more. Monsters evolve at the shrine when they reach level 12 *and* you've mastered
  their topic.
- **Quests:** restore the three Numera Seals and defeat THE ARITHMETIC BEAST, find Mira's lost numbered
  stones, rebuild Bram's bridge to the desert, wake the Crystal Seal, and decode the rune tablet.
- **Beyond the forest:** beat the Arithmetic Beast and a cave opens in the ruins, leading to the **Algebra Cavern**,
  then the **Geometry Kingdom** and the **Chronos Dimension** (GDD worlds 2–4). Each world has its own camp,
  monsters, seals, side quest and boss.
- **Village services:** the MATHMART sells potions, Mathballs, boosts, Knowledge Tomes and EXP Stars; the
  MATHMON RECOVERY CENTER heals your team when you solve Nurse Hana's problems.
- **Hints you can see:** press H while answering and an animated picture (number line, fraction bars, balance
  scale, shapes...) shows the strategy.
- **The story:** a prologue, four chapters and a final chapter with three endings, told in pixel dialogue
  boxes (portraits, typewriter text, choices; ESC skips ahead). Find historical records in every world, uncover
  what Professor Numeris has been hiding, and learn who the hooded stranger is. Everything you learn goes into
  the **Codex (Tab → Codex)**: world history, characters, every MathMon, regions, records and the main story.
  The lore bible is [docs/LORE.md](docs/LORE.md); the story data lives in `data/story/`.
- **Learning profile (Tab → Profile):** mastery per topic, your history, and the AI log showing every
  agent decision step by step.

## The AI

A central orchestrator runs five agents: Question Generator, Learning Analyst, Difficulty Manager,
AI Tutor and Game Master. It works fully offline. Add `ANTHROPIC_API_KEY` to `.env` (see `.env.example`)
for a live tutor voice. The AI only ever changes learning data. HP, damage, EXP, items, captures and quests
are decided by deterministic rules in `combat/`, `monsters/` and `world/`, configured in `data/*.json`.

## Develop

```
.venv/Scripts/python -m pip install -r requirements-dev.txt pytest
.venv/Scripts/python -m pytest
```

- `tools/make_variants.py` regenerates the recoloured sprites (evolutions, bosses, Crystal Realm forms).
- `tools/generate_worlds.py` regenerates the Algebra Cavern, Geometry Kingdom and Chronos Dimension maps.
- `tools/process_building_art.py` turns the Mathmart / Recovery Center art into interiors, frames and exteriors.
- `tools/generate_audio.py` regenerates the music and sound effects.
- `tools/build_web.py` builds the browser version.

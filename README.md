# MATHMON

**Train your mind. Evolve your power.**

MATHMON is an 8-bit monster-collecting RPG where every attack is a maths question and every correct answer makes your partner stronger. Pick a starter, explore the Number Forest, befriend wild MATHMON, and grow from your first practice battle to facing bosses that bend the rules of the fight.

It is built for learners aged 12 to 17 (and anyone who still loves a good RPG). It plays fully on your own computer or in the browser: no account and no internet needed. Behind the scenes, a team of AI agents watches how you learn and shapes the next challenge for you.

The full design is in [GDD.md](GDD.md), and the phase checklist is in [docs/DEV_CHECKLIST.md](docs/DEV_CHECKLIST.md).

## The adventure

You are a new trainer in **Number Forest**. Professor Numeris is waiting in the village. Tall grass hides wild MATHMON, and signs, chests and puzzle shrines dot the trail. Deep in the ruins, **THE ARITHMETIC BEAST** guards an old stone gate sealed by the three Numera Seals.

Beat it and a cave opens in the ruins. It leads to the **Algebra Cavern**, then the **Geometry Kingdom** and the **Chronos Dimension**. Each world has its own camp, monsters, seals, side quest, boss and music.

Along the way you can:

- **Choose a starter:** FRACTELLA (Crystal, fractions), GEOMAX (Earth, geometry), NUMEREX (Dark, integers) or CHRONOX (Time, algebra and sequences).
- **Collect and train:** throw Math Capsules at weakened wild monsters. Your party holds three, and the Monster Sanctuary keeps twenty more. Monsters evolve at the shrine when they reach level 12 *and* you have mastered their topic.
- **Follow quests:** restore the Numera Seals, find Mira's lost numbered stones, rebuild Bram's bridge to the desert, wake the Crystal Seal and decode the rune tablet.
- **Visit the village:** the MATHMART sells potions, Mathballs, boosts, Knowledge Tomes and EXP Stars. At the MATHMON RECOVERY CENTER, Nurse Hana heals your team when you solve her problems.
- **Uncover the story:** a prologue, four chapters and a final chapter with three endings, told in pixel dialogue boxes. Find the historical records in every world, discover what Professor Numeris has been hiding, and learn who the hooded stranger is. Everything you learn goes into the **Codex**.
- **Hunt the Monster Trials:** twelve unique bosses roam the worlds, each with its own maths weakness, battle phases and tricks, and five mastery ranks to climb. Walk into one to battle it; the Trials catalogue (T) shows the ones you have met and hints where the others roam.
- **Duel rivals in the Math Arena:** a best-of-five race where the first correct answer wins the round.
- **Fill your MathDex** with every monster you have seen and befriended.

Questions grow harder as your team levels up, and your active quests sit in the top-right corner with how far away the next objective is.

Wrong answers are part of the journey. A hint costs a little, a second try still lands, and press **H** to see an animated picture of the strategy: a number line, fraction bars, a balance scale or shapes. If your team faints, Sage Ilo carries everyone back to the Sanctuary. Nothing you caught or learned is lost.

## How to play

| Key | Action |
|---|---|
| WASD / arrows | Move, choose |
| E / Enter / Space | Talk, interact, confirm |
| Tab | Trainer menu (party, bag, quests, Codex, MathDex, profile, save) |
| Esc | Pause / back |
| 1–4 | Menu shortcuts (battle actions, moves) |
| H / W | Hint / worked example while answering |
| N / T / M / J | World map / Trials catalogue / MathDex / show-hide quest tracker |
| F11 | Fullscreen |

Menus also work with the mouse. On a phone, on-screen buttons appear so you can play with a tap.

In battle, choose **FIGHT / MONSTER / BAG / RUN**. Each move asks a question on its own topic, and first-try answers hit hardest.

## What you practise

Addition, subtraction, multiplication, division, fractions, ratios, integers, algebra, geometry and sequences across the main adventure. The Monster Trials add negatives, large numbers, percentages, angles, equations, exponents, order of operations and logic.

Every question is generated and checked by the game itself with exact arithmetic, so the answer is always fair. No AI ever writes a question or decides whether you were right.

## The AI

MATHMON uses a **multi-agent AI**. A central orchestrator runs five rule-based agents:

| Agent | What it does |
|---|---|
| Question Generator | Picks the topic and difficulty and serves only verified questions |
| Learning Analyst | Tracks mastery, accuracy, hint use and repeated misconceptions |
| Difficulty Manager | Moves difficulty up or down one band at a time, with safeguards |
| AI Tutor | Progressive hints, feedback on mistakes, worked examples on new numbers |
| Game Master | Recommends quests, training spots and boss readiness |

On top of them sits **Agent 6, the AI Planner**, an LLM agent powered by Claude. It is given a goal ("plan this learner's next step") and decides by itself which agents to call as tools, reads the results, and submits a plan. The game validates every plan against the rules: a rejected plan goes back to Claude with the reason so it can correct itself. An accepted plan steers the next few questions.

Open **Tab → Profile → AI LOG** to watch every decision step by step, including each tool call the planner made.

The AI only ever changes *learning* data. HP, damage, EXP, items, captures and quests are decided by deterministic rules in `combat/`, `monsters/` and `world/`, configured in `data/*.json`. Without an API key everything still works offline, using the rule-based agents.

### Turning on the live AI (optional)

Copy `.env.example` to `.env` and add your [Anthropic](https://www.anthropic.com/) key:

```
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_MODEL=claude-haiku-5-5
MATHMON_AI_MODE=hybrid
```

`MATHMON_AI_MODE` can be `offline`, `live` or `hybrid`. Only the maths question, the answer and learning statistics are sent, never the player's name. The browser build always runs offline, so a key is never shipped inside the web page.

## Play it

You need Python 3.

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python main.py
```

Your save lives in `saves/mathmon.sqlite3`.

### In the browser

```
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python tools/build_web.py --serve
```

Open `http://127.0.0.1:8000`. Running `tools/build_web.py` without `--serve` writes the upload folder `build/mathmon/build/web`, which is what Vercel publishes (`vercel --prod` from that folder). In the browser, saves are kept in the page's local storage.

## Develop

```
.venv/Scripts/python -m pip install -r requirements-dev.txt pytest
.venv/Scripts/python -m pytest
```

- `tools/make_variants.py` regenerates the recoloured sprites (evolutions, bosses, Crystal Realm forms).
- `tools/generate_worlds.py` regenerates the Algebra Cavern, Geometry Kingdom and Chronos Dimension maps.
- `tools/process_building_art.py` turns the Mathmart and Recovery Center art into interiors, frames and exteriors.
- `tools/generate_audio.py` regenerates the music and sound effects.
- `tools/process_monster_sprites.py` slices raw monster sheets into animation frames.
- `tools/build_web.py` builds the browser version.

## What is in the box

```
main.py            start here
game/              the adventure: overworld, battles, MathDex, arena, trials, touch controls
states/            menus and screens (party, bag, quests, Codex, profile, shop...)
world/             maps, quests and world rules
monsters/          species, evolution and party rules
combat/            battle rules (damage, EXP, captures)
battle_engine/     Monster Trials rules (no drawing, just the fight)
mathematics/       question templates and the exact answer checker
ai/                the orchestrator, five rule-based agents and the AI Planner
database/          your trainer, team and progress
data/              maps, monsters, moves, quests, items and the story
assets/            sprites, backgrounds, fonts, music and sounds
tools/             web build, sprite, map and audio helpers
docs/              Monster Trials guide, lore bible and dev checklist
```

Curious how a Trial boss thinks? [docs/ADVANCED_BATTLES.md](docs/ADVANCED_BATTLES.md) is the field guide. For the world's history and characters, read [docs/LORE.md](docs/LORE.md).

Go on. The tall grass is moving.

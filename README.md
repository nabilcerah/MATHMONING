# MATHMON

**Train your mind. Evolve your power.**

MATHMON is a little pixel adventure where every battle is a maths question and every correct answer makes your creature stronger. You pick a starter, wander the Number Forest, befriend wild MATHMON, and grow from counting on your fingers to taking on bosses that bend the rules of the fight.

It is built for curious kids (and anyone who still likes a good RPG), and it plays fully on your own computer. No account. No internet required. Just you, your partner, and the next problem.

## The adventure

You are a new ranger in **Number Forest**. Professor Numeris is waiting in Lakeside Village with a practice battle and a smile. Tall grass hides wild MATHMON. Signs, chests, springs, and puzzle shrines dot the trail. Somewhere in the Shadow Ruins, **NUMEREX**, the Arithmetic Beast, guards an old stone gate.

Beat NUMEREX and a crystal portal wakes. Step through into the **Crystal Realm**, a brighter world of stronger creatures and harder questions. When you want a real challenge, press **T** and walk into the **Monster Trials**: twelve unique bosses, each with its own maths weakness, phases, and battle tricks.

Along the way you can:

- Choose a starter — fiery **PYRON**, calm **AQUABIT**, or sturdy **GEOMAX** — and watch it evolve as you practise.
- Meet wild friends in the grass (VOLTIX, DIVOWL, FRACTELLA, and a few rare surprises) and welcome them onto your team.
- Solve shrine puzzles, rest at springs, and open chests for potions and boosters.
- Duel rivals in the **Math Arena**, a best-of-five race where the first correct answer wins the round.
- Keep a **MathDex** of everyone you have seen and befriended.

Wrong answers are part of the story. Miss three times and your mentor walks the question with you, one short step at a time. A lost battle sends you back to the trail with your progress safe.

## What you practise

Questions are written and checked by the game itself, with exact arithmetic, so the answer is always fair.

On the trail you will meet addition, subtraction, multiplication, division, fractions, place value, shapes, and time and money. The game notices which topics need a little more love and gently steers the next fight that way.

Monster Trials go further: negatives, large numbers, percentages, geometry, angles, algebra, equations, sequences, exponents, order of operations, and logic. Every question is proved before it ever appears on screen.

## How to play

| | |
|---|---|
| Move | Arrow keys or **W A S D** |
| Talk, read, open, enter | **E**, **Enter**, or **Space** |
| Practice battle | **B** |
| World map | **N** |
| MathDex | **M** or **Tab** |
| Monster Trials | **T** |
| Save and return to the menu | **Esc** |
| Full screen | **F11** or **Alt+Enter** |

In a battle, pick an action and type your answer.

- **ATTACK** throws a question (sometimes a quick puzzle). A correct answer hits.
- **SKILLS** let you choose the topic once your creature reaches level 2.
- **ITEMS** are potions, EXP boosters, and learning crystals.
- **TEAM** switches which MATHMON is fighting.
- **CAPTURE** appears when a wild MATHMON is worn down. A short challenge, and it can join you.
- **AI MENTOR** offers a hint and a similar example. Press **H** any time a question is on screen for the built-in hint.
- **FLEE** steps back onto the trail. Your learning stays with you.

On a phone or a narrow window, on-screen buttons appear so you can play with a tap.

## Play it

You need Python 3 and pip.

```bash
pip install -r requirements.txt
python main.py
```

Your save lives in `saves/mathmon.sqlite3` while you are developing. A packaged build keeps saves in your user data folder instead.

### A live tutor (optional)

The mentor already works offline, with hints and walkthroughs written into the game. If you want those lines written fresh for the exact question in front of you, add an [Anthropic](https://www.anthropic.com/) key:

```bash
copy .env.example .env
```

Then put your key in `.env`:

```
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
```

The tutor gives a hint and a similar example during a fight, and short worked steps after three misses. It never decides whether you were right, and it never decides damage. The browser build always uses the offline tutor, so a key is never shipped inside the web page.

### In the browser

```bash
pip install -r requirements-dev.txt
python tools/build_web.py --serve
```

Open `http://localhost:8000`. `python tools/build_web.py` on its own writes the upload folder at `build/mathmon/build/web` (that is what Vercel publishes).

### Tests

```bash
python -m unittest discover -s tests
```

## What is in the box

```
main.py            start here
game/              the adventure: overworld, battles, MathDex, arena, trials
mathematics/       question writers and the exact answer checker
battle_engine/     Monster Trials rules (no drawing, just the fight)
ai/                the learning coach: topics, difficulty, hints, rewards
database/          your ranger, team, and progress
data/              maps, monsters, and world layout
assets/            sprites, backgrounds, fonts, sounds
tools/             web build and sprite helpers
docs/              how Monster Trials are built
```

Curious how a Trial boss thinks? `docs/ADVANCED_BATTLES.md` is the field guide: phases, weaknesses, and how to add a monster of your own.

Go on. The tall grass is moving.

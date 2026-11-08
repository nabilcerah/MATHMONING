# MATHMON
## Game Design Document (GDD) & Technical Implementation Specification

**Document Version:** 1.0
**Project Type:** Agentic AI Educational RPG
**Genre:** 2D Pixel-Art, Turn-Based Monster-Collecting RPG
**Theme:** Edutainment & Innovation
**Primary Platform:** PC
**Game Engine:** Python + Pygame
**AI Architecture:** Hybrid Multi-Agent AI
**Database:** SQLite
**Target Audience:** Secondary-school students (initial design assumption: Form 1–5)
**Development Priority:** Fully playable competition MVP

**Tagline: Train Your Mind. Evolve Your Power.**

> **How this document relates to the code.** Parts I–IX below are the design specification and are
> the primary source of truth. **Part X (end of file)** records how each part was implemented in this
> repository, the decisions taken where the specification met existing content, and known limitations.
> The phase-by-phase checklist lives in [docs/DEV_CHECKLIST.md](docs/DEV_CHECKLIST.md).

---

# PART I — GAME DESIGN DOCUMENT

# 1. GAME OVERVIEW

## 1.1 High Concept

MATHMON is an educational RPG that combines classic 8-bit monster-collecting gameplay with Agentic AI-powered personalised mathematics learning.

Players explore an open fantasy world, encounter wild creatures, battle opponents, capture monsters, complete quests and evolve their team.

The central game mechanic is mathematics-based combat.

Whenever players perform an attack, they must solve a mathematical challenge. Their mathematical performance determines the strength and effectiveness of their attacks.

Unlike conventional educational games, MATHMON uses Agentic AI to monitor player performance, identify mathematical weaknesses, adjust challenge difficulty, provide personalised tutoring and recommend learning activities.

The objective is to make mathematical learning a natural part of an enjoyable adventure.

## 1.2 Design Pillars

The game must follow five design principles.

**Pillar 1: Genuine RPG Experience**

MATHMON must feel like a complete RPG rather than a mathematics quiz with a game interface.

Exploration, combat, collection, progression, NPC interactions and discovery are essential.

**Pillar 2: Mathematics Through Gameplay**

Players should use mathematical knowledge to:
- Attack enemies.
- Unlock abilities.
- Open puzzle gates.
- Complete NPC quests.
- Capture creatures.
- Defeat bosses.
- Evolve their monsters.

**Pillar 3: Personalised Learning**

No two players should necessarily receive the same sequence of mathematical challenges.

The game adapts based on individual learning performance.

**Pillar 4: Meaningful Monster Progression**

Players should have a reason to collect, train and evolve their creatures.

Combat level and mathematical mastery must contribute separately to creature development.

**Pillar 5: Real Agentic AI**

The AI must analyse, plan, select tools, execute learning interventions, update player profiles and make meaningful recommendations.

It must not be presented as Agentic AI merely because it can generate questions or respond to messages.

# 2. GAME WORLD AND STORY

## 2.1 World Concept

MATHMON takes place in a fantasy universe called MATHEA.

Mathea is a world powered by mathematical energy called the NUMERA.

Every creature possesses a different form of mathematical energy.

However, the world is becoming unstable because the NUMERA is disappearing.

Mysterious creatures are losing control of their abilities, ancient mathematical structures are shutting down and different regions are becoming corrupted.

The player becomes a new NUMERA TRAINER.

Their mission is to explore Mathea, collect elemental creatures, restore mathematical energy and defeat the guardians threatening the world.

## 2.2 World Structure

The game contains four planned regions.

**WORLD 1: NUMBER FOREST**

Mathematical topics:
- Addition.
- Subtraction.
- Multiplication.
- Division.
- Fractions.

Environment:
- Green forests.
- Grasslands.
- Ancient ruins.
- Small villages.
- Hidden treasure areas.

Main boss: THE ARITHMETIC BEAST.

**WORLD 2: ALGEBRA CAVERN**

Mathematical topics:
- Variables.
- Linear equations.
- Expressions.
- Simultaneous equations.

Environment:
- Crystal caves.
- Underground passages.
- Ancient laboratories.

Main boss: THE UNKNOWN GUARDIAN.

**WORLD 3: GEOMETRY KINGDOM**

Mathematical topics:
- Area.
- Perimeter.
- Angles.
- Volume.
- Pythagoras theorem.

Environment:
- Ancient temples.
- Geometric structures.
- Stone castles.

Main boss: THE DIMENSION DRAGON.

**WORLD 4: CHRONOS DIMENSION**

Mathematical topics:
- Number sequences.
- Patterns.
- Time calculations.
- Advanced algebra.
- Introductory calculus as a future expansion.

Environment:
- Floating islands.
- Clockwork structures.
- Time-distorted landscapes.

Main boss: THE INFINITE OVERLORD.

Only NUMBER FOREST must be fully developed for the first MVP.

The architecture must allow future regions to be added through data and map configuration rather than major changes to the game engine.

# 3. PLAYER GAMEPLAY AND CONTROLS

## 3.1 Player Role

The player controls a trainer who explores the world and commands a team of mathematical creatures.

The trainer has:
- Name.
- Character appearance.
- Current location.
- Quest progress.
- Monster collection.
- Inventory.
- Learning profile.
- Game progress.

## 3.2 Controls

Keyboard controls:

| Key | Function |
|---|---|
| W / Up | Move up |
| S / Down | Move down |
| A / Left | Move left |
| D / Right | Move right |
| E | Interact |
| Enter | Confirm |
| Esc | Pause / Back |
| Tab | Open trainer menu |
| 1–4 | Menu shortcuts where applicable |

Menus must also support mouse interaction.

# 4. MONSTER COLLECTION SYSTEM

## 4.1 Party Structure

The player can maintain a team of THREE active party monsters.

Only ONE monster participates in battle at a time.

The remaining two stay in reserve and can be switched into combat.

Requirements:
- Maximum three monsters in the active party.
- One active monster at a time.
- Captured monsters join the party when space is available.
- Additional monsters are stored in the Monster Sanctuary.
- Initial storage capacity: 20 monsters.
- The player can rearrange their team at designated locations or through the trainer menu.
- Duplicate monsters are allowed.

When all three party monsters faint, the player is returned to the nearest safe location.

Captured monsters and permanent progression must never be deleted as a punishment.

## 4.2 Starter Selection

At the beginning of the game, allow the player to choose one starter monster:

1. FRACTELLA
2. GEOMAX
3. NUMEREX
4. CHRONOX

The remaining creatures can be discovered and captured through exploration.

The starter-selection screen must display:
- Monster sprite.
- Element.
- Description.
- Combat role.
- Mathematical affinity.
- Basic stats.

## 4.3 Initial Monster Roster

Create the following original creatures.

### FRACTELLA

Element: Crystal
Role: Balanced attacker / support.

Appearance:
- Pink and purple jelly-like slime.
- Translucent geometric body sections.
- Tiny arms.
- Sparkling eyes.
- Crystal on its head.
- Fraction symbol integrated into the crystal.

Mathematical affinity:
- Fractions.
- Ratios.
- Proportions.

Abilities:
- Crystal Shard.
- Fraction Blast.
- Prism Shield.

Passive:
Correct fraction challenges improve its ability effectiveness.

### GEOMAX

Element: Earth
Role: Tank / heavy attacker.

Appearance:
- Small bulky stone golem.
- Square torso.
- Golden-brown armour.
- Chunky arms.
- Glowing blue eyes.
- Triangular chest crystal.

Mathematical affinity:
- Geometry.
- Area.
- Perimeter.
- Volume.

Abilities:
- Stone Punch.
- Earthquake.
- Geometric Barrier.

Passive:
Receives additional defensive benefits from geometry mastery.

### NUMEREX

Element: Dark
Role: Fast attacker / debuffer.

Appearance:
- Floating shadow phantom.
- Dark purple body.
- Glowing red eyes.
- Wispy lower body.
- Tiny shadow arms.
- Natural negative symbol integrated into its markings.

Mathematical affinity:
- Negative numbers.
- Integers.
- Subtraction.

Abilities:
- Negative Pulse.
- Shadow Orb.
- Void Collapse.

Passive:
Receives bonus offensive effectiveness from integer mastery.

### CHRONOX

Element: Time
Role: Tactical attacker / control.

Appearance:
- Small bronze and golden clockwork dragon.
- Mechanical wings.
- Golden horns.
- Cyan glowing eyes.
- Circular clock marking on chest.
- Algebraic X integrated into its forehead.

Mathematical affinity:
- Number sequences.
- Patterns.
- Algebra.
- Time calculations.

Abilities:
- Pattern Swipe.
- Time Rift.
- Temporal Shift.

Passive:
Can obtain tactical control effects through strong performance in its mathematical topics.

## 4.4 Monster Statistics

Each monster has:

| Stat | Purpose |
|---|---|
| HP | Health |
| Attack | Offensive strength |
| Defence | Damage resistance |
| Speed | Determines escape ability and future tactical mechanics |
| Level | Combat progression |
| EXP | Experience gained |
| Mastery | Mathematical skill progression |
| Focus | Resource used for special moves |

Suggested level-one base statistics:

| Monster | HP | Attack | Defence | Speed |
|---|---:|---:|---:|---:|
| Fractella | 85 | 15 | 14 | 12 |
| Geomax | 110 | 14 | 20 | 7 |
| Numerex | 75 | 19 | 10 | 17 |
| Chronox | 85 | 16 | 13 | 15 |

These are initial balancing values. Implement the stats using configurable data rather than hardcoding them throughout the game.

# 5. ELEMENTAL SYSTEM

There are four initial elements:

- Crystal.
- Earth.
- Dark.
- Time.

Use this elemental relationship cycle:

Crystal beats Time.

Time beats Dark.

Dark beats Earth.

Earth beats Crystal.

The reverse matchup is a disadvantage.

Matchups that are not directly connected are neutral.

Elemental damage multipliers:

| Effectiveness | Multiplier |
|---|---:|
| Super effective | 1.5 |
| Neutral | 1.0 |
| Not very effective | 0.75 |

Display a clear battle message:
- "It's super effective!"
- "It's not very effective."
- "A normal attack!"

Elemental effectiveness must be controlled by the battle engine.

Do not let AI independently decide elemental damage.

# 6. CORE GAMEPLAY LOOP

The complete gameplay loop is:

1. Explore the overworld.
2. Discover items, NPCs and hidden locations.
3. Encounter wild monsters.
4. Participate in mathematical battles.
5. Defeat or capture monsters.
6. Earn EXP and rewards.
7. Improve mathematical mastery.
8. Complete quests.
9. Train and evolve monsters.
10. Unlock new areas and challenges.

The game should provide reasons to explore beyond fighting.

Players should be able to spend time:
- Talking to NPCs.
- Searching treasure locations.
- Solving environmental puzzles.
- Visiting shops.
- Completing quests.
- Exploring hidden paths.
- Managing their monster team.

# 7. TURN-BASED BATTLE SYSTEM

## 7.1 Battle Philosophy

Use classic turn-based RPG combat inspired by traditional monster-collecting games.

Combat must be strategic, readable and easy to understand.

Battle interface:

- Player monster.
- Enemy monster.
- Player HP bar.
- Enemy HP bar.
- Level indicators.
- EXP progress.
- Battle dialogue.
- Action menu.

Main actions:

1. FIGHT
2. MONSTER
3. BAG
4. RUN

## 7.2 Battle Flow

When a wild encounter occurs:

1. Enter the battle screen.
2. Display the player's active monster.
3. Display the enemy monster.
4. Display both HP bars.
5. Display the action menu.
6. Wait for the player's action.

The player's selected action is resolved first.

If the enemy remains alive, it performs its response.

The battle repeats until:
- The enemy is defeated.
- The enemy is captured.
- The player successfully escapes.
- The player's entire team faints.

The player always has time to read and understand the mathematical questions.

Do not impose a countdown timer in the initial version.

## 7.3 FIGHT MECHANIC

When FIGHT is selected:

Display the active monster's available moves.

Each move includes:
- Move name.
- Element.
- Mathematical topic.
- Base power.
- Focus cost.
- Short description.

Example:

FRACTELLA:

| Move | Topic | Power | Focus |
|---|---|---:|---:|
| Crystal Shard | Fractions | 16 | 0 |
| Fraction Blast | Ratios | 26 | 2 |
| Prism Shield | Geometry | Defensive | 1 |

Moves are configurable through data.

Selecting an attack generates a mathematical question.

Example:

2/3 + 1/6 = ?

Answer: 5/6.

Correct mathematical answers allow the attack to execute.

## 7.4 Answer Performance

Each attack question permits:
- First answer attempt.
- One optional hint.
- One additional answer attempt.

Performance multipliers:

| Performance | Damage multiplier |
|---|---:|
| Correct on first attempt without hint | 1.00 |
| Correct after using hint | 0.85 |
| Correct after second attempt | 0.75 |
| Incorrect after both attempts | 0.00 |

The AI tutor can provide an explanation after the question is resolved.

Incorrect answers should never shame the player.

## 7.5 DAMAGE FORMULA

Use this initial combat damage formula:

Damage = (Move Power + 0.5 × Attacker Attack)
× Defence Factor
× Answer Multiplier
× Mastery Multiplier
× Element Multiplier

Where:

Defence Factor = 100 / (100 + Defender Defence × 2)

Mastery Multiplier = 0.9 + 0.2 × (Topic Mastery / 100)

Round the final damage to the nearest integer.

Apply a minimum damage of 1 for a successful damaging attack.

Example:

Attacker:
- Move power = 16.
- Attack = 15.
- Topic mastery = 70.

Defender:
- Defence = 14.

Answer:
- Correct on first attempt.

Element:
- Neutral.

Calculation:

(16 + 0.5 × 15) × (100 / 128) × 1.0 × 1.04 × 1.0

Approximate damage = 22 HP.

The game engine must calculate damage. AI must not calculate or apply damage independently.

## 7.6 FOCUS SYSTEM

Focus is a resource used to activate powerful abilities.

Rules:
- Maximum Focus: 3.
- Correct ordinary attacks generate 1 Focus.
- Special moves consume 2 Focus.
- A special move cannot be used without sufficient Focus.
- Focus is maintained during the battle.
- Focus resets when entering a new battle.

A move can therefore become stronger when the player demonstrates consistent mathematical performance.

## 7.7 ENEMY ATTACKS

Enemy monsters use simple tactical behaviour.

Possible behaviours:
- Normal attack.
- Strong attack.
- Defensive action.
- Element-specific ability.

For the MVP, use a deterministic enemy decision system based on:
- Current HP.
- Available moves.
- Move priority.
- Basic difficulty configuration.

Enemy attacks do not require the player to solve a question.

However, the AI can analyse how the player responds to different enemy encounters for future learning recommendations.

## 7.8 SWITCHING MONSTERS

Selecting MONSTER displays the player's active party.

The player may switch to another healthy monster.

Rules:
- Switching consumes the player's turn.
- The enemy gets an opportunity to attack.
- Fainted monsters cannot be selected.
- Switching should never delete the previous monster's HP or progress.
- The active monster's current HP is preserved.

This makes team composition meaningful.

## 7.9 ITEMS

Initial items:

HEALTH POTION:
Restores 30% of maximum HP.

FOCUS CRYSTAL:
Restores 2 Focus during battle.

MATH CAPSULE:
Used to capture wild monsters.

REVIVAL CRYSTAL:
Restores a fainted monster with 30% HP.

Using a consumable item consumes the player's turn, except for clearly designated out-of-battle items.

## 7.10 RUNNING AWAY

Allow players to escape wild encounters.

Suggested escape formula:

Escape Chance = 50 + 3 × (Player Speed - Enemy Speed)

Clamp the result between 20% and 90%.

Boss battles and story encounters cannot be escaped.

An unsuccessful escape allows the enemy to attack.

# 8. MONSTER CAPTURE SYSTEM

Capturing monsters is a major part of MATHMON.

Wild monsters should be discovered throughout the overworld.

The player can weaken them before attempting capture.

## 8.1 Capture Conditions

- Only wild monsters can be captured.
- Boss monsters cannot be captured.
- The player must have an available Math Capsule.
- Captured monsters join the party if a slot is available.
- Otherwise, they are transferred to the Monster Sanctuary.

## 8.2 Capture Mechanics

When the player selects a Math Capsule:

1. Display a capture animation.
2. Generate a short mathematical binding challenge.
3. The question is based on the encountered monster's topic affinity.
4. The player solves the question.
5. Calculate capture probability.
6. Play the capture result animation.

Capture chance formula:

Capture Chance = 20 + 50 × (1 - Enemy HP Ratio) + Knowledge Bonus

Knowledge Bonus:
- Correct answer: +15 percentage points.
- Incorrect answer: +0.

Clamp the probability between 5% and 90%.

Example:

Enemy HP ratio = 0.2.

Correct mathematical answer:

20 + 50 × 0.8 + 15 = 75%.

The game rolls against this percentage.

A failed attempt consumes the capsule.

AI must not control the capture probability.

## 8.3 Capture Feedback

Successful capture:

"You successfully captured GEOMAX!"

Failed capture:

"The monster escaped the capsule!"

On successful capture:
- Add the creature to the party or storage.
- Save the creature's level and statistics.
- Display its mathematical affinity.
- Update the collection record.
- Provide a modest capture EXP reward.

# 9. MONSTER LEVEL AND EVOLUTION SYSTEM

## 9.1 Combat Level

Each monster begins at Level 1.

MVP maximum level: 20.

EXP required to reach the next level:

EXP Required = 60 + 20 × (Current Level - 1)

Examples:

| Current level | EXP needed |
|---|---:|
| 1 | 60 |
| 2 | 80 |
| 3 | 100 |
| 4 | 120 |
| 5 | 140 |

EXP sources:
- Winning battles.
- Capturing wild monsters.
- Completing quests.
- Defeating bosses.
- Discovering major locations.

Suggested battle EXP:

EXP Reward = 20 + 5 × Enemy Level.

Boss and quest rewards can be configured separately.

The active monster receives 100% of battle EXP.

Other party monsters receive 35% of battle EXP as shared training experience.

Only monsters that are not fainted receive shared EXP.

## 9.2 Stat Growth

When monsters level up:
- Increase maximum HP.
- Increase Attack.
- Increase Defence.
- Optionally improve Speed.

Use growth rates stored in monster configuration.

Current HP should increase by the same amount as maximum HP when levelling, so the player does not feel punished for progression.

## 9.3 Mathematical Mastery

This is a second independent progression system.

Every monster has an associated mathematical mastery category.

Mastery ranges from 0 to 100.

Example:

Fractella:
- Fractions.
- Ratios.
- Proportions.

Geomax:
- Geometry.
- Area.
- Perimeter.
- Volume.

Numerex:
- Integers.
- Negative numbers.
- Subtraction.

Chronox:
- Algebra.
- Sequences.
- Patterns.
- Time calculations.

Mastery is updated through question performance.

## 9.4 Mastery Calculation

Maintain a rolling history of the last 20 assessed questions for each topic.

Assign a learning score:

- Correct without assistance: 1.0.
- Correct after hint: 0.75.
- Correct after a worked example: 0.50.
- Incorrect after available attempts: 0.

Mastery Score = Average Learning Score × 100.

Display the score in the player profile.

Use an evidence requirement before considering a player to have mastered a topic.

Suggested mastery levels:

| Score | Classification |
|---|---|
| 0–39 | Foundation |
| 40–69 | Developing |
| 70–84 | Proficient |
| 85–100 | Mastered |

A player must have at least 10 assessed questions in a topic before being eligible for the Mastered classification.

Insufficient evidence must be displayed separately from low mastery.

## 9.5 Evolution Conditions

Evolution requires BOTH:

1. Minimum combat level.
2. Mathematical mastery achievement.

Initial evolution requirement:

- Monster level: 12 or higher.
- Associated topic mastery: 60 or higher.
- At least 10 assessed questions in that topic.

Evolution should become available through an NPC or a designated evolution shrine.

Do not force evolution immediately.

Show an evolution preview and let the player choose when to evolve.

Evolution must:
- Change the creature's appearance.
- Improve selected stats.
- Unlock or improve abilities.
- Preserve existing experience.
- Preserve mathematical learning records.
- Continue normal progression.

The MVP only needs to implement at least one complete evolution path as a proof of concept. All monsters should have data structures ready for additional stages.

# 10. OPEN-WORLD EXPLORATION

## 10.1 Overworld

Create an explorable 2D tile-based world.

The player must be able to:
- Walk in four directions.
- Interact with NPCs.
- Enter buildings.
- Visit shops.
- Discover treasures.
- Find hidden paths.
- Enter battle encounters.
- Access quest locations.

Use camera scrolling for maps larger than the visible game window.

## 10.2 NUMBER FOREST MVP

Number Forest should contain three subareas:

**STARTER VILLAGE**

Features:
- Player starting location.
- Monster Sanctuary.
- Shop.
- Tutorial NPC.
- Quest-giver NPC.
- Healing point.

**GREEN MEADOW**

Features:
- Wild monster encounters.
- Grass areas.
- Treasure.
- Tutorial battles.
- Basic arithmetic challenges.

**ANCIENT NUMBER RUINS**

Features:
- Mathematical puzzle gates.
- Hidden rewards.
- Stronger wild monsters.
- Main story quest.
- First boss arena.

Do not make the map feel like a set of disconnected battle screens.

The player must be able to explore continuously.

## 10.3 Random Encounters

Wild monsters appear in designated encounter zones.

Initial encounter configuration:

- Encounter probability: approximately 8% per eligible movement step.
- Minimum movement-step cooldown: 7 steps after a battle.
- Encounter tables determined by map region.
- Spawn levels based on region configuration.
- Rare creatures may have lower spawn probabilities.

Random encounters must not happen in:
- Buildings.
- Safe zones.
- Menus.
- NPC interaction states.
- Boss arenas.

Make encounter probabilities configurable.

## 10.4 NPC SYSTEM

NPCs may:
- Offer quests.
- Teach mathematical concepts.
- Provide hints.
- Sell items.
- Heal monsters.
- Explain the story.
- Reveal hidden areas.

NPC dialogue must be managed through structured dialogue data.

AI can personalise optional explanations, but essential storyline information must not depend on unpredictable LLM responses.

# 11. QUEST SYSTEM

There are three main quest categories.

MAIN QUESTS:

Advance the story and unlock new regions.

SIDE QUESTS:

Provide additional rewards and mathematical challenges.

EXPLORATION QUESTS:

Encourage discovery of secret locations and hidden treasures.

Examples:

Quest 1: THE LOST NUMBERS

An NPC has lost several numbered stones.

The player must solve arithmetic clues to locate them.

Reward:
- EXP.
- Health Potions.
- Coins.

Quest 2: THE BROKEN BRIDGE

An NPC needs help calculating the quantity of materials required to repair a bridge.

Mathematical topic:
- Area.
- Measurement.
- Multiplication.

Reward:
- Geomax-related item.
- EXP.
- Access to a new area.

Quest 3: THE CRYSTAL SEAL

The player must solve fraction puzzles to activate an ancient crystal structure.

Mathematical topic:
- Fractions.

Reward:
- Crystal Shards.
- Monster EXP.
- Special quest item.

Quest rewards must be deterministic and saved to the database.

The AI Game Master may recommend quests based on learning needs, but it must not arbitrarily alter quest completion requirements.

# 12. ITEMS AND ECONOMY

Create a simple game economy.

Player currency: NUMERA COINS.

Currencies are earned through:
- Battles.
- Quests.
- Hidden treasures.
- NPC tasks.

Items can be purchased from village shops.

Initial item list:

| Item | Function |
|---|---|
| Health Potion | Restore 30% HP |
| Greater Potion | Restore 60% HP |
| Focus Crystal | Restore 2 Focus |
| Math Capsule | Capture wild monsters |
| Revival Crystal | Revive fainted monster |
| Evolution Crystal | Special evolution quest item |

Avoid pay-to-win mechanics.

No real-money purchases are required.

---

# PART II — AGENTIC AI DESIGN

# 13. AI ROLE AND OBJECTIVES

The AI is the personal educational director of every MATHMON player.

Its objective is to improve the player's learning experience while preserving the freedom and enjoyment of exploration.

The AI must:
- Understand player performance.
- Maintain a persistent learning profile.
- Identify knowledge gaps.
- Recommend appropriate challenges.
- Generate or select mathematics questions.
- Provide personalised explanations.
- Adjust difficulty.
- Recommend quests.
- Evaluate whether the player is ready for more advanced challenges.

The AI does not own the game engine.

All HP, damage, EXP, inventory, monster stats, capture results and quest completion are controlled by deterministic game systems.

# 14. AGENT ARCHITECTURE

Build one central AI Orchestrator connected to five specialised agents.

## AGENT 1: QUESTION GENERATOR

Responsibilities:
- Generate mathematics challenges.
- Select the mathematical topic.
- Determine question difficulty.
- Produce hints.
- Produce worked solutions.
- Avoid repetitive challenges.

Inputs:
- Player mastery profile.
- Current region.
- Monster affinity.
- Requested difficulty.
- Recent question history.

Output:
Structured question object.

Example:

```json
{
  "question_id": "ALG_001",
  "topic": "algebra",
  "difficulty": "easy",
  "question": "2x + 6 = 16",
  "correct_answer": "5",
  "hint": "First subtract 6 from both sides.",
  "explanation": "2x = 10, so x = 5."
}
```

Question correctness must be independently verified by the mathematics engine.

Prefer deterministic templates for mathematical generation.

LLM-generated wording and word problems may be added as an optional extension, but their mathematical content must be validated before use.

## AGENT 2: LEARNING ANALYST

Responsibilities:
- Analyse correct and incorrect responses.
- Track topic-level performance.
- Identify repeated mistakes.
- Detect possible misconceptions.
- Estimate mastery and learning confidence.
- Produce learning summaries.

Example result:

```json
{
  "topic": "algebra",
  "identified_weakness": "isolating_variables",
  "evidence_count": 12,
  "mastery_score": 42,
  "recommendation": "guided_linear_equations"
}
```

The analyst must distinguish insufficient evidence from demonstrated weakness.

## AGENT 3: DIFFICULTY MANAGER

Responsibilities:
- Recommend question difficulty.
- Adjust the educational challenge.
- Prevent questions from becoming too easy.
- Reduce complexity when appropriate.
- Increase complexity when mastery improves.

Suggested starting logic:

| Mastery | Recommended difficulty |
|---|---|
| 0–39 | Foundation / Easy |
| 40–69 | Intermediate |
| 70–84 | Advanced |
| 85–100 | Mastery challenge |

The AI can also consider:
- Recent accuracy.
- Number of failed attempts.
- Hint usage.
- Confidence of the learning data.
- Topic-specific performance.

Use rule-based safeguards rather than allowing arbitrary LLM difficulty decisions.

## AGENT 4: AI TUTOR

Responsibilities:
- Explain incorrect answers.
- Give progressive hints.
- Break problems into smaller steps.
- Explain mathematical concepts.
- Provide worked examples.
- Encourage the player.
- Adapt explanations to the player's ability.

The AI Tutor should not reveal the complete solution immediately when the player asks for a hint.

Example:

Player:
"I don't understand this fraction question."

AI Tutor:

"Let's make the denominators equal first. What number can both 3 and 6 divide into?"

The explanation should be understandable by the intended student age group.

## AGENT 5: GAME MASTER / QUEST DIRECTOR

Responsibilities:
- Analyse player progression.
- Recommend suitable quests.
- Identify opportunities to revisit previous topics.
- Recommend boss readiness.
- Suggest monster training activities.
- Create personalised learning objectives.

Example:

"The player has demonstrated good arithmetic knowledge but still needs practice with fractions. Recommend the Crystal Seal quest before entering the next major challenge."

The Game Master can recommend existing quests but cannot change deterministic quest rules.

## CENTRAL AI ORCHESTRATOR

The Orchestrator coordinates all agents.

Required workflow:

1. Receive game event.
2. Retrieve the current player profile.
3. Identify the educational objective.
4. Determine which agent is required.
5. Invoke the relevant agent or tools.
6. Validate its result.
7. Apply permitted learning-profile updates.
8. Return a structured decision to the game engine.
9. Record the decision and its outcome.

Example:

Event: Player repeatedly struggles with fractions.

Orchestrator:
- Retrieves learning history.
- Calls Learning Analyst.
- Receives fraction weakness analysis.
- Calls Difficulty Manager.
- Selects a suitable question difficulty.
- Calls Question Generator.
- Prepares a fraction question.
- Makes AI Tutor available for hints.
- Stores the outcome after the player responds.

This should be an actual executable workflow, not a simulated sequence in documentation.

# 15. ADAPTIVE LEARNING SYSTEM

This is MATHMON's central innovation.

Two players should be able to follow the same storyline while receiving different learning experiences.

Example:

PLAYER A:

- Addition: 90%.
- Multiplication: 85%.
- Fractions: 35%.
- Algebra: 70%.

AI recommendation:

"Focus on fractions. Complete a guided fraction quest before moving to more advanced challenges."

PLAYER B:

- Addition: 65%.
- Multiplication: 45%.
- Fractions: 85%.
- Algebra: 80%.

AI recommendation:

"Strengthen multiplication skills through intermediate challenges."

Adaptive learning must influence:
- Battle questions.
- Quest recommendations.
- Tutor responses.
- Puzzle difficulty.
- Recommended training topics.
- Mastery-based evolution readiness.

The AI should not modify the player's story progression unfairly.

# 16. AI INTERACTION MODES

Implement three modes.

MODE A: OFFLINE AI

The game must remain playable without an API connection.

Use:
- Rule-based agent decisions.
- Question templates.
- Prewritten hints.
- Deterministic explanations.
- Local learning analysis.

MODE B: LIVE AI TUTOR

Connect the game to an Anthropic API through a secure Python backend.

Use:
- Natural-language explanations.
- Personalised tutoring.
- Contextual examples.
- Optional conversational interaction.

MODE C: HYBRID AGENTIC AI

Recommended default.

Use deterministic logic for:
- Mathematics validation.
- Combat.
- Damage.
- EXP.
- Capture.
- Level progression.
- Mastery calculation.
- Inventory.
- Quest state.

Use AI reasoning for:
- Educational analysis.
- Question adaptation.
- Tutor explanations.
- Quest recommendations.
- Personalised feedback.

If an API request fails, return to an offline response without crashing the game.

# 17. AI SAFETY AND VALIDATION

Important requirements:

1. Never use LLM output as the source of mathematical truth.
2. Validate generated questions independently.
3. Never let AI change monster HP directly.
4. Never let AI award arbitrary EXP.
5. Never allow AI to create unauthorised inventory changes.
6. Validate every structured agent response.
7. Restrict API context to necessary game and learning information.
8. Do not send unnecessary personal information.
9. Avoid harmful, insulting or age-inappropriate tutor responses.
10. Use timeouts and deterministic fallbacks.

The player should always be able to finish a battle if the AI API becomes unavailable.

---

# PART III — MATHEMATICS ENGINE

# 18. MATHEMATICAL CONTENT SYSTEM

Create a separate mathematics module.

Initial topics:

ARITHMETIC:
- Addition.
- Subtraction.
- Multiplication.
- Division.

FRACTIONS:
- Equivalent fractions.
- Addition.
- Subtraction.
- Multiplication.
- Division.
- Ratios.

ALGEBRA:
- Expressions.
- Variables.
- Linear equations.
- Simultaneous equations.

GEOMETRY:
- Area.
- Perimeter.
- Angles.
- Volume.
- Pythagoras theorem.

INTEGERS:
- Positive numbers.
- Negative numbers.
- Integer arithmetic.
- Subtraction involving negative numbers.

SEQUENCES:
- Number patterns.
- Arithmetic sequences.
- Pattern recognition.
- Time calculations.

Questions must be stored using structured data.

Each question contains:

- Unique ID.
- Topic.
- Subtopic.
- Difficulty.
- Question statement.
- Answer type.
- Correct answer.
- Hint.
- Worked explanation.
- Associated monster affinity.
- Source or generation method.

# 19. ANSWER VALIDATOR

Use SymPy where appropriate and safe deterministic parsing for simpler arithmetic.

Never use Python eval() on player input.

Support:
- Integers.
- Decimals.
- Fractions.
- Algebraic expressions.
- Simple equations.

Implement answer normalisation.

For example:

1/2, 0.5 and equivalent fractional expressions should be accepted when mathematically equivalent and appropriate to the requested answer format.

The question object may specify whether the player must give:
- An exact fraction.
- A decimal.
- An integer.
- A simplified expression.
- A numerical solution.

Do not accept mathematically equivalent answers if the question explicitly requires a specific representation, unless the input normaliser confirms it satisfies the requested form.

Include automated tests for answer validation.

---

# PART IV — TECHNICAL ARCHITECTURE

# 20. RECOMMENDED TECHNOLOGY STACK

| Component | Technology |
|---|---|
| Main game engine | Python |
| Graphics | Pygame |
| Visual style | 8-bit pixel art |
| AI | Anthropic API, optional |
| Agent orchestration | Python |
| Mathematics | SymPy + deterministic validators |
| Database | SQLite |
| Data validation | Typed Python models / Pydantic if useful |
| Environment variables | python-dotenv |
| Testing | pytest |
| Asset processing | Pillow |
| Version control | Git |

The game must work locally without requiring a web server.

# 21. SOFTWARE ARCHITECTURE

Use a modular architecture.

Recommended folder structure:

```
MATHMON/
│
├── main.py
├── config.py
├── requirements.txt
├── .env.example
├── README.md
├── GDD.md
│
├── game/
│   ├── game_manager.py
│   ├── state_manager.py
│   ├── event_manager.py
│   ├── save_manager.py
│   ├── camera.py
│   └── settings.py
│
├── states/
│   ├── main_menu.py
│   ├── character_selection.py
│   ├── starter_selection.py
│   ├── overworld_state.py
│   ├── battle_state.py
│   ├── question_state.py
│   ├── inventory_state.py
│   ├── party_state.py
│   ├── player_profile_state.py
│   ├── dialogue_state.py
│   └── pause_state.py
│
├── world/
│   ├── map_manager.py
│   ├── tilemap.py
│   ├── encounter_manager.py
│   ├── npc_manager.py
│   ├── quest_manager.py
│   ├── interaction_manager.py
│   └── world_data/
│
├── monsters/
│   ├── monster.py
│   ├── monster_data.py
│   ├── monster_factory.py
│   ├── monster_party.py
│   ├── capture_manager.py
│   ├── evolution_manager.py
│   └── elemental_system.py
│
├── combat/
│   ├── battle_manager.py
│   ├── battle_rules.py
│   ├── damage_calculator.py
│   ├── enemy_ai.py
│   ├── move_system.py
│   └── reward_manager.py
│
├── mathematics/
│   ├── question_generator.py
│   ├── question_templates.py
│   ├── answer_validator.py
│   ├── mastery_manager.py
│   └── explanations.py
│
├── ai/
│   ├── orchestrator.py
│   ├── agent_base.py
│   ├── question_agent.py
│   ├── learning_analyst.py
│   ├── difficulty_manager.py
│   ├── tutor_agent.py
│   ├── game_master.py
│   ├── llm_provider.py
│   ├── offline_provider.py
│   └── schemas.py
│
├── database/
│   ├── database.py
│   ├── schema.sql
│   ├── repositories/
│   └── migrations/
│
├── ui/
│   ├── buttons.py
│   ├── panels.py
│   ├── dialogue_box.py
│   ├── progress_bars.py
│   └── menus.py
│
├── assets/
│   ├── sprites/
│   │   ├── monsters/
│   │   ├── player/
│   │   └── npcs/
│   ├── maps/
│   ├── backgrounds/
│   ├── ui/
│   ├── fonts/
│   └── audio/
│
├── data/
│   ├── monsters.json
│   ├── moves.json
│   ├── items.json
│   ├── questions.json
│   ├── quests.json
│   ├── encounters.json
│   └── world.json
│
├── tests/
│   ├── test_combat.py
│   ├── test_damage.py
│   ├── test_capture.py
│   ├── test_evolution.py
│   ├── test_questions.py
│   ├── test_validator.py
│   ├── test_mastery.py
│   ├── test_ai_agents.py
│   ├── test_database.py
│   └── test_save_load.py
│
└── saves/
```

You may adjust the structure if necessary, but do not combine all game logic into one Python file.

# 22. GAME STATE MANAGEMENT

Implement an explicit state machine.

Required states:

- Main Menu.
- New Game.
- Starter Selection.
- Overworld.
- Dialogue.
- Battle.
- Mathematical Question.
- Party Management.
- Inventory.
- Player Profile.
- Monster Sanctuary.
- Pause.
- Game Over / Recovery.

State transitions must be controlled by a central State Manager.

Do not create multiple competing Pygame loops.

Use one main game loop.

The main game loop must handle:
- Events.
- State updates.
- Rendering.
- Frame timing.
- Input.

Suggested target frame rate: 60 FPS.

# 23. DATABASE DESIGN

Use SQLite.

Create the following persistent entities.

PLAYERS:
- player_id.
- player_name.
- current_region.
- current_map.
- position_x.
- position_y.
- currency.
- created_at.

MONSTERS:
- monster_instance_id.
- species_id.
- level.
- exp.
- current_hp.
- maximum_hp.
- attack.
- defence.
- speed.
- evolution_stage.
- acquired_at.

PARTY:
- player_id.
- monster_instance_id.
- party_position.
- is_active.

STORAGE:
- player_id.
- monster_instance_id.
- storage_position.

LEARNING_PROFILES:
- player_id.
- topic.
- mastery_score.
- evidence_count.
- last_assessed_at.

QUESTION_HISTORY:
- attempt_id.
- player_id.
- question_id.
- topic.
- difficulty.
- correct.
- used_hint.
- attempts_used.
- learning_score.
- timestamp.

QUESTS:
- player_id.
- quest_id.
- status.
- progress.
- completed_at.

INVENTORY:
- player_id.
- item_id.
- quantity.

CAPTURE_RECORDS:
- player_id.
- species_id.
- captured_count.

Save automatically after significant events.

The game must restore the last saved state when reopened.

Use database transactions for critical changes such as successful captures, evolution and rewards.

---

# PART V — VISUAL AND AUDIO DESIGN

# 24. VISUAL STYLE

Use a nostalgic Game Boy-inspired 8-bit RPG aesthetic.

Technical presentation:

- Virtual resolution: 320 × 240.
- Scale to a larger desktop window using nearest-neighbour scaling.
- Crisp pixel edges.
- Limited colour palettes.
- Dark outlines.
- Retro game menus.
- Pixel-art backgrounds.
- Animated monster sprites.
- Classic RPG dialogue boxes.

The visual style should be consistent across all environments.

Avoid making the interface look like an ordinary modern educational dashboard.

## 24.1 Monster Animation System

Support 3×3 animation sprite sheets.

Each sheet has nine animation cells:

| Grid position | Animation |
|---|---|
| Row 1, Column 1 | Idle |
| Row 1, Column 2 | Walk 1 |
| Row 1, Column 3 | Walk 2 |
| Row 2, Column 1 | Attack 1 |
| Row 2, Column 2 | Attack 2 |
| Row 2, Column 3 | Special 1 |
| Row 3, Column 1 | Special 2 |
| Row 3, Column 2 | Damage |
| Row 3, Column 3 | Victory |

Target source sheet resolution:
768 × 768.

Each intended animation cell:
256 × 256.

Implement a SpriteSheetLoader that:
- Loads a sprite sheet.
- Checks its image dimensions.
- Crops the nine cells.
- Allows individual animation frames to be selected.
- Scales frames to the game display.
- Supports transparent backgrounds.
- Provides a configurable frame duration.

IMPORTANT:

Generated image assets may not always have the exact resolution, spacing or alpha transparency specified in their generation prompt.

Inspect the actual files before cropping.

Do not blindly divide an arbitrary image into nine sections if it has borders, gutters, inconsistent cell positions or a visible checkerboard background.

Provide a manual configuration fallback for sprite-sheet cell coordinates.

The game must remain playable using placeholder sprites if a monster asset is missing.

## 24.2 Animation Requirements

Implement:
- Idle looping animation.
- Alternating walking animation.
- Attack wind-up.
- Attack execution.
- Special ability animation.
- Damage reaction.
- Victory animation.

Monster animations must be triggered by game events.

For example:

Player selects Fraction Blast:
1. Display Attack 1.
2. Display mathematical challenge.
3. Validate answer.
4. Display Attack 2.
5. Apply damage.
6. Return to battle idle animation.

# 25. AUDIO

Provide optional:
- Main menu theme.
- Overworld background music.
- Battle music.
- Boss battle music.
- Attack effects.
- Monster capture sound.
- Evolution sound.
- Level-up sound.

If audio assets are unavailable, use placeholder silence or simple generated effects.

The game must not crash because of missing audio files.

---

# PART VI — USER INTERFACE

# 26. REQUIRED SCREENS

MAIN MENU:
- MATHMON logo.
- New Game.
- Continue.
- Settings.
- Exit.

STARTER SELECTION:
- Four monster choices.
- Monster descriptions.
- Element information.
- Mathematical affinity.

OVERWORLD:
- Player.
- Map.
- NPCs.
- Interaction prompts.
- Mini status display.

BATTLE:
- Both monsters.
- HP bars.
- Levels.
- EXP indicators.
- Dialogue.
- Fight / Monster / Bag / Run.

QUESTION:
- Question statement.
- Answer input.
- Submit button.
- Hint option.
- Explanation panel.
- Feedback.

PARTY:
- Three active party slots.
- Monster health.
- Level.
- EXP.
- Mastery.
- Switch controls.

MONSTER SANCTUARY:
- Stored monsters.
- Monster information.
- Transfer controls.
- Party management.

PLAYER PROFILE:
- Topic mastery.
- Total questions attempted.
- Learning history.
- Strongest topics.
- Developing topics.
- AI recommendations.

INVENTORY:
- Items.
- Quantities.
- Descriptions.
- Usage controls.

PAUSE:
- Resume.
- Save.
- Settings.
- Main Menu.

---

# PART VII — CLAUDE CODE IMPLEMENTATION INSTRUCTIONS

# 27. DEVELOPMENT PRIORITIES

Claude Code must build MATHMON incrementally.

Do not attempt to generate the entire game in one enormous source file.

## PHASE 1 — PROJECT FOUNDATION

Implement:
- Project structure.
- Pygame initialisation.
- Window management.
- Game loop.
- State Manager.
- Main Menu.
- Basic UI system.
- Settings.

Acceptance criteria:
- Game launches without errors.
- Menu is navigable.
- Keyboard controls work.
- Window scales correctly.
- Missing optional assets do not crash the application.

## PHASE 2 — MONSTER SYSTEM

Implement:
- Monster data models.
- Four original monster species.
- Monster stats.
- Starter selection.
- Party manager.
- Monster Sanctuary.
- Basic monster animations.

Acceptance criteria:
- Player can select a starter.
- Player can maintain a party of three.
- Monster information is displayed correctly.
- Monsters can be switched and stored.

## PHASE 3 — OVERWORLD

Implement:
- Tile map.
- Player movement.
- Camera.
- Starter Village.
- Green Meadow.
- NPC interactions.
- Random encounters.
- Basic treasure objects.

Acceptance criteria:
- Player can explore the world.
- Player cannot walk through blocked tiles.
- NPC interactions work.
- Random encounters only occur in designated zones.

## PHASE 4 — BATTLE ENGINE

Implement:
- Battle state.
- Enemy creation.
- Four main battle actions.
- Move system.
- Question screen.
- Damage calculation.
- Enemy attacks.
- Monster switching.
- Item usage.
- Battle rewards.

Acceptance criteria:
- Player can complete a full battle.
- Both monsters display their HP correctly.
- Correct answers produce attacks.
- Incorrect answers trigger the configured learning flow.
- Damage matches the deterministic formula.
- A defeated enemy ends the battle correctly.

## PHASE 5 — CAPTURE AND PROGRESSION

Implement:
- Math Capsule.
- Capture probability.
- Capture animation.
- Monster party/storage integration.
- EXP.
- Level progression.
- Focus.
- Evolution conditions.

Acceptance criteria:
- Wild creatures can be captured.
- Boss creatures cannot be captured.
- Party limits are enforced.
- Captured creatures are saved.
- Levelling works.
- Evolution requires both level and mathematical mastery.

## PHASE 6 — MATHEMATICS ENGINE

Implement:
- Question templates.
- Difficulty levels.
- Topic classification.
- Answer validation.
- Hints.
- Worked explanations.
- Question history.
- Mastery calculation.

Acceptance criteria:
- Questions are mathematically correct.
- Answers are independently validated.
- Equivalent valid representations are handled appropriately.
- Mastery updates after every assessed challenge.
- Repeated questions are controlled.

## PHASE 7 — AGENTIC AI

Implement:
- Central Orchestrator.
- Question Generator Agent.
- Learning Analyst.
- Difficulty Manager.
- AI Tutor.
- Game Master.
- Offline AI provider.
- Optional Anthropic provider.
- Validated agent responses.

Acceptance criteria:
- The agents have actual executable functions.
- Orchestrator can coordinate at least two agents in one adaptive workflow.
- Player history influences later questions.
- Tutor responds contextually to mistakes.
- Difficulty changes according to learning evidence.
- AI recommendations are stored.
- Offline mode works without API credentials.

## PHASE 8 — QUESTS AND WORLD DESIGN

Implement:
- Main quest.
- Side quests.
- NPC dialogue.
- Puzzle gates.
- Shop.
- Healing point.
- First boss.
- World completion conditions.

Acceptance criteria:
- Player can complete the first region.
- Rewards are correctly applied.
- Quest progress persists.
- Boss battle functions.
- Player can access the next region only after the configured requirements.

## PHASE 9 — FINAL POLISH AND TESTING

Implement:
- Improved menus.
- Animations.
- Sound effects.
- Save/load.
- Error handling.
- Performance improvements.
- Testing.
- README.

Acceptance criteria:
- Main features operate together.
- No major crashes during normal play.
- Game save and restore work.
- The application is demonstrable from start to boss victory.
- Tests pass.

---

# PART VIII — TESTING REQUIREMENTS

# 28. AUTOMATED TESTS

Create automated tests for:

COMBAT:
- Damage calculation.
- Element advantages.
- Defence calculations.
- Focus consumption.
- Fainting.
- Enemy defeat.

CAPTURE:
- Capture probability.
- Capture success.
- Capture failure.
- Party capacity.
- Storage capacity.
- Boss capture restriction.

PROGRESSION:
- EXP calculations.
- Level-up.
- Stat growth.
- Mastery calculations.
- Evolution eligibility.

MATHEMATICS:
- Integer validation.
- Decimal validation.
- Fraction validation.
- Algebra validation.
- Equivalent answers.
- Invalid input.
- Question generation.

AI:
- Agent inputs and outputs.
- Orchestrator routing.
- Learning analysis.
- Difficulty recommendations.
- Tutor fallback.
- Invalid AI response handling.
- Offline functionality.

DATABASE:
- Player creation.
- Monster storage.
- Party management.
- Question history.
- Quest progress.
- Save/load recovery.

Use pytest.

Do not mark tests as passed without executing them.

# 29. PERFORMANCE AND RELIABILITY

Requirements:

- Target 60 FPS.
- Keep the Pygame loop responsive.
- Never block rendering while waiting for the AI API.
- Run external API requests outside the main game loop.
- Include request timeouts.
- Handle missing assets.
- Handle malformed AI output.
- Handle database errors.
- Avoid losing progress during normal game closure.
- Use a consistent game state transition system.

The game must be fully playable without an internet connection.

# 30. DEFINITION OF DONE

The first competition-ready MVP is complete when a player can:

1. Launch MATHMON.
2. Start a new adventure.
3. Select a starter monster.
4. Enter Number Forest.
5. Explore the overworld.
6. Interact with NPCs.
7. Encounter wild monsters.
8. Participate in mathematical turn-based combat.
9. Receive AI hints.
10. Defeat enemies.
11. Capture wild creatures.
12. Maintain a party of three monsters.
13. Store additional creatures.
14. Earn EXP.
15. Increase monster levels.
16. Improve mathematical mastery.
17. Receive personalised AI recommendations.
18. Visit a shop and use items.
19. Complete quests.
20. Defeat the first boss.
21. Save and restore the adventure.

The MVP must also demonstrate the following Agentic AI workflow:

A player repeatedly struggles with algebra.

The Learning Analyst identifies the problem.

The Orchestrator calls the Difficulty Manager.

The Question Generator produces a suitable practice challenge.

The AI Tutor gives a contextual hint.

The player improves.

The Learning Analyst updates the mastery profile.

The Game Master recommends an appropriate next quest.

This workflow must be operational and demonstrable.

---

# PART IX — MASTER INSTRUCTION TO CLAUDE CODE

You are responsible for converting this document into a working game.

Treat this GDD as the primary source of truth.

Follow these instructions:

1. Inspect the existing project directory before making changes.
2. Do not overwrite useful existing assets or source code unnecessarily.
3. Create GDD.md containing the complete game design specification.
4. Create the proposed modular project structure.
5. Implement actual functionality rather than generating placeholder functions for every feature.
6. Work phase by phase.
7. Test each major subsystem before integration.
8. Fix errors before proceeding.
9. Keep game logic separate from AI logic.
10. Keep mathematical validation separate from question generation.
11. Keep all game data configurable.
12. Do not let the LLM control deterministic game mechanics.
13. Maintain offline functionality.
14. Use the original MATHMON creature designs and visual identity.
15. Prioritise a polished, playable first region over incomplete future content.

## Initial execution instructions

Before writing code:

A. Inspect the folder and Python installation.

B. Identify available assets and check their actual file dimensions and formats.

C. Create a development checklist based on the implementation phases.

D. Identify any missing dependencies.

E. Create the initial project structure.

Then begin PHASE 1.

Do not stop after producing the architecture, planning document or README.

Actually implement, run and test the application.

After every phase, report:
- Files created or modified.
- Features implemented.
- Tests executed.
- Tests passed or failed.
- Remaining tasks.
- Any important implementation decisions.

If a feature is too large for the MVP, implement a working simplified version and document the limitation rather than leaving it entirely unimplemented.

## FINAL PROJECT GOAL

Build MATHMON into a complete educational monster-collecting RPG that demonstrates how Agentic AI can personalise mathematical learning through an immersive game experience.

The final product must successfully combine:

**RPG GAMEPLAY + MONSTER COLLECTION + MATHEMATICS + ADAPTIVE LEARNING + AGENTIC AI.**

The game must be fun to play, mathematically reliable, visually engaging, technically credible and suitable for demonstration at an AI innovation competition.

Start with PHASE 1 and continue systematically until the first playable MVP is complete.

---

# PART X — IMPLEMENTATION NOTES (this repository)

Status: all nine phases implemented and tested. The checklist with acceptance criteria and the tests
that verify each one is in [docs/DEV_CHECKLIST.md](docs/DEV_CHECKLIST.md).

## X.1 Where each part lives

| GDD part | Code / data |
|---|---|
| 4 Monsters, party, Sanctuary | `data/monsters.json`, `monsters/` (`monster.py`, `monster_party.py`, `monster_factory.py`) |
| 5 Elements | `data/elements.json`, `monsters/elemental_system.py` |
| 7 Battle | `combat/battle_manager.py` (rules), `combat/damage_calculator.py`, `combat/enemy_ai.py`, `game/battle.py` (screen) |
| 8 Capture | `monsters/capture_manager.py` |
| 9 Levels, mastery, evolution | `monsters/monster.py`, `mathematics/mastery_manager.py`, `monsters/evolution_manager.py`, `states/evolution_state.py` |
| 10 World, encounters, NPCs | `data/maps/*.json`, `game/overworld.py`, `world/encounter_manager.py`, `data/encounters.json` |
| 11 Quests | `data/quests.json`, `world/quest_manager.py`, `states/quest_state.py`, `states/challenge_state.py` |
| 12 Items, shop | `data/items.json`, `world/shop.py`, `states/shop_state.py`, `states/inventory_state.py` |
| 13–17 Agentic AI | `ai/orchestrator.py`, `ai/{question_agent,learning_analyst,difficulty_manager,tutor_agent,game_master}.py`, `ai/schemas.py`, `ai/llm_provider.py`, `ai/offline_provider.py` |
| 18–19 Maths | `mathematics/question_templates.py`, `mathematics/question_generator.py`, `mathematics/answer_validator.py`, `mathematics/curriculum.py` |
| 22 State machine | `game/game_manager.py` (one loop), `game/state_manager.py`, `states/` |
| 23 Database | `database/schema.sql`, `database/database.py` (migrations), `database/player_repository.py` |
| 25 Audio | `game/audio.py` |
| Every tunable number | `data/rules.json` |

## X.2 Decisions taken where the specification met existing content

- **Rebuilt on the existing game.** The overworld, painted maps, sprites, Monster Trials, Math Arena, puzzle shrines
  and Crystal Realm were kept. The older starters (PYRON, AQUABIT) and wild monsters are now wild species with GDD
  stats and elements.
- **NUMEREX is both a starter and the boss.** The boss is a separate species, `NUMEREX_BOSS` ("THE ARITHMETIC
  BEAST", level 10, darker recolour). It can't be captured or escaped from.
- **Area names.** Lakeside Village → Starter Village, Whisper Fields → Green Meadow, Shadow Ruins → Ancient Number
  Ruins. The other painted areas remain as optional exploration.
- **Puzzle gates.** The ruins are too open on the painted map for a wall, so the arch is sealed by three Numera
  Seals (puzzle gates). THE BROKEN BRIDGE *is* a physical barrier: it cuts off the Sunsand Desert until repaired.
- **Buildings.** The Shop and Monster Sanctuary are walk-in interiors (`data/maps/village_*.json`). The Sanctuary
  keeper heals the party and manages storage.
- **Evolution shrine.** It needs the Evolution Crystal from THE CRYSTAL SEAL to awaken. Evolution itself follows
  the GDD rule exactly (level 12 + mastery 60 + 10 questions), and the player confirms it after a preview.
- **Focus.** Specials and supports spend Focus only when the move succeeds; a missed special keeps its Focus.
- **Questions.** "One optional hint" per question. After a wrong first attempt the tutor names the likely
  misconception, and a *worked example on different numbers* is offered (learning score 0.5 if then solved).
  A second-attempt success without a worked example scores 0.75. Unreadable input never costs an attempt.
- **Mastery.** One profile for the whole game. Battles, captures, puzzle gates and the bonus modes (Arena, Trials)
  all record assessed questions. Fewer than 5 questions in a topic is shown as "gathering evidence", never as weak.
- **Passives** (applied on top of the core formula as an explicit `extra` multiplier): FRACTELLA +5% per correct
  fractions answer (max 15%); GEOMAX takes up to 15% less damage from geometry mastery; NUMEREX deals up to 15% more
  from integer mastery; CHRONOX slows the foe's next hit after two first-try answers in a row.
- **Enemy damage scale.** Wild ×0.7, trainer ×0.85, boss ×1.0 (`rules.json`). Enemies answer no questions.

## X.2b Worlds 2–4

All four GDD worlds are playable. Each new world has an arrival camp (healing spring, travelling merchant, the main
quest giver), two wild areas, and a sanctum. The sanctum holds three seals (puzzle gates whose questions never drop
below a set difficulty) and the boss gate. Portals chain the worlds in order and each opens only after that world's
boss: Number Forest (ruins cave entrance) → Algebra Cavern → Geometry Kingdom → Chronos Dimension → home. Defeating
THE INFINITE OVERLORD sets `game:complete`.

| World | Topics | Wild (levels) | Boss |
|---|---|---|---|
| Algebra Cavern | algebra, integers | NULLSHADE, INFERMATH, AQUABIT, NUMEREX (9–13) | THE UNKNOWN GUARDIAN (EQUINOX, Lv 14) |
| Geometry Kingdom | geometry, multiplication | CRYSTALGON, VOLTBYTE, GALAXION, MYCOMORPH, GEOMAX (12–16) | THE DIMENSION DRAGON (Lv 17) |
| Chronos Dimension | sequences, time, algebra | CHRONOWL, HEXABYTE, SPHYNOX, ARITHMORD (15–19) | THE INFINITE OVERLORD (INFINITY ZERO, Lv 20) |

Boss gates are data: each `boss_gate` object in a map names its seals, boss, level, flag and texts. The maps are
generated by `tools/generate_worlds.py`, and the new species reuse the Monster Trials sprite sheets.

## X.2c Changes from the playtest bug report

| Report item | What changed |
|---|---|
| 1. Hints should not be words | `game/visual_hint.py` draws an animated picture from the question's own numbers, beside the question with a one-line caption: number-line hops, gaps to measure, dot arrays, groups, fraction bars, balance scales, labelled shapes, pattern arrows, clocks (28 kinds, every question type). Pictures never use a computed result (tested). |
| 2. Music and SFX | `tools/generate_audio.py` synthesises 7 chiptune loops (menu, one per world, battle, boss) and 9 effects as WAVs. Music follows the state and world. Settings has a sound toggle. |
| 3. Choose a companion in the MathDex | ENTER on a caught species makes it the party lead (fetched from the Sanctuary if needed). The lead follows you; ★ marks it. |
| 4. Map parts can't be crossed | The player now walks through NPCs (Bram stood on the bridge path), and bumping the broken bridge explains how to repair it. A test checks every map is fully connected. |
| 5. Mathmon Recovery Center | The blue village house is the MCR, using the provided exterior, interior, nurse and recovery-chamber art (`tools/process_building_art.py`). Healing means solving up to 3 AI-chosen problems: each right answer heals 34% and advances the 9-frame chamber; a miss still heals 10%. Three right answers fully heal. Fainting wakes you there. World camps have Recovery Stations; the Sanctuary no longer heals for free. |
| 6. Mathmart and item list | The red house is the MATHMART (provided art) selling exactly the requested items at the requested prices. Health Potion → Math Potion, Focus Crystal → Energy Potion, Math Capsule → Basic Mathball, Revival Crystal → Revive Crystal (old saves are migrated). New: Full Restore, Advanced Mathball (+15% capture), Attack/Defence Boost (±25% for the battle), Knowledge Tome (EXP for Proficient topics), EXP Star (+1 level). Coin rewards were raised to match. |

## X.3 Notes on the specification text

- **Damage example (7.5).** The formula gives (16 + 7.5) × 100/128 × 1.0 × 1.04 × 1.0 = **19.09 → 19**, not the "≈ 22"
  printed in the example. The engine implements the formula as written, and a test pins the value.
- **SymPy.** `sympy.parse_expr` evaluates strings with Python's `eval`, so player algebra goes through a small
  recursive-descent parser that builds SymPy objects directly (GDD 19: never `eval` player input).

## X.4 Running

```
.venv/Scripts/python main.py          # play
.venv/Scripts/python -m pytest        # tests
```

Optional AI tutor voice: put `ANTHROPIC_API_KEY=...` in `.env`. `MATHMON_AI_MODE` = `offline`, `live` or `hybrid`
(default `hybrid`). Without a key the game is fully playable offline.

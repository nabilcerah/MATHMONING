# MATHMON development checklist (GDD Part VII)

Status of each phase against its acceptance criteria. "Verified by" names the automated tests that
exercise it (`.venv/Scripts/python -m pytest`).

## Phase 1 — Project foundation ✅
- [x] Modular structure: `game/`, `states/`, `world/`, `monsters/`, `combat/`, `mathematics/`, `ai/`, `database/`, `data/`
- [x] One main loop (`GameManager.run_async`), 60 FPS, central `StateManager` (`game/state_manager.py`)
- [x] Main menu (New Game / Continue / Settings / Exit), keyboard + mouse
- [x] 320×240 canvas, whole-number nearest-neighbour scaling, F11 fullscreen, resizable window
- [x] Missing sprites → placeholder sprite; missing audio → generated blips / silence
- Verified by: `test_game_smoke`, `test_deployment`, real launch (~60 FPS)

## Phase 2 — Monster system ✅
- [x] Data-driven species (`data/monsters.json`), moves (`data/moves.json`), GDD stats for the 4 starters
- [x] Starter selection showing sprite, element, description, role, affinity, stats, moves, passive
- [x] Party of 3 + Monster Sanctuary (20), duplicates allowed, lead/reorder, deposit/withdraw/swap
- [x] Animated sprites (idle / wind-up / attack / special / hurt / victory poses)
- Verified by: `test_capture.PartyTests`, `test_progression.ExpTests.test_gdd_starter_stats`, `test_save_load`

## Phase 3 — Overworld ✅
- [x] Painted tile world with collision, camera, fog of war, fast travel
- [x] Starter Village (spawn, Shop + Sanctuary interiors, Professor Numeris tutorial, quest-giver Mira, healing)
- [x] Green Meadow (grass, treasure, tutorial battles), Ancient Number Ruins (seals, boss arch, stronger monsters)
- [x] Encounters: 8% per grass step, 7-step cooldown, region tables/levels, never in safe zones or dialogue
- Verified by: `test_overworld` (incl. safe-zone and broken-bridge tests), `test_realm`

## Phase 4 — Battle engine ✅
- [x] FIGHT / MONSTER / BAG / RUN, move list with element, topic, power, Focus cost, description
- [x] Question screen: attempt → optional hint → second attempt / worked example → explanation
- [x] GDD damage formula, element cycle, enemy AI (deterministic), switching, items, rewards
- Verified by: `test_combat`, `test_game_smoke`

## Phase 5 — Capture and progression ✅
- [x] Math Capsule + binding challenge on the monster's affinity, GDD capture formula, capsule animation
- [x] EXP curve, 35% shared EXP, stat growth, level cap 20, Focus
- [x] Evolution needs level 12 AND mastery 60 with 10 questions; preview + confirm at the shrine; 4 evolution paths
- Verified by: `test_capture`, `test_progression`, `test_region_flow`

## Phase 6 — Mathematics engine ✅
- [x] Templates for 10 topics × 4 bands, each answer re-proved (expression / substitution / equivalence)
- [x] Answer types: integer, number, fraction, simplified fraction, decimal, expression, equation, time
- [x] Safe parser (no `eval`, no `sympy.parse_expr`), question history, rolling-20 mastery with evidence rules
- Verified by: `test_questions`, `test_validator`, `test_progression.MasteryTests`, `test_question_engine`

## Phase 7 — Agentic AI ✅
- [x] Orchestrator running the 9-step workflow with a visible trace, logged to `ai_decisions`
- [x] Question Generator, Learning Analyst (misconceptions, evidence), Difficulty Manager (rules + safeguards),
      AI Tutor (progressive hints, misconception feedback, worked examples), Game Master (quests, readiness, objectives)
- [x] Offline / live / hybrid modes (`MATHMON_AI_MODE`), timeouts, validated responses, offline fallback
- Verified by: `test_ai_agents` (incl. the GDD 30 algebra workflow)

## Phase 8 — Quests and world design ✅
- [x] Main quest THE FADING NUMERA; side quests LOST NUMBERS, BROKEN BRIDGE, CRYSTAL SEAL, UNKNOWN RUNES;
      exploration quest HIDDEN TREASURES
- [x] Puzzle gates (three Numera Seals), shop, healing, boss, region completion → Crystal Realm portal
- Verified by: `test_region_flow`, `test_save_load.SaveLoadTests.test_quest_progress_and_rewards_persist`

## Phase 9 — Polish and testing ✅
- [x] Save on significant events + autosave, restore on Continue, legacy-save migration
- [x] Placeholder sound effects, optional music files, sound toggle
- [x] 184+ automated tests

## Worlds 2–4 ✅
- [x] Algebra Cavern (algebra, integers): Cave Mouth camp, Glow Tunnels, Echo Hollow, Lost Laboratory; boss
      THE UNKNOWN GUARDIAN (Lv 14); main quest THE UNKNOWN GUARDIAN, side quest THE LAB NOTES
- [x] Geometry Kingdom (geometry, multiplication): Temple Gate, Garden Court, Pillar Court, Dragon Keep; boss
      THE DIMENSION DRAGON (Lv 17); main quest THE DIMENSION DRAGON, side quest THE ROYAL GARDEN
- [x] Chronos Dimension (sequences, time, advanced algebra): Clock Gate, Tick Isles, Tock Isles, Time Spire; boss
      THE INFINITE OVERLORD (Lv 20); main quest THE INFINITE OVERLORD (ends the game), side quest THE BROKEN CLOCKS
- [x] 10 new wild species (the Monster Trials art), each world harder than the last, seals with difficulty floors
- [x] Portals chain Number Forest → Cavern → Kingdom → Chronos → home; each opens only after that world's boss
- [x] Maps generated by `tools/generate_worlds.py` (layout, collision, art, reachability check)
- Verified by: `test_worlds` (map integrity, portals both ways, consistency, a full playthrough of all three worlds)

## Playtest bug report ✅
- [x] Visual animated hints for every question type (`game/visual_hint.py`)
- [x] Generated chiptune music per world + battle/boss, and sound effects (`tools/generate_audio.py`)
- [x] Choose a companion from the MathDex
- [x] Player walks through NPCs; the broken bridge explains itself; all maps connectivity-tested
- [x] Mathmon Recovery Center: heal by solving maths, with the provided art (`states/clinic_state.py`)
- [x] Mathmart with the requested items and prices (old item names migrated)
- Verified by: `test_bug_report`

## World lore, storyline and narrative ✅
- [x] Lore bible (`docs/LORE.md`): Mathea, the Numera and Axioms, four civilisations, the Last Calculation, a
      layered mystery, Professor Numeris's secret and arc, Vera Tallow (the hooded stranger)
- [x] Prologue, Chapters 1–4, Final chapter "The Last Calculation" with three endings, epilogue; chapter cards
- [x] Visual dialogue system: portraits, names, typewriter text, continue arrow, choices, skip, transitions,
      10 dialogue categories (text only, no audio narration)
- [x] Professor and NPC lines react to story progress; story NPCs appear and leave by flag
- [x] Codex: World History, Characters, MathMon Encyclopedia (all 30 species), Regions, Historical Records, Main Story
- [x] 16 historical records in the maps, the Professor's lab with a locked drawer, contradictions to find
- [x] History, MathMon, secret and final quests with lore links; maths explained in story terms after each seal
- [x] Story progress, lore, choices and endings saved as world flags; old saves migrated
- Verified by: `test_story` (data integrity, dialogue screen, progression, Codex, save/load, all three endings)

## Known limitations (MVP)
- The three new worlds share one generated layout (camp, two wild areas, sanctum), re-themed per world.
- The Crystal Realm remains a bonus area reached from Number Forest.
- The ruins' painted map is too open for a physical gate, so the boss arch is sealed by three puzzle seals.
- Evolved forms reuse their base sprite sheets with a new colourway (generated by `tools/make_variants.py`) and a
  larger drawn size, rather than new art.
- Music and effects are generated chiptunes rather than composed tracks.

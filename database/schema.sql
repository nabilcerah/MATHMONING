-- MATHMON SQLite schema (GDD 23). Applied on every start with CREATE ... IF NOT EXISTS;
-- column additions to older saves are done by database.migrations.

CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, creature TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1, hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL, exp INTEGER NOT NULL DEFAULT 0,
    world TEXT NOT NULL DEFAULT 'NUMBER FOREST',            -- current_map
    x INTEGER NOT NULL DEFAULT 4, y INTEGER NOT NULL DEFAULT 6,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- GDD MONSTERS: every monster the player owns.
CREATE TABLE IF NOT EXISTS monsters (
    monster_instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    species_id TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1, exp INTEGER NOT NULL DEFAULT 0,
    current_hp INTEGER NOT NULL, maximum_hp INTEGER NOT NULL,
    attack INTEGER NOT NULL, defence INTEGER NOT NULL, speed INTEGER NOT NULL,
    evolution_stage INTEGER NOT NULL DEFAULT 1,
    acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_monsters_player ON monsters(player_id);

CREATE TABLE IF NOT EXISTS party (
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    monster_instance_id INTEGER NOT NULL UNIQUE REFERENCES monsters(monster_instance_id) ON DELETE CASCADE,
    party_position INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(player_id, party_position)
);

CREATE TABLE IF NOT EXISTS storage (
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    monster_instance_id INTEGER NOT NULL UNIQUE REFERENCES monsters(monster_instance_id) ON DELETE CASCADE,
    storage_position INTEGER NOT NULL,
    PRIMARY KEY(player_id, storage_position)
);

CREATE TABLE IF NOT EXISTS learning_profiles (
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    mastery_score INTEGER NOT NULL DEFAULT 0,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    last_assessed_at TEXT,
    PRIMARY KEY(player_id, topic)
);

CREATE TABLE IF NOT EXISTS question_history (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL, topic TEXT NOT NULL, subtopic TEXT NOT NULL DEFAULT '',
    difficulty TEXT NOT NULL,
    correct INTEGER NOT NULL, used_hint INTEGER NOT NULL DEFAULT 0,
    attempts_used INTEGER NOT NULL DEFAULT 1,
    learning_score REAL NOT NULL,
    worked_example INTEGER NOT NULL DEFAULT 0,
    prompt TEXT NOT NULL DEFAULT '', submitted TEXT NOT NULL DEFAULT '', expected TEXT NOT NULL DEFAULT '',
    misconception TEXT NOT NULL DEFAULT '',
    context TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_history_player_topic ON question_history(player_id, topic, attempt_id);

CREATE TABLE IF NOT EXISTS quests (
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    quest_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',     -- active | completed
    progress TEXT NOT NULL DEFAULT '{}',       -- JSON: {"step": n, "counters": {...}}
    completed_at TEXT,
    PRIMARY KEY(player_id, quest_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    item TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 0,       -- item = item_id
    PRIMARY KEY(player_id, item)
);

CREATE TABLE IF NOT EXISTS capture_records (
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    species_id TEXT NOT NULL,
    captured_count INTEGER NOT NULL DEFAULT 0,
    seen_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(player_id, species_id)
);

-- The AI Orchestrator's decision log (GDD 14, step 9: "Record the decision and its outcome").
CREATE TABLE IF NOT EXISTS ai_decisions (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    event TEXT NOT NULL, objective TEXT NOT NULL DEFAULT '',
    agents TEXT NOT NULL DEFAULT '', decision TEXT NOT NULL DEFAULT '{}',
    outcome TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    message TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS world_flags (
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    flag TEXT NOT NULL,
    PRIMARY KEY(player_id, flag)
);

-- Pre-GDD tables, kept so older saves and the bonus modes (Arena, Monster Trials) keep working.
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL, topic TEXT NOT NULL, difficulty TEXT NOT NULL,
    prompt TEXT NOT NULL, submitted TEXT NOT NULL, expected TEXT NOT NULL,
    correct INTEGER NOT NULL, concept TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_attempts_player_topic ON attempts(player_id, topic, attempt_id);
CREATE TABLE IF NOT EXISTS topic_stats (
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    topic TEXT NOT NULL, attempted INTEGER NOT NULL DEFAULT 0,
    correct INTEGER NOT NULL DEFAULT 0, streak INTEGER NOT NULL DEFAULT 0,
    mastery INTEGER NOT NULL DEFAULT 0, common_mistake TEXT NOT NULL DEFAULT '',
    last_difficulty TEXT NOT NULL DEFAULT 'easy',
    PRIMARY KEY(player_id, topic)
);
CREATE TABLE IF NOT EXISTS team_members (
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    species TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 1, exp INTEGER NOT NULL DEFAULT 0,
    hp INTEGER NOT NULL, max_hp INTEGER NOT NULL,
    PRIMARY KEY(player_id, species)
);
CREATE TABLE IF NOT EXISTS arena_stats (
    player_id INTEGER PRIMARY KEY REFERENCES players(player_id) ON DELETE CASCADE,
    rating INTEGER NOT NULL DEFAULT 1000, wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0, streak INTEGER NOT NULL DEFAULT 0,
    best_streak INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS trainer_progress (
    player_id INTEGER PRIMARY KEY REFERENCES players(player_id) ON DELETE CASCADE,
    xp INTEGER NOT NULL DEFAULT 0, level INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS monster_records (
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    monster_id TEXT NOT NULL, rank INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0, losses INTEGER NOT NULL DEFAULT 0,
    best_turns INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(player_id, monster_id)
);

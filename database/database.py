"""SQLite storage with automatic schema creation and transactional updates."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import DATABASE_PATH


class Database:
    def __init__(self, path=None):
        self.path = Path(path or DATABASE_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS players (
                    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL, creature TEXT NOT NULL,
                    level INTEGER NOT NULL DEFAULT 1, hp INTEGER NOT NULL,
                    max_hp INTEGER NOT NULL, exp INTEGER NOT NULL DEFAULT 0,
                    world TEXT NOT NULL DEFAULT 'NUMBER FOREST',
                    x INTEGER NOT NULL DEFAULT 4, y INTEGER NOT NULL DEFAULT 6,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
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
                CREATE TABLE IF NOT EXISTS inventory (
                    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
                    item TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(player_id, item)
                );
                CREATE TABLE IF NOT EXISTS world_flags (
                    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
                    flag TEXT NOT NULL,
                    PRIMARY KEY(player_id, flag)
                );
                CREATE TABLE IF NOT EXISTS recommendations (
                    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
                    message TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)


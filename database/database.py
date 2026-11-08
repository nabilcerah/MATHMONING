"""SQLite storage with automatic schema creation, migrations and transactional updates."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import DATABASE_PATH, ROOT

SCHEMA_PATH = ROOT / "database" / "schema.sql"

# Columns added after the first release: (table, column, definition).
MIGRATIONS = (
    ("players", "currency", "INTEGER NOT NULL DEFAULT 0"),
    ("players", "current_region", "TEXT NOT NULL DEFAULT 'number_forest'"),
    ("players", "gdd_version", "INTEGER NOT NULL DEFAULT 0"),
)


class Database:
    def __init__(self, path=None):
        self.path = Path(path or DATABASE_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        """One transaction: committed on success, rolled back if anything inside fails."""
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
            db.executescript(Path(SCHEMA_PATH).read_text(encoding="utf-8"))
            for table, column, definition in MIGRATIONS:
                existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
                if column not in existing:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

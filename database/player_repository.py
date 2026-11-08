"""High-level data access used by game and agents."""
from database.models import PlayerRecord, TopicPerformance


class PlayerRepository:
    def __init__(self, database):
        self.database = database

    @staticmethod
    def _record(row):
        if row is None:
            return None
        return PlayerRecord(row["player_id"], row["name"], row["creature"], row["level"], row["hp"],
                            row["max_hp"], row["exp"], row["world"], row["x"], row["y"])

    def create_player(self, name, creature, max_hp):
        with self.database.connect() as db:
            db.execute("DELETE FROM players")
            cursor = db.execute("INSERT INTO players(name, creature, hp, max_hp) VALUES (?, ?, ?, ?)",
                                (name.strip()[:24] or "Rookie", creature, max_hp, max_hp))
            player_id = cursor.lastrowid
            for item, count in (("Health Potion", 3), ("EXP Booster", 1), ("Learning Crystal", 2)):
                db.execute("INSERT INTO inventory(player_id, item, quantity) VALUES (?, ?, ?)", (player_id, item, count))
            return player_id

    def load_player(self):
        with self.database.connect() as db:
            return self._record(db.execute("SELECT * FROM players ORDER BY player_id DESC LIMIT 1").fetchone())

    def save_player(self, player):
        with self.database.connect() as db:
            db.execute("""UPDATE players SET level=?, hp=?, max_hp=?, exp=?, x=?, y=?, world=?,
                         updated_at=CURRENT_TIMESTAMP WHERE player_id=?""",
                       (player.level, player.hp, player.max_hp, player.exp, player.x, player.y,
                        getattr(player, "world", "number_forest"), player.player_id))

    def record_attempt(self, player_id, question, submitted, correct):
        with self.database.connect() as db:
            db.execute("""INSERT INTO attempts(player_id, question_id, topic, difficulty, prompt,
                         submitted, expected, correct, concept) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (player_id, question.question_id, question.topic, question.difficulty, question.prompt,
                        str(submitted)[:100], question.answer, int(correct), question.concept))
            row = db.execute("SELECT * FROM topic_stats WHERE player_id=? AND topic=?", (player_id, question.topic)).fetchone()
            attempted = (row["attempted"] if row else 0) + 1
            total_correct = (row["correct"] if row else 0) + int(correct)
            streak = (row["streak"] if row else 0) + 1 if correct else 0
            # Mastery requires repeated success and a useful body of evidence.
            accuracy = total_correct / attempted
            mastery = max(0, min(100, round(accuracy * 100 * min(1.0, attempted / 8))))
            recent = db.execute("SELECT correct FROM attempts WHERE player_id=? AND topic=? ORDER BY attempt_id DESC LIMIT 8",
                                (player_id, question.topic)).fetchall()
            recent_acc = sum(item["correct"] for item in recent) / max(1, len(recent))
            mistake = ""
            if not correct:
                mistake = f"Check the steps for {question.concept}; last answer was {str(submitted)[:24]}."
            db.execute("""INSERT INTO topic_stats(player_id, topic, attempted, correct, streak, mastery, common_mistake, last_difficulty)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                         ON CONFLICT(player_id, topic) DO UPDATE SET attempted=excluded.attempted,
                         correct=excluded.correct, streak=excluded.streak, mastery=excluded.mastery,
                         common_mistake=CASE WHEN excluded.common_mistake!='' THEN excluded.common_mistake ELSE topic_stats.common_mistake END,
                         last_difficulty=excluded.last_difficulty""",
                       (player_id, question.topic, attempted, total_correct, streak, mastery, mistake, question.difficulty))
            return {"attempted": attempted, "correct": total_correct, "accuracy": accuracy,
                    "recent_accuracy": recent_acc, "streak": streak, "mastery": mastery, "common_mistake": mistake}

    def get_learning_profile(self, player_id):
        with self.database.connect() as db:
            stats = db.execute("SELECT * FROM topic_stats WHERE player_id=? ORDER BY topic", (player_id,)).fetchall()
            profile = {}
            for row in stats:
                recent = db.execute("SELECT correct FROM attempts WHERE player_id=? AND topic=? ORDER BY attempt_id DESC LIMIT 8",
                                    (player_id, row["topic"])).fetchall()
                profile[row["topic"]] = {
                    "attempted": row["attempted"], "correct": row["correct"],
                    "accuracy": row["correct"] / max(1, row["attempted"]), "mastery": row["mastery"],
                    "streak": row["streak"], "recent_accuracy": sum(r["correct"] for r in recent) / max(1, len(recent)),
                    "common_mistake": row["common_mistake"], "last_difficulty": row["last_difficulty"],
                }
            return profile

    def recent_attempts(self, player_id, limit=5):
        with self.database.connect() as db:
            rows = db.execute("SELECT topic, prompt, submitted, expected, correct, created_at FROM attempts WHERE player_id=? ORDER BY attempt_id DESC LIMIT ?",
                              (player_id, limit)).fetchall()
            return [dict(row) for row in rows]

    def inventory(self, player_id):
        with self.database.connect() as db:
            return {row["item"]: row["quantity"] for row in db.execute("SELECT item, quantity FROM inventory WHERE player_id=?", (player_id,))}

    def use_item(self, player_id, item):
        with self.database.connect() as db:
            row = db.execute("SELECT quantity FROM inventory WHERE player_id=? AND item=?", (player_id, item)).fetchone()
            if not row or row["quantity"] < 1:
                return False
            db.execute("UPDATE inventory SET quantity=quantity-1 WHERE player_id=? AND item=?", (player_id, item))
            return True

    def add_item(self, player_id, item, count=1):
        with self.database.connect() as db:
            db.execute("""INSERT INTO inventory(player_id, item, quantity) VALUES (?, ?, ?)
                         ON CONFLICT(player_id, item) DO UPDATE SET quantity=quantity+excluded.quantity""",
                       (player_id, item, max(0, int(count))))

    def world_flags(self, player_id):
        with self.database.connect() as db:
            return {row["flag"] for row in db.execute("SELECT flag FROM world_flags WHERE player_id=?", (player_id,))}

    def set_world_flag(self, player_id, flag):
        with self.database.connect() as db:
            db.execute("INSERT OR IGNORE INTO world_flags(player_id, flag) VALUES (?, ?)", (player_id, str(flag)[:80]))

    def clear_world_flags(self, player_id, prefix):
        with self.database.connect() as db:
            db.execute("DELETE FROM world_flags WHERE player_id=? AND substr(flag, 1, ?)=?",
                       (player_id, len(prefix), prefix))

    def arena_stats(self, player_id):
        with self.database.connect() as db:
            row = db.execute("SELECT rating, wins, losses, streak, best_streak FROM arena_stats WHERE player_id=?",
                             (player_id,)).fetchone()
            return dict(row) if row else {"rating": 1000, "wins": 0, "losses": 0, "streak": 0, "best_streak": 0}

    def save_arena_stats(self, player_id, stats):
        with self.database.connect() as db:
            db.execute("""INSERT INTO arena_stats(player_id, rating, wins, losses, streak, best_streak)
                          VALUES (?, ?, ?, ?, ?, ?)
                          ON CONFLICT(player_id) DO UPDATE SET rating=excluded.rating, wins=excluded.wins,
                          losses=excluded.losses, streak=excluded.streak, best_streak=excluded.best_streak""",
                       (player_id, stats["rating"], stats["wins"], stats["losses"], stats["streak"],
                        stats["best_streak"]))

    def add_recommendation(self, player_id, message):
        with self.database.connect() as db:
            db.execute("INSERT INTO recommendations(player_id, message) VALUES (?, ?)", (player_id, message[:220]))

    def recommendations(self, player_id, limit=3):
        with self.database.connect() as db:
            rows = db.execute("SELECT message FROM recommendations WHERE player_id=? ORDER BY recommendation_id DESC LIMIT ?",
                              (player_id, limit)).fetchall()
            return [row["message"] for row in rows]

    def overall_summary(self, player_id):
        with self.database.connect() as db:
            row = db.execute("SELECT COUNT(*) attempted, COALESCE(SUM(correct),0) correct FROM attempts WHERE player_id=?", (player_id,)).fetchone()
            return dict(attempted=row["attempted"], correct=row["correct"],
                        accuracy=row["correct"] / max(1, row["attempted"]))

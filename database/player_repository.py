"""High-level data access used by the game and the agents (GDD 23).

Critical changes (captures, evolution, rewards, purchases) each happen inside one transaction.
"""
import json

from database.models import PlayerRecord
from mathematics import curriculum, mastery_manager
from monsters import monster_factory
from monsters.monster import Monster, exp_to_next
from monsters.monster_data import canonical_species, has_species, rules
from monsters.monster_party import MonsterParty

GDD_VERSION = 1


class PlayerRepository:
    def __init__(self, database):
        self.database = database

    # ================================================================== players
    @staticmethod
    def _record(row):
        if row is None:
            return None
        keys = row.keys()
        return PlayerRecord(row["player_id"], row["name"], row["creature"], row["level"], row["hp"],
                            row["max_hp"], row["exp"], row["world"], row["x"], row["y"],
                            row["currency"] if "currency" in keys else 0,
                            row["current_region"] if "current_region" in keys else "number_forest")

    def create_player(self, name, creature, max_hp=None, starter_level=1):
        """A brand-new trainer with ``creature`` as their starter (one save slot, as before)."""
        species_id = canonical_species(creature)
        starter = monster_factory.create(species_id, starter_level)
        cfg = rules()
        with self.database.connect() as db:
            db.execute("DELETE FROM players")
            cursor = db.execute("""INSERT INTO players(name, creature, level, hp, max_hp, currency, gdd_version)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (name.strip()[:24] or "Rookie", species_id, starter.level, starter.hp,
                                 starter.max_hp, cfg["coins"]["start"], GDD_VERSION))
            player_id = cursor.lastrowid
            for item, count in cfg["starting_items"].items():
                db.execute("INSERT INTO inventory(player_id, item, quantity) VALUES (?, ?, ?)", (player_id, item, count))
            self._insert_monster(db, player_id, starter)
            db.execute("INSERT INTO party(player_id, monster_instance_id, party_position, is_active) VALUES (?, ?, 0, 1)",
                       (player_id, starter.instance_id))
            self._bump_capture(db, player_id, species_id, captured=1, seen=1)
        return player_id

    def load_player(self):
        with self.database.connect() as db:
            return self._record(db.execute("SELECT * FROM players ORDER BY player_id DESC LIMIT 1").fetchone())

    def save_player(self, player):
        """Position, map and the lead monster's summary (shown on the title screen)."""
        with self.database.connect() as db:
            db.execute("""UPDATE players SET level=?, hp=?, max_hp=?, exp=?, x=?, y=?, world=?,
                         updated_at=CURRENT_TIMESTAMP WHERE player_id=?""",
                       (player.level, player.hp, player.max_hp, player.exp, player.x, player.y,
                        getattr(player, "world", "number_forest"), player.player_id))

    # ================================================================== currency
    def coins(self, player_id):
        with self.database.connect() as db:
            row = db.execute("SELECT currency FROM players WHERE player_id=?", (player_id,)).fetchone()
            return int(row["currency"]) if row else 0

    def add_coins(self, player_id, amount):
        with self.database.connect() as db:
            db.execute("UPDATE players SET currency = MAX(0, currency + ?) WHERE player_id=?", (int(amount), player_id))

    def buy(self, player_id, item, price, count=1):
        """Spend coins and add the item in ONE transaction. Returns False if the player can't afford it."""
        total = int(price) * int(count)
        with self.database.connect() as db:
            row = db.execute("SELECT currency FROM players WHERE player_id=?", (player_id,)).fetchone()
            if not row or row["currency"] < total:
                return False
            db.execute("UPDATE players SET currency = currency - ? WHERE player_id=?", (total, player_id))
            db.execute("""INSERT INTO inventory(player_id, item, quantity) VALUES (?, ?, ?)
                          ON CONFLICT(player_id, item) DO UPDATE SET quantity=quantity+excluded.quantity""",
                       (player_id, item, int(count)))
            return True

    def sell(self, player_id, item, price):
        with self.database.connect() as db:
            row = db.execute("SELECT quantity FROM inventory WHERE player_id=? AND item=?", (player_id, item)).fetchone()
            if not row or row["quantity"] < 1:
                return False
            db.execute("UPDATE inventory SET quantity=quantity-1 WHERE player_id=? AND item=?", (player_id, item))
            db.execute("UPDATE players SET currency = currency + ? WHERE player_id=?", (int(price), player_id))
            return True

    # ================================================================== monsters
    @staticmethod
    def _monster(row):
        return Monster(row["species_id"], row["level"], row["exp"], row["current_hp"], row["maximum_hp"],
                       row["attack"], row["defence"], row["speed"], row["evolution_stage"],
                       row["monster_instance_id"], row["acquired_at"])

    @staticmethod
    def _insert_monster(db, player_id, monster):
        cursor = db.execute("""INSERT INTO monsters(player_id, species_id, level, exp, current_hp, maximum_hp,
                               attack, defence, speed, evolution_stage) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (player_id, monster.species_id, monster.level, monster.exp, monster.hp, monster.max_hp,
                             monster.attack, monster.defence, monster.speed, monster.evolution_stage))
        monster.instance_id = cursor.lastrowid
        return monster

    @staticmethod
    def _update_monster(db, monster):
        db.execute("""UPDATE monsters SET species_id=?, level=?, exp=?, current_hp=?, maximum_hp=?, attack=?,
                      defence=?, speed=?, evolution_stage=? WHERE monster_instance_id=?""",
                   (monster.species_id, monster.level, monster.exp, monster.hp, monster.max_hp, monster.attack,
                    monster.defence, monster.speed, monster.evolution_stage, monster.instance_id))

    def save_monster(self, player_id, monster):
        with self.database.connect() as db:
            if monster.instance_id is None:
                self._insert_monster(db, player_id, monster)
            else:
                self._update_monster(db, monster)
            self._sync_lead(db, player_id)

    def load_party(self, player_id):
        """The player's party and Sanctuary. Saves from before the GDD rebuild are migrated once."""
        with self.database.connect() as db:
            if not db.execute("SELECT 1 FROM party WHERE player_id=? LIMIT 1", (player_id,)).fetchone():
                self._migrate_legacy_team(db, player_id)
            party_rows = db.execute("""SELECT m.*, p.is_active FROM party p JOIN monsters m
                                       ON m.monster_instance_id = p.monster_instance_id
                                       WHERE p.player_id=? ORDER BY p.party_position""", (player_id,)).fetchall()
            storage_rows = db.execute("""SELECT m.* FROM storage s JOIN monsters m
                                         ON m.monster_instance_id = s.monster_instance_id
                                         WHERE s.player_id=? ORDER BY s.storage_position""", (player_id,)).fetchall()
        party = [self._monster(row) for row in party_rows]
        active = next((i for i, row in enumerate(party_rows) if row["is_active"]), 0)
        return MonsterParty(party, [self._monster(row) for row in storage_rows], active)

    def save_party(self, player_id, party):
        """Write every monster plus the party/storage layout in one transaction."""
        with self.database.connect() as db:
            for monster in party.all_monsters():
                if monster.instance_id is None:
                    self._insert_monster(db, player_id, monster)
                else:
                    self._update_monster(db, monster)
            db.execute("DELETE FROM party WHERE player_id=?", (player_id,))
            db.execute("DELETE FROM storage WHERE player_id=?", (player_id,))
            for position, monster in enumerate(party.party):
                db.execute("INSERT INTO party(player_id, monster_instance_id, party_position, is_active) VALUES (?, ?, ?, ?)",
                           (player_id, monster.instance_id, position, int(position == party.active_index)))
            for position, monster in enumerate(party.storage):
                db.execute("INSERT INTO storage(player_id, monster_instance_id, storage_position) VALUES (?, ?, ?)",
                           (player_id, monster.instance_id, position))
            self._sync_lead(db, player_id)

    def _sync_lead(self, db, player_id):
        """Mirror the lead monster onto the players row (title screen 'CONTINUE (name, Lv n)')."""
        row = db.execute("""SELECT m.* FROM party p JOIN monsters m ON m.monster_instance_id = p.monster_instance_id
                            WHERE p.player_id=? ORDER BY p.party_position LIMIT 1""", (player_id,)).fetchone()
        if row:
            db.execute("UPDATE players SET creature=?, level=?, hp=?, max_hp=?, exp=? WHERE player_id=?",
                       (row["species_id"], row["level"], row["current_hp"], row["maximum_hp"], row["exp"], player_id))

    def _migrate_legacy_team(self, db, player_id):
        """Pre-GDD saves kept the starter on the players row and captures in team_members."""
        player = db.execute("SELECT * FROM players WHERE player_id=?", (player_id,)).fetchone()
        if not player:
            return
        monsters = [self._legacy_monster(player["creature"], player["level"], player["exp"], player["hp"])]
        for row in db.execute("SELECT * FROM team_members WHERE player_id=? ORDER BY rowid", (player_id,)):
            if has_species(row["species"]):
                monsters.append(self._legacy_monster(row["species"], row["level"], row["exp"], row["hp"]))
        party = MonsterParty()
        for monster in monsters:
            self._insert_monster(db, player_id, monster)
            if not party.party_full:
                party.party.append(monster)
            elif not party.storage_full:
                party.storage.append(monster)
        for position, monster in enumerate(party.party):
            db.execute("INSERT INTO party(player_id, monster_instance_id, party_position, is_active) VALUES (?, ?, ?, ?)",
                       (player_id, monster.instance_id, position, int(position == 0)))
        for position, monster in enumerate(party.storage):
            db.execute("INSERT INTO storage(player_id, monster_instance_id, storage_position) VALUES (?, ?, ?)",
                       (player_id, monster.instance_id, position))
        for monster in monsters:
            self._bump_capture(db, player_id, monster.species_id, captured=1)
        coins = rules()["coins"]["start"]
        db.execute("UPDATE players SET currency = MAX(currency, ?), gdd_version=? WHERE player_id=?",
                   (coins, GDD_VERSION, player_id))
        for item, count in rules()["starting_items"].items():
            db.execute("""INSERT INTO inventory(player_id, item, quantity) VALUES (?, ?, ?)
                          ON CONFLICT(player_id, item) DO NOTHING""", (player_id, item, count))

    @staticmethod
    def _legacy_monster(species_id, level, exp, hp):
        monster = monster_factory.create(canonical_species(species_id), level)
        monster.exp = max(0, min(int(exp), exp_to_next(monster.level) - 1))
        monster.hp = max(0, min(int(hp), monster.max_hp)) if hp is not None else monster.max_hp
        return monster

    # ================================================================== learning (GDD 9.4)
    def record_assessment(self, player_id, question, correct, used_hint=False, attempts_used=1,
                          learning_score=None, submitted="", misconception="", worked_example=False, context=""):
        """Store one assessed question and recompute that topic's mastery from its last 20 scores."""
        topic = curriculum.mastery_topic(getattr(question, "topic", "reasoning"))
        if learning_score is None:
            learning_score = 1.0 if correct else 0.0
        difficulty = curriculum.normalise_difficulty(getattr(question, "difficulty", "foundation"))
        with self.database.connect() as db:
            db.execute("""INSERT INTO question_history(player_id, question_id, topic, subtopic, difficulty, correct,
                          used_hint, attempts_used, learning_score, worked_example, prompt, submitted, expected,
                          misconception, context) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (player_id, str(getattr(question, "question_id", ""))[:60], topic,
                        str(getattr(question, "subtopic", getattr(question, "concept", "")))[:40], difficulty,
                        int(bool(correct)), int(bool(used_hint)), int(attempts_used), float(learning_score),
                        int(bool(worked_example)), str(getattr(question, "prompt", ""))[:160], str(submitted)[:40],
                        str(getattr(question, "answer", ""))[:40], str(misconception)[:40], str(context)[:20]))
            return self._refresh_profile(db, player_id, topic)

    def _refresh_profile(self, db, player_id, topic):
        window = mastery_manager.window()
        rows = db.execute("""SELECT learning_score FROM question_history WHERE player_id=? AND topic=?
                             ORDER BY attempt_id DESC LIMIT ?""", (player_id, topic, window)).fetchall()
        evidence = db.execute("SELECT COUNT(*) n FROM question_history WHERE player_id=? AND topic=?",
                              (player_id, topic)).fetchone()["n"]
        score = mastery_manager.mastery_score([row["learning_score"] for row in reversed(rows)])
        db.execute("""INSERT INTO learning_profiles(player_id, topic, mastery_score, evidence_count, last_assessed_at)
                      VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                      ON CONFLICT(player_id, topic) DO UPDATE SET mastery_score=excluded.mastery_score,
                      evidence_count=excluded.evidence_count, last_assessed_at=excluded.last_assessed_at""",
                   (player_id, topic, score, evidence))
        return {"topic": topic, "mastery": score, "evidence": evidence}

    def learning_profile(self, player_id):
        """{topic: {mastery, evidence, band, sufficient, recent_accuracy, hint_rate, last_assessed_at}}"""
        with self.database.connect() as db:
            rows = db.execute("SELECT * FROM learning_profiles WHERE player_id=?", (player_id,)).fetchall()
            profile = {}
            for row in rows:
                recent = db.execute("""SELECT correct, used_hint, attempts_used FROM question_history
                                       WHERE player_id=? AND topic=? ORDER BY attempt_id DESC LIMIT 8""",
                                    (player_id, row["topic"])).fetchall()
                status = mastery_manager.status(row["mastery_score"], row["evidence_count"])
                profile[row["topic"]] = {
                    "mastery": row["mastery_score"], "evidence": row["evidence_count"],
                    "band": status.band, "label": status.label, "sufficient": status.sufficient,
                    "recent_accuracy": sum(r["correct"] for r in recent) / max(1, len(recent)),
                    "hint_rate": sum(r["used_hint"] for r in recent) / max(1, len(recent)),
                    "failed_attempts": sum(1 for r in recent if r["attempts_used"] >= 2),
                    "recent_count": len(recent), "last_assessed_at": row["last_assessed_at"],
                }
            return profile

    def mastery(self, player_id, topic):
        with self.database.connect() as db:
            row = db.execute("SELECT mastery_score FROM learning_profiles WHERE player_id=? AND topic=?",
                             (player_id, curriculum.mastery_topic(topic))).fetchone()
            return int(row["mastery_score"]) if row else 0

    def question_history(self, player_id, topic=None, limit=20):
        query = "SELECT * FROM question_history WHERE player_id=?"
        args = [player_id]
        if topic:
            query += " AND topic=?"
            args.append(curriculum.mastery_topic(topic))
        query += " ORDER BY attempt_id DESC LIMIT ?"
        args.append(limit)
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(query, args).fetchall()]

    def history_summary(self, player_id):
        with self.database.connect() as db:
            row = db.execute("""SELECT COUNT(*) attempted, COALESCE(SUM(correct), 0) correct,
                                COALESCE(SUM(used_hint), 0) hints FROM question_history WHERE player_id=?""",
                             (player_id,)).fetchone()
            return {"attempted": row["attempted"], "correct": row["correct"], "hints": row["hints"],
                    "accuracy": row["correct"] / max(1, row["attempted"])}

    # ================================================================== quests
    def quest_states(self, player_id):
        with self.database.connect() as db:
            rows = db.execute("SELECT * FROM quests WHERE player_id=?", (player_id,)).fetchall()
            return {row["quest_id"]: {"status": row["status"], "progress": json.loads(row["progress"] or "{}"),
                                      "completed_at": row["completed_at"]} for row in rows}

    def save_quest(self, player_id, quest_id, status, progress):
        with self.database.connect() as db:
            db.execute("""INSERT INTO quests(player_id, quest_id, status, progress, completed_at)
                          VALUES (?, ?, ?, ?, CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP END)
                          ON CONFLICT(player_id, quest_id) DO UPDATE SET status=excluded.status,
                          progress=excluded.progress,
                          completed_at=COALESCE(quests.completed_at, excluded.completed_at)""",
                       (player_id, quest_id, status, json.dumps(progress), status))

    def complete_quest(self, player_id, quest_id, progress, rewards):
        """Mark a quest complete and grant its deterministic rewards in one transaction.
        EXP is applied to monsters by the caller (it saves the party afterwards)."""
        with self.database.connect() as db:
            row = db.execute("SELECT status FROM quests WHERE player_id=? AND quest_id=?", (player_id, quest_id)).fetchone()
            if row and row["status"] == "completed":
                return False
            db.execute("""INSERT INTO quests(player_id, quest_id, status, progress, completed_at)
                          VALUES (?, ?, 'completed', ?, CURRENT_TIMESTAMP)
                          ON CONFLICT(player_id, quest_id) DO UPDATE SET status='completed',
                          progress=excluded.progress, completed_at=CURRENT_TIMESTAMP""",
                       (player_id, quest_id, json.dumps(progress)))
            db.execute("UPDATE players SET currency = currency + ? WHERE player_id=?", (int(rewards.get("coins", 0)), player_id))
            for item, count in rewards.get("items", {}).items():
                db.execute("""INSERT INTO inventory(player_id, item, quantity) VALUES (?, ?, ?)
                              ON CONFLICT(player_id, item) DO UPDATE SET quantity=quantity+excluded.quantity""",
                           (player_id, item, int(count)))
            for flag in rewards.get("flags", []):
                db.execute("INSERT OR IGNORE INTO world_flags(player_id, flag) VALUES (?, ?)", (player_id, flag))
            return True

    # ================================================================== capture records
    @staticmethod
    def _bump_capture(db, player_id, species_id, captured=0, seen=0):
        db.execute("""INSERT INTO capture_records(player_id, species_id, captured_count, seen_count) VALUES (?, ?, ?, ?)
                      ON CONFLICT(player_id, species_id) DO UPDATE SET
                      captured_count=captured_count+excluded.captured_count, seen_count=seen_count+excluded.seen_count""",
                   (player_id, species_id, captured, seen))

    def record_seen(self, player_id, species_id):
        with self.database.connect() as db:
            self._bump_capture(db, player_id, species_id, seen=1)

    def record_capture(self, player_id, party, species_id):
        """Save the new monster and its collection record together (one transaction)."""
        self.save_party(player_id, party)
        with self.database.connect() as db:
            self._bump_capture(db, player_id, species_id, captured=1)

    def capture_records(self, player_id):
        with self.database.connect() as db:
            return {row["species_id"]: {"captured": row["captured_count"], "seen": row["seen_count"]}
                    for row in db.execute("SELECT * FROM capture_records WHERE player_id=?", (player_id,))}

    # ================================================================== AI decisions
    def log_decision(self, player_id, event, objective, agents, decision, outcome=""):
        with self.database.connect() as db:
            cursor = db.execute("""INSERT INTO ai_decisions(player_id, event, objective, agents, decision, outcome)
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (player_id, event[:40], objective[:200], ",".join(agents)[:200],
                                 json.dumps(decision, default=str)[:4000], outcome[:200]))
            return cursor.lastrowid

    def set_decision_outcome(self, decision_id, outcome):
        with self.database.connect() as db:
            db.execute("UPDATE ai_decisions SET outcome=? WHERE decision_id=?", (outcome[:200], decision_id))

    def recent_decisions(self, player_id, limit=5, event=None):
        query = "SELECT * FROM ai_decisions WHERE player_id=?"
        args = [player_id]
        if event:
            query += " AND event=?"
            args.append(event)
        query += " ORDER BY decision_id DESC LIMIT ?"
        args.append(limit)
        with self.database.connect() as db:
            rows = db.execute(query, args).fetchall()
            return [{**dict(row), "decision": json.loads(row["decision"] or "{}")} for row in rows]

    # ================================================================== inventory
    def inventory(self, player_id):
        with self.database.connect() as db:
            return {row["item"]: row["quantity"] for row in
                    db.execute("SELECT item, quantity FROM inventory WHERE player_id=? AND quantity > 0", (player_id,))}

    def item_count(self, player_id, item):
        return self.inventory(player_id).get(item, 0)

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

    def set_inventory(self, player_id, counts):
        """Write a whole bag back (after a battle used items from a working copy)."""
        with self.database.connect() as db:
            for item, count in counts.items():
                db.execute("""INSERT INTO inventory(player_id, item, quantity) VALUES (?, ?, ?)
                              ON CONFLICT(player_id, item) DO UPDATE SET quantity=excluded.quantity""",
                           (player_id, item, max(0, int(count))))

    # ================================================================== flags
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

    # ================================================================== recommendations
    def add_recommendation(self, player_id, message):
        with self.database.connect() as db:
            db.execute("INSERT INTO recommendations(player_id, message) VALUES (?, ?)", (player_id, message[:220]))

    def recommendations(self, player_id, limit=3):
        with self.database.connect() as db:
            rows = db.execute("SELECT message FROM recommendations WHERE player_id=? ORDER BY recommendation_id DESC LIMIT ?",
                              (player_id, limit)).fetchall()
            return [row["message"] for row in rows]

    # ================================================================== pre-GDD API (Arena, Trials)
    def record_attempt(self, player_id, question, submitted, correct):
        """Arena and Monster Trials answers: kept in the old tables AND counted as assessed
        questions, so there is one mastery profile for the whole game."""
        with self.database.connect() as db:
            db.execute("""INSERT INTO attempts(player_id, question_id, topic, difficulty, prompt,
                         submitted, expected, correct, concept) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (player_id, question.question_id, question.topic, question.difficulty, question.prompt,
                        str(submitted)[:100], question.answer, int(correct), question.concept))
            row = db.execute("SELECT * FROM topic_stats WHERE player_id=? AND topic=?", (player_id, question.topic)).fetchone()
            attempted = (row["attempted"] if row else 0) + 1
            total_correct = (row["correct"] if row else 0) + int(correct)
            streak = (row["streak"] if row else 0) + 1 if correct else 0
            accuracy = total_correct / attempted
            legacy_mastery = max(0, min(100, round(accuracy * 100 * min(1.0, attempted / 8))))
            recent = db.execute("SELECT correct FROM attempts WHERE player_id=? AND topic=? ORDER BY attempt_id DESC LIMIT 8",
                                (player_id, question.topic)).fetchall()
            recent_acc = sum(item["correct"] for item in recent) / max(1, len(recent))
            mistake = f"Check the steps for {question.concept}; last answer was {str(submitted)[:24]}." if not correct else ""
            db.execute("""INSERT INTO topic_stats(player_id, topic, attempted, correct, streak, mastery, common_mistake, last_difficulty)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                         ON CONFLICT(player_id, topic) DO UPDATE SET attempted=excluded.attempted,
                         correct=excluded.correct, streak=excluded.streak, mastery=excluded.mastery,
                         common_mistake=CASE WHEN excluded.common_mistake!='' THEN excluded.common_mistake ELSE topic_stats.common_mistake END,
                         last_difficulty=excluded.last_difficulty""",
                       (player_id, question.topic, attempted, total_correct, streak, legacy_mastery, mistake, question.difficulty))
        self.record_assessment(player_id, question, correct, submitted=submitted, context="bonus")
        return {"attempted": attempted, "correct": total_correct, "accuracy": accuracy,
                "recent_accuracy": recent_acc, "streak": streak, "mastery": legacy_mastery, "common_mistake": mistake}

    def get_learning_profile(self, player_id):
        """Pre-GDD per-topic stats (used by the Arena's question picker)."""
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
            rows = db.execute("""SELECT topic, prompt, submitted, expected, correct, timestamp AS created_at
                                 FROM question_history WHERE player_id=? ORDER BY attempt_id DESC LIMIT ?""",
                              (player_id, limit)).fetchall()
            return [dict(row) for row in rows]

    def overall_summary(self, player_id):
        return self.history_summary(player_id)

    def team_members(self, player_id):
        with self.database.connect() as db:
            rows = db.execute("SELECT species, level, exp, hp, max_hp FROM team_members WHERE player_id=? "
                              "ORDER BY rowid", (player_id,)).fetchall()
            return [dict(row) for row in rows]

    def save_member(self, player_id, member):
        """Old Team API: members are Monster instances now, so this saves the monster."""
        if isinstance(member, Monster):
            self.save_monster(player_id, member)

    def trainer_progress(self, player_id):
        with self.database.connect() as db:
            row = db.execute("SELECT xp, level FROM trainer_progress WHERE player_id=?", (player_id,)).fetchone()
            return dict(row) if row else {"xp": 0, "level": 1}

    def save_trainer_progress(self, player_id, xp, level):
        with self.database.connect() as db:
            db.execute("""INSERT INTO trainer_progress(player_id, xp, level) VALUES (?, ?, ?)
                          ON CONFLICT(player_id) DO UPDATE SET xp=excluded.xp, level=excluded.level""",
                       (player_id, int(xp), int(level)))

    def monster_records(self, player_id):
        with self.database.connect() as db:
            rows = db.execute("SELECT monster_id, rank, wins, losses, best_turns FROM monster_records WHERE player_id=?",
                              (player_id,)).fetchall()
            return {row["monster_id"]: dict(row) for row in rows}

    def save_monster_record(self, player_id, record):
        with self.database.connect() as db:
            db.execute("""INSERT INTO monster_records(player_id, monster_id, rank, wins, losses, best_turns)
                          VALUES (?, ?, ?, ?, ?, ?)
                          ON CONFLICT(player_id, monster_id) DO UPDATE SET rank=excluded.rank, wins=excluded.wins,
                          losses=excluded.losses, best_turns=excluded.best_turns""",
                       (player_id, record["monster_id"], record["rank"], record["wins"], record["losses"],
                        record.get("best_turns", 0)))

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

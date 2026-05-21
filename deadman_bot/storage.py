from __future__ import annotations

import os
import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS deadman_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    message TEXT NOT NULL,
    due_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    sent_at INTEGER,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at INTEGER,
    failed_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_deadman_due ON deadman_entries (due_at);
CREATE INDEX IF NOT EXISTS idx_deadman_chat ON deadman_entries (chat_id);
"""

COLUMN_DEFINITIONS = {
    "attempts": "attempts INTEGER NOT NULL DEFAULT 0",
    "last_attempt_at": "last_attempt_at INTEGER",
    "failed_at": "failed_at INTEGER",
}


class Storage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            self._ensure_column(conn, "attempts")
            self._ensure_column(conn, "last_attempt_at")
            self._ensure_column(conn, "failed_at")
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, name: str) -> None:
        cur = conn.execute("PRAGMA table_info(deadman_entries)")
        columns = {row["name"] for row in cur.fetchall()}
        if name not in columns:
            definition = COLUMN_DEFINITIONS.get(name)
            if not definition:
                raise ValueError(f"Unknown column definition for {name}")
            conn.execute(f"ALTER TABLE deadman_entries ADD COLUMN {definition}")

    def upsert_entry(
        self, chat_id: int, email: str, message: str, due_at: int, now_ts: int
    ) -> None:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT id FROM deadman_entries
                WHERE chat_id = ? AND sent_at IS NULL AND failed_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (chat_id,),
            )
            row = cur.fetchone()
            if row:
                entry_id = row["id"]
                conn.execute(
                    """
                    UPDATE deadman_entries
                    SET email = ?, message = ?, due_at = ?, updated_at = ?,
                        attempts = 0, last_attempt_at = NULL, failed_at = NULL
                    WHERE id = ?
                    """,
                    (email, message, due_at, now_ts, entry_id),
                )
                conn.execute(
                    """
                    DELETE FROM deadman_entries
                    WHERE chat_id = ? AND sent_at IS NULL AND failed_at IS NULL AND id != ?
                    """,
                    (chat_id, entry_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO deadman_entries
                        (chat_id, email, message, due_at, created_at, updated_at, sent_at, attempts, failed_at)
                    VALUES (?, ?, ?, ?, ?, ?, NULL, 0, NULL)
                    """,
                    (chat_id, email, message, due_at, now_ts, now_ts),
                )
            conn.commit()

    def get_active_entry(self, chat_id: int) -> sqlite3.Row | None:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM deadman_entries
                WHERE chat_id = ? AND sent_at IS NULL AND failed_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (chat_id,),
            )
            return cur.fetchone()

    def update_due_at(self, entry_id: int, due_at: int, now_ts: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE deadman_entries SET due_at = ?, updated_at = ? WHERE id = ?",
                (due_at, now_ts, entry_id),
            )
            conn.commit()

    def delete_active_entries(self, chat_id: int) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                DELETE FROM deadman_entries
                WHERE chat_id = ? AND sent_at IS NULL AND failed_at IS NULL
                """,
                (chat_id,),
            )
            conn.commit()
            return cur.rowcount

    def get_due_entries(
        self, now_ts: int, retry_after_seconds: int
    ) -> list[sqlite3.Row]:
        retry_cutoff = now_ts - retry_after_seconds
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM deadman_entries
                WHERE sent_at IS NULL
                  AND failed_at IS NULL
                  AND due_at <= ?
                  AND (last_attempt_at IS NULL OR last_attempt_at <= ?)
                ORDER BY due_at ASC
                """,
                (now_ts, retry_cutoff),
            )
            return list(cur.fetchall())

    def record_attempt(self, entry_id: int, now_ts: int) -> int:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE deadman_entries
                SET attempts = attempts + 1, last_attempt_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now_ts, now_ts, entry_id),
            )
            cur = conn.execute(
                "SELECT attempts FROM deadman_entries WHERE id = ?",
                (entry_id,),
            )
            attempts = cur.fetchone()["attempts"]
            conn.commit()
            return attempts

    def mark_failed(self, entry_id: int, now_ts: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE deadman_entries SET failed_at = ?, updated_at = ? WHERE id = ?",
                (now_ts, now_ts, entry_id),
            )
            conn.commit()

    def mark_sent(self, entry_id: int, now_ts: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE deadman_entries SET sent_at = ?, updated_at = ? WHERE id = ?",
                (now_ts, now_ts, entry_id),
            )
            conn.commit()

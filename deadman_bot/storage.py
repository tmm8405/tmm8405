from __future__ import annotations

import os
import sqlite3
from typing import Iterable


SCHEMA = """
CREATE TABLE IF NOT EXISTS deadman_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    message TEXT NOT NULL,
    due_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    sent_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_deadman_due ON deadman_entries (due_at);
CREATE INDEX IF NOT EXISTS idx_deadman_chat ON deadman_entries (chat_id);
"""


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
            conn.commit()

    def upsert_entry(
        self, chat_id: int, email: str, message: str, due_at: int, now_ts: int
    ) -> None:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT id FROM deadman_entries
                WHERE chat_id = ? AND sent_at IS NULL
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
                    SET email = ?, message = ?, due_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (email, message, due_at, now_ts, entry_id),
                )
                conn.execute(
                    """
                    DELETE FROM deadman_entries
                    WHERE chat_id = ? AND sent_at IS NULL AND id != ?
                    """,
                    (chat_id, entry_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO deadman_entries
                        (chat_id, email, message, due_at, created_at, updated_at, sent_at)
                    VALUES (?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (chat_id, email, message, due_at, now_ts, now_ts),
                )
            conn.commit()

    def get_active_entry(self, chat_id: int) -> sqlite3.Row | None:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM deadman_entries
                WHERE chat_id = ? AND sent_at IS NULL
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

    def delete_active_entry(self, chat_id: int) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM deadman_entries WHERE chat_id = ? AND sent_at IS NULL",
                (chat_id,),
            )
            conn.commit()
            return cur.rowcount

    def get_due_entries(self, now_ts: int) -> Iterable[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM deadman_entries
                WHERE sent_at IS NULL AND due_at <= ?
                ORDER BY due_at ASC
                """,
                (now_ts,),
            )
            return list(cur.fetchall())

    def mark_sent(self, entry_id: int, now_ts: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE deadman_entries SET sent_at = ?, updated_at = ? WHERE id = ?",
                (now_ts, now_ts, entry_id),
            )
            conn.commit()

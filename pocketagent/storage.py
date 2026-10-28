"""Local SQLite storage for PocketAgent conversations."""

from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DEFAULT_TITLE = "New conversation"
VALID_MODES = {"chat", "reading"}


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    mode: str
    model: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Message:
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: str


def default_database_path() -> Path:
    """Return a per-user Windows data path, outside the source checkout."""
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local_app_data / "PocketAgent" / "conversations.sqlite3"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conversation_from_row(row: sqlite3.Row) -> Conversation:
    return Conversation(
        id=row["id"],
        title=row["title"],
        mode=row["mode"],
        model=row["model"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ConversationStore:
    """A small, local-only SQLite conversation store."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=5)
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

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'chat',
                    model TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id)
                        REFERENCES conversations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS messages_by_conversation
                    ON messages(conversation_id, id);
                """
            )
            # Keep existing local databases usable if this schema grows later.
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(conversations)")
            }
            if "mode" not in columns:
                connection.execute(
                    "ALTER TABLE conversations ADD COLUMN mode TEXT NOT NULL DEFAULT 'chat'"
                )
            if "model" not in columns:
                connection.execute("ALTER TABLE conversations ADD COLUMN model TEXT")

    def create_conversation(
        self, *, mode: str = "chat", model: str | None = None
    ) -> Conversation:
        if mode not in VALID_MODES:
            raise ValueError(f"Unknown conversation mode: {mode}")
        now = _utc_now()
        conversation_id = uuid.uuid4().hex
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO conversations
                   (id, title, mode, model, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (conversation_id, DEFAULT_TITLE, mode, model, now, now),
            )
        return self.get_conversation(conversation_id)

    def list_conversations(self) -> list[Conversation]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT id, title, mode, model, created_at, updated_at
                   FROM conversations ORDER BY updated_at DESC, id DESC"""
            ).fetchall()
        return [_conversation_from_row(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> Conversation:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT id, title, mode, model, created_at, updated_at
                   FROM conversations WHERE id = ?""",
                (conversation_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Conversation not found: {conversation_id}")
        return _conversation_from_row(row)

    def update_settings(
        self,
        conversation_id: str,
        *,
        mode: str,
        model: str | None,
    ) -> None:
        if mode not in VALID_MODES:
            raise ValueError(f"Unknown conversation mode: {mode}")
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE conversations SET mode = ?, model = ?, updated_at = ?
                   WHERE id = ?""",
                (mode, model, _utc_now(), conversation_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Conversation not found: {conversation_id}")

    def add_message(
        self, conversation_id: str, *, role: str, content: str
    ) -> Message:
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unsupported message role: {role}")
        if not content.strip():
            raise ValueError("Message content cannot be empty")

        now = _utc_now()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT title FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Conversation not found: {conversation_id}")
            cursor = connection.execute(
                """INSERT INTO messages (conversation_id, role, content, created_at)
                   VALUES (?, ?, ?, ?)""",
                (conversation_id, role, content, now),
            )
            title = row["title"]
            if role == "user" and title == DEFAULT_TITLE:
                title = " ".join(content.split())[:64].rstrip()
                connection.execute(
                    "UPDATE conversations SET title = ? WHERE id = ?",
                    (title or DEFAULT_TITLE, conversation_id),
                )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            message_id = cursor.lastrowid
        return Message(
            id=int(message_id),
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=now,
        )

    def get_messages(self, conversation_id: str) -> list[Message]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT id, conversation_id, role, content, created_at
                   FROM messages WHERE conversation_id = ? ORDER BY id""",
                (conversation_id,),
            ).fetchall()
        return [
            Message(
                id=row["id"],
                conversation_id=row["conversation_id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def clear_conversation(self, conversation_id: str) -> None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Conversation not found: {conversation_id}")
            connection.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
            )
            connection.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (DEFAULT_TITLE, _utc_now(), conversation_id),
            )


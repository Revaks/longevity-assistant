"""Хранилище заметок, отметок выполнения, настроек и кэша векторов."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    date TEXT PRIMARY KEY,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS completions (
    date    TEXT NOT NULL,
    item_id TEXT NOT NULL,
    done_at TEXT NOT NULL,
    PRIMARY KEY (date, item_id)
);
CREATE TABLE IF NOT EXISTS profile (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS embeddings (
    tip_id       TEXT NOT NULL,
    model        TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    vector       TEXT NOT NULL,
    PRIMARY KEY (tip_id, model)
);
"""


class Storage:
    def __init__(self, db_path: Path):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(SCHEMA)
            self._conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )

    def close(self) -> None:
        self._conn.close()

    # -- заметки -------------------------------------------------------
    def get_note(self, date: str) -> str:
        row = self._conn.execute("SELECT text FROM notes WHERE date = ?", (date,)).fetchone()
        return row["text"] if row else ""

    def set_note(self, date: str, text: str) -> None:
        text = text.strip()
        with self._conn:
            if text:
                self._conn.execute(
                    "INSERT INTO notes (date, text) VALUES (?, ?) "
                    "ON CONFLICT(date) DO UPDATE SET text = excluded.text",
                    (date, text),
                )
            else:
                self._conn.execute("DELETE FROM notes WHERE date = ?", (date,))

    def notes_in_range(self, start: str, end: str) -> dict[str, str]:
        rows = self._conn.execute(
            "SELECT date, text FROM notes WHERE date BETWEEN ? AND ?", (start, end)
        ).fetchall()
        return {row["date"]: row["text"] for row in rows}

    # -- отметки выполнения --------------------------------------------
    def toggle_completion(self, date: str, item_id: str) -> bool:
        with self._conn:
            existing = self._conn.execute(
                "SELECT 1 FROM completions WHERE date = ? AND item_id = ?", (date, item_id)
            ).fetchone()
            if existing:
                self._conn.execute(
                    "DELETE FROM completions WHERE date = ? AND item_id = ?", (date, item_id)
                )
                return False
            self._conn.execute(
                "INSERT INTO completions (date, item_id, done_at) VALUES (?, ?, ?)",
                (date, item_id, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            return True

    def completions_on(self, date: str) -> set[str]:
        rows = self._conn.execute(
            "SELECT item_id FROM completions WHERE date = ?", (date,)
        ).fetchall()
        return {row["item_id"] for row in rows}

    def completion_counts(self, start: str, end: str) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT item_id, COUNT(*) AS n FROM completions "
            "WHERE date BETWEEN ? AND ? GROUP BY item_id",
            (start, end),
        ).fetchall()
        return {row["item_id"]: row["n"] for row in rows}

    # -- настройки и профиль -------------------------------------------
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute("SELECT value FROM profile WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO profile (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    # -- кэш векторов ---------------------------------------------------
    def get_vectors(self, model: str, content_hash: str) -> dict[str, list[float]]:
        rows = self._conn.execute(
            "SELECT tip_id, vector FROM embeddings WHERE model = ? AND content_hash = ?",
            (model, content_hash),
        ).fetchall()
        return {row["tip_id"]: json.loads(row["vector"]) for row in rows}

    def put_vectors(self, model: str, content_hash: str,
                    vectors: dict[str, list[float]]) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM embeddings WHERE model = ?", (model,))
            self._conn.executemany(
                "INSERT INTO embeddings (tip_id, model, content_hash, vector) "
                "VALUES (?, ?, ?, ?)",
                [
                    (tip_id, model, content_hash, json.dumps(vector))
                    for tip_id, vector in vectors.items()
                ],
            )

    # -- миграция -------------------------------------------------------
    def migrate_notes_json(self, candidates: list[Path]) -> int:
        moved = 0
        for path in candidates:
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            with self._conn:
                for date, text in data.items():
                    if not isinstance(text, str) or not text.strip():
                        continue
                    self._conn.execute(
                        "INSERT INTO notes (date, text) VALUES (?, ?) "
                        "ON CONFLICT(date) DO NOTHING",
                        (date, text.strip()),
                    )
                    moved += 1
            path.rename(path.with_suffix(path.suffix + ".migrated"))
        return moved

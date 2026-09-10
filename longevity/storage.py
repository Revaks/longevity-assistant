"""Хранилище заметок, отметок выполнения, настроек и кэша векторов."""

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "2"

#: Префикс для ключей настроек приложения.
APP_PREFIX = "app."

#: Префикс для ключей профиля пользователя.
USER_PREFIX = "user."

#: Допустимые префиксы ключей.
_PREFIXES = (APP_PREFIX, USER_PREFIX)

#: Ключ meta, в который записывается путь к резервной копии notes.json.
#: Нужен человеку, откатившемуся на старую версию: README новой версии
#: откат уберёт, а база останется на месте.
NOTES_BACKUP_KEY = "notes_json_backup"

#: Начало пометки, которой отделяется перенесённый текст от текста в базе.
MERGE_MARK = "--- перенесено из notes.json"

#: Сколько запасных имён вида notes.json.migrated.2 перебирать, прежде чем
#: сдаться. Столько откатов подряд не бывает, а бесконечный цикл — бывает.
_MAX_BACKUP_ATTEMPTS = 1000

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
-- Дневник: несколько заметок на день. Таблица notes выше остаётся
-- только как legacy-источник для переноса (см. sync_notes_to_diary).
CREATE TABLE IF NOT EXISTS diary (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date    TEXT NOT NULL,
    created TEXT NOT NULL,
    text    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_diary_date ON diary(date);
CREATE TABLE IF NOT EXISTS measurements (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date    TEXT NOT NULL,
    kind    TEXT NOT NULL,
    value   REAL NOT NULL,
    note    TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_measurements_kind ON measurements(kind, date);
"""


class StorageError(Exception):
    """С этой базой работать нельзя — например, её создала более новая версия."""


class UnknownKeyPrefix(ValueError):
    """Ключ настройки не относится ни к приложению, ни к профилю."""


class Storage:
    def __init__(self, db_path: Path):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        #: Сообщения о том, что при миграции пошло не так, но не настолько,
        #: чтобы не запускаться. Вызывающий код показывает их пользователю.
        self.migration_warnings: list[str] = []
        try:
            with self._conn:
                self._conn.executescript(SCHEMA)
                self._conn.execute(
                    "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                    (SCHEMA_VERSION,),
                )
            self._migrate_schema()
            self._check_schema_version(db_path)
        except BaseException:
            self._conn.close()
            raise

    def _migrate_schema(self) -> None:
        """Поднять номер схемы у баз старых версий без потери данных.

        Таблицы добавляются через ``CREATE TABLE IF NOT EXISTS`` (см. SCHEMA),
        а здесь только обновляется номер. Неизвестный номер не трогаем — его
        отклонит _check_schema_version.
        """
        found = self.get_meta("schema_version")
        try:
            if int(found) < int(SCHEMA_VERSION):
                self.set_meta("schema_version", SCHEMA_VERSION)
        except (TypeError, ValueError):
            pass

    def _check_schema_version(self, db_path: Path) -> None:
        """Отказ работать с базой из будущего: недостающих колонок не выдумать."""
        found = self.get_meta("schema_version")
        try:
            found_version = int(found)
        except (TypeError, ValueError):
            raise StorageError(
                f"База данных {db_path} помечена неизвестной версией схемы "
                f"({found!r}). Возможно, файл повреждён."
            ) from None
        if found_version > int(SCHEMA_VERSION):
            raise StorageError(
                f"База данных {db_path} создана более новой версией приложения "
                f"(схема {found_version}, эта версия знает {SCHEMA_VERSION}). "
                "Обновите «Ассистент долголетия» — иначе часть ваших данных "
                "будет потеряна."
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

    # -- дневник (несколько заметок на день) ----------------------------
    def diary_entries_on(self, date: str) -> list[dict]:
        """Все заметки дня: [(id, date, created, text)] по времени создания."""
        rows = self._conn.execute(
            "SELECT id, date, created, text FROM diary WHERE date = ? "
            "ORDER BY created, id", (date,)).fetchall()
        return [dict(row) for row in rows]

    def diary_entries_in_range(self, start: str, end: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, date, created, text FROM diary "
            "WHERE date BETWEEN ? AND ? ORDER BY date, created, id",
            (start, end)).fetchall()
        return [dict(row) for row in rows]

    def has_diary_notes(self, date: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM diary WHERE date = ? LIMIT 1", (date,)).fetchone()
        return row is not None

    def add_diary(self, date: str, text: str) -> int:
        """Новая заметка на день. Возвращает её id."""
        text = text.strip()
        if not text:
            return 0
        created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO diary (date, created, text) VALUES (?, ?, ?)",
                (date, created, text))
        return cursor.lastrowid or 0

    def update_diary(self, entry_id: int, text: str) -> bool:
        text = text.strip()
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE diary SET text = ? WHERE id = ?", (text, entry_id))
            return bool(cursor.rowcount)

    def delete_diary(self, entry_id: int) -> bool:
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM diary WHERE id = ?", (entry_id,))
            return bool(cursor.rowcount)

    def sync_notes_to_diary(self) -> int:
        """Перенести старые одиночные заметки (notes) в дневник.

        Одна запись notes -> одна запись diary (дата/время переноса).
        Старая строка удаляется — её копия уже в дневнике; повторный запуск
        идемпотентен, дубликаты не создаются.
        """
        rows = self._conn.execute(
            "SELECT date, text FROM notes ORDER BY date").fetchall()
        moved = 0
        with self._conn:
            for row in rows:
                date, text = row["date"], (row["text"] or "").strip()
                if not text:
                    continue
                dup = self._conn.execute(
                    "SELECT 1 FROM diary WHERE date = ? AND text = ? LIMIT 1",
                    (date, text)).fetchone()
                if dup:
                    self._conn.execute(
                        "DELETE FROM notes WHERE date = ?", (date,))
                    continue
                created = datetime.now(timezone.utc).isoformat(timespec="seconds")
                self._conn.execute(
                    "INSERT INTO diary (date, created, text) VALUES (?, ?, ?)",
                    (date, created, text))
                self._conn.execute(
                    "DELETE FROM notes WHERE date = ?", (date,))
                moved += 1
        return moved

    # -- отметки выполнения --------------------------------------------
    def toggle_completion(self, date: str, item_id: str) -> bool:
        # Решение принимается одним изменяющим запросом (DELETE), а не парой
        # «SELECT — потом INSERT/DELETE»: SELECT не открывает транзакцию, и в
        # окне между чтением и записью два вызова могли бы оба решить, что
        # записи нет, и оба попытаться её вставить. DELETE — DML-запрос, он
        # сразу стартует транзакцию, поэтому check-then-act исчезает.
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM completions WHERE date = ? AND item_id = ?", (date, item_id)
            )
            if cursor.rowcount:
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

    # -- биодневник (измерения) -----------------------------------------
    def add_measurement(self, kind: str, value: float, note: str = "",
                        day: str | None = None) -> int:
        """Добавить измерение; дата по умолчанию — сегодня. Возвращает id."""
        if day is None:
            day = date.today().isoformat()
        created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO measurements (date, kind, value, note, created) "
                "VALUES (?, ?, ?, ?, ?)",
                (day, kind, value, note.strip(), created),
            )
        return cursor.lastrowid or 0

    def measurements_of_kind(self, kind: str, limit: int = 30) -> list[dict]:
        """Последние измерения вида, сначала свежие."""
        rows = self._conn.execute(
            "SELECT id, date, kind, value, note, created FROM measurements "
            "WHERE kind = ? ORDER BY date DESC, id DESC LIMIT ?",
            (kind, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def all_measurements(self, limit: int = 500) -> list[dict]:
        """Все измерения (для выгрузки/удаления), свежие первыми."""
        rows = self._conn.execute(
            "SELECT id, date, kind, value, note, created FROM measurements "
            "ORDER BY date DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_measurement(self, measurement_id: int) -> bool:
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM measurements WHERE id = ?", (measurement_id,))
            return bool(cursor.rowcount)

    # -- настройки и профиль -------------------------------------------
    def get_value(self, key: str, default=None):
        """Значение настройки любого JSON-типа. Испорченное значение — как отсутствующее."""
        _check_prefix(key)
        row = self._conn.execute(
            "SELECT value FROM profile WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return default

    def set_value(self, key: str, value) -> None:
        """Сохранить значение любого JSON-совместимого типа."""
        _check_prefix(key)
        with self._conn:
            self._conn.execute(
                "INSERT INTO profile (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def all_values(self, prefix: str) -> dict:
        """Все значения с этим префиксом; в ключах результата префикса нет."""
        if prefix not in _PREFIXES:
            raise UnknownKeyPrefix(f"неизвестный префикс: {prefix!r}")
        rows = self._conn.execute(
            "SELECT key, value FROM profile WHERE key LIKE ?", (prefix + "%",)
        ).fetchall()
        result = {}
        for row in rows:
            try:
                result[row["key"][len(prefix):]] = json.loads(row["value"])
            except json.JSONDecodeError:
                continue
        return result

    # -- профиль календаря (типизированные доступы) ---------------------
    def load_profile(self):
        """Профиль календаря: возраст, пол, активность, разгрузка, скрытые пункты."""
        from .plan import Profile, parse_hidden

        age = self.get_value("user.age")
        if isinstance(age, bool) or not isinstance(age, int):
            age = None
        sex = self.get_value("user.sex")
        if not isinstance(sex, str):
            sex = None
        activity = self.get_value("user.activity")
        if isinstance(activity, bool) or not isinstance(activity, int):
            activity = 1
        return Profile(
            age=age,
            sex=sex,
            activity=activity,
            deload=bool(self.get_value("user.deload")),
            hidden=parse_hidden(self.get_value("user.hidden")),
        )

    def save_profile(self, profile) -> None:
        """Сохранить профиль (скрытые пункты пишутся отдельно через save_hidden)."""
        self.set_value("user.age", profile.age)
        self.set_value("user.sex", profile.sex)
        self.set_value("user.activity", profile.activity)
        self.set_value("user.deload", profile.deload)

    def load_custom_items(self, categories: list[str]):
        from .plan import parse_custom_items

        return parse_custom_items(self.get_value("user.custom"), categories)

    def save_custom_items(self, items) -> None:
        from .plan import serialize_custom_items

        self.set_value("user.custom", serialize_custom_items(items))

    def save_hidden(self, ids) -> None:
        from .plan import serialize_hidden

        self.set_value("user.hidden", serialize_hidden(ids))

    def screening_last_done(self, screening_id: str):
        """Дата последнего прохождения обследования (None — не проходили)."""
        raw = self.get_value(f"user.screen.{screening_id}")
        if not isinstance(raw, str):
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None

    def mark_screening(self, screening_id: str, day: date) -> None:
        self.set_value(f"user.screen.{screening_id}", day.isoformat())

    def clear_screening(self, screening_id: str) -> None:
        self.set_value(f"user.screen.{screening_id}", None)

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

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
        """Переносит заметки из старых notes.json в базу.

        Возвращает число заметок, действительно записанных в базу (а не число
        попыток). Неудачи переименования исходника не мешают запуску — данные
        к этому моменту уже в базе — и складываются в self.migration_warnings,
        чтобы интерфейс мог о них сказать.
        """
        self.migration_warnings = []
        moved = 0
        today = datetime.now().date().isoformat()
        for path in candidates:
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                # ValueError покрывает и json.JSONDecodeError (битый синтаксис),
                # и UnicodeDecodeError (оборванная многобайтовая UTF-8
                # последовательность) — оба подкласса ValueError, а не OSError.
                # Именно усечённый файл — типичный след неатомарной записи
                # старой версией, ради которого миграция существует.
                continue
            if not isinstance(data, dict):
                continue
            moved += self._merge_notes(data, today)
            self._backup_migrated_file(path)
        return moved

    def _merge_notes(self, data: dict, today: str) -> int:
        """Сливает заметки из файла с тем, что уже лежит в базе."""
        written = 0
        with self._conn:
            for date, text in data.items():
                if not isinstance(text, str):
                    # Старый файл мог быть отредактирован руками: {"2026-09-01": 123}.
                    continue
                text = text.strip()
                if not text:
                    continue
                row = self._conn.execute(
                    "SELECT text FROM notes WHERE date = ?", (date,)
                ).fetchone()
                merged = _merge_note(row["text"] if row else "", text, today)
                if merged is None:
                    continue
                self._conn.execute(
                    "INSERT INTO notes (date, text) VALUES (?, ?) "
                    "ON CONFLICT(date) DO UPDATE SET text = excluded.text",
                    (date, merged),
                )
                written += 1
        return written

    def _backup_migrated_file(self, path: Path) -> None:
        """Убирает перенесённый файл, не затирая прошлые резервные копии."""
        backup = _free_backup_path(path)
        if backup is None:
            self.migration_warnings.append(
                f"Не удалось подобрать имя для резервной копии {path}: "
                "слишком много прежних копий рядом. Файл оставлен как есть."
            )
            return
        try:
            # replace, а не rename: rename на Windows падает, если цель занята,
            # и это ронял старт при повторном обновлении. Имя при этом уже
            # свободно, так что перезаписи чужого бэкапа не будет.
            path.replace(backup)
        except OSError as exc:
            self.migration_warnings.append(
                f"Заметки из {path} перенесены в базу, но сам файл переименовать "
                f"не удалось ({exc}). Уберите или переименуйте его вручную, иначе "
                "при следующем запуске перенос повторится."
            )
            return
        self.set_meta(NOTES_BACKUP_KEY, str(backup))


def _merge_note(existing: str, incoming: str, today: str) -> str | None:
    """Объединённый текст заметки или None, если менять в базе нечего.

    Политика «база всегда старше файла» неверна для отката: там свежее как раз
    файл. Поэтому при расхождении не выбрасываем ни одну из версий, а
    показываем обе — решает пользователь.
    """
    if not existing:
        return incoming
    if incoming == existing:
        return None
    if incoming in existing:
        # Этот текст уже переносили: второй перенос не должен ничего дублировать.
        return None
    return f"{existing}\n\n{MERGE_MARK} {today} ---\n{incoming}"


def _free_backup_path(path: Path) -> Path | None:
    """Свободное имя для резервной копии: notes.json.migrated, потом .2, .3…"""
    backup = path.with_name(path.name + ".migrated")
    if not backup.exists():
        return backup
    for n in range(2, _MAX_BACKUP_ATTEMPTS + 1):
        numbered = path.with_name(f"{path.name}.migrated.{n}")
        if not numbered.exists():
            return numbered
    return None


def _check_prefix(key: str) -> None:
    """Проверить, что ключ начинается с известного префикса."""
    if not key.startswith(_PREFIXES):
        raise UnknownKeyPrefix(
            f"ключ {key!r} должен начинаться с {APP_PREFIX!r} или {USER_PREFIX!r}")

import datetime as dt
import json
import sqlite3
from pathlib import Path

import pytest

from longevity.storage import MERGE_MARK, NOTES_BACKUP_KEY, Storage, StorageError


@pytest.fixture
def store(tmp_path):
    s = Storage(tmp_path / "data.db")
    yield s
    s.close()


def test_note_roundtrip(store):
    store.set_note("2026-09-06", "выпил чай")

    assert store.get_note("2026-09-06") == "выпил чай"


def test_missing_note_is_empty_string(store):
    assert store.get_note("2026-01-01") == ""


def test_empty_text_deletes_note(store):
    store.set_note("2026-09-06", "текст")
    store.set_note("2026-09-06", "   ")

    assert store.get_note("2026-09-06") == ""


def test_note_is_overwritten_not_duplicated(store):
    store.set_note("2026-09-06", "первая")
    store.set_note("2026-09-06", "вторая")

    assert store.get_note("2026-09-06") == "вторая"
    assert store.notes_in_range("2026-09-01", "2026-09-30") == {"2026-09-06": "вторая"}


def test_notes_in_range_excludes_outside_dates(store):
    store.set_note("2026-08-31", "август")
    store.set_note("2026-09-06", "сентябрь")

    assert store.notes_in_range("2026-09-01", "2026-09-30") == {"2026-09-06": "сентябрь"}


def test_toggle_completion_flips_state(store):
    assert store.toggle_completion("2026-09-06", "mind_greens") is True
    assert store.completions_on("2026-09-06") == {"mind_greens"}

    assert store.toggle_completion("2026-09-06", "mind_greens") is False
    assert store.completions_on("2026-09-06") == set()


def test_toggle_completion_round_trip_leaves_no_duplicates(store):
    first = store.toggle_completion("2026-09-06", "mind_greens")
    second = store.toggle_completion("2026-09-06", "mind_greens")

    assert first is True
    assert second is False
    assert store.completions_on("2026-09-06") == set()
    assert store.completion_counts("2026-09-01", "2026-09-30") == {}


def test_completion_counts_over_a_week(store):
    for day in ("2026-08-31", "2026-09-01", "2026-09-02"):
        store.toggle_completion(day, "mind_greens")
    store.toggle_completion("2026-09-01", "mind_berries")

    counts = store.completion_counts("2026-08-31", "2026-09-06")

    assert counts == {"mind_greens": 3, "mind_berries": 1}


def test_settings_roundtrip_with_default(store):
    from longevity.storage import APP_PREFIX
    assert store.get_value(APP_PREFIX + "model") is None
    assert store.get_value(APP_PREFIX + "model", "qwen3.5:4b") == "qwen3.5:4b"

    store.set_value(APP_PREFIX + "model", "qwen3.5:9b")
    store.set_value(APP_PREFIX + "model", "qwen3.5:4b")

    assert store.get_value(APP_PREFIX + "model") == "qwen3.5:4b"


def test_vectors_roundtrip(store):
    store.put_vectors("emb:1", "hash-a", {"zh06": [0.1, 0.2], "pit05": [0.3, 0.4]})

    assert store.get_vectors("emb:1", "hash-a") == {"zh06": [0.1, 0.2], "pit05": [0.3, 0.4]}


def test_vectors_invalidated_by_content_hash(store):
    store.put_vectors("emb:1", "hash-a", {"zh06": [0.1]})

    assert store.get_vectors("emb:1", "hash-b") == {}


def test_vectors_invalidated_by_model(store):
    store.put_vectors("emb:1", "hash-a", {"zh06": [0.1]})

    assert store.get_vectors("emb:2", "hash-a") == {}


def test_put_vectors_replaces_previous_set(store):
    store.put_vectors("emb:1", "hash-a", {"zh06": [0.1]})
    store.put_vectors("emb:1", "hash-b", {"pit05": [0.9]})

    assert store.get_vectors("emb:1", "hash-b") == {"pit05": [0.9]}
    assert store.get_vectors("emb:1", "hash-a") == {}


def test_migrates_notes_json_and_renames_it(tmp_path):
    legacy = tmp_path / "notes.json"
    legacy.write_text(json.dumps({"2026-09-06": "старая заметка"}), encoding="utf-8")
    store = Storage(tmp_path / "data.db")

    moved = store.migrate_notes_json([legacy])

    assert moved == 1
    assert store.get_note("2026-09-06") == "старая заметка"
    assert not legacy.exists()
    assert (tmp_path / "notes.json.migrated").exists(), "исходник сохраняется для отката"
    store.close()


def test_migrated_file_is_renamed_and_not_reread(tmp_path):
    legacy = tmp_path / "notes.json"
    legacy.write_text(json.dumps({"2026-09-06": "заметка"}), encoding="utf-8")
    store = Storage(tmp_path / "data.db")

    assert store.migrate_notes_json([legacy]) == 1
    assert store.migrate_notes_json([legacy]) == 0

    assert store.get_note("2026-09-06") == "заметка"
    store.close()


def test_migration_ignores_broken_file(tmp_path):
    legacy = tmp_path / "notes.json"
    legacy.write_text("{это не json", encoding="utf-8")
    store = Storage(tmp_path / "data.db")

    assert store.migrate_notes_json([legacy]) == 0
    assert legacy.exists(), "битый файл не трогаем"
    store.close()


def test_migration_ignores_file_with_broken_utf8(tmp_path):
    legacy = tmp_path / "notes.json"
    legacy.write_bytes(b'{"2026-09-06": "\xd0\xb7\xd0')
    store = Storage(tmp_path / "data.db")

    assert store.migrate_notes_json([legacy]) == 0
    assert legacy.exists(), "файл с оборванной UTF-8 последовательностью не трогаем"
    store.close()


def test_schema_version_recorded(tmp_path):
    store = Storage(tmp_path / "data.db")

    assert store.get_meta("schema_version") == "1"
    store.close()


def test_reopening_existing_database_keeps_data(tmp_path):
    first = Storage(tmp_path / "data.db")
    first.set_note("2026-09-06", "сохранилось")
    first.close()

    second = Storage(tmp_path / "data.db")
    assert second.get_note("2026-09-06") == "сохранилось"
    second.close()


def test_write_error_surfaces_as_exception(tmp_path):
    store = Storage(tmp_path / "data.db")
    store.close()

    with pytest.raises(sqlite3.ProgrammingError):
        store.set_note("2026-09-06", "после закрытия")


# -- резервная копия исходного файла -----------------------------------
def test_existing_backup_is_not_overwritten(tmp_path):
    """Обновился, откатился, обновился снова — первый бэкап обязан уцелеть."""
    old_backup = tmp_path / "notes.json.migrated"
    old_backup.write_text(json.dumps({"2026-09-01": "первое обновление"}),
                          encoding="utf-8")
    legacy = tmp_path / "notes.json"
    legacy.write_text(json.dumps({"2026-09-02": "после отката"}), encoding="utf-8")
    store = Storage(tmp_path / "data.db")

    assert store.migrate_notes_json([legacy]) == 1

    assert json.loads(old_backup.read_text(encoding="utf-8")) == {
        "2026-09-01": "первое обновление"
    }, "прежняя резервная копия затёрта"
    second = tmp_path / "notes.json.migrated.2"
    assert json.loads(second.read_text(encoding="utf-8")) == {"2026-09-02": "после отката"}
    assert not legacy.exists()
    store.close()


def test_backup_path_is_recorded_in_meta(tmp_path):
    legacy = tmp_path / "notes.json"
    legacy.write_text(json.dumps({"2026-09-06": "заметка"}), encoding="utf-8")
    store = Storage(tmp_path / "data.db")

    store.migrate_notes_json([legacy])

    assert store.get_meta(NOTES_BACKUP_KEY) == str(tmp_path / "notes.json.migrated")
    store.close()


def test_rename_failure_does_not_break_startup(tmp_path, monkeypatch):
    """Заметки уже в базе: невозможность переименовать файл — не повод падать."""
    legacy = tmp_path / "notes.json"
    legacy.write_text(json.dumps({"2026-09-06": "заметка"}), encoding="utf-8")
    store = Storage(tmp_path / "data.db")

    def refuse(self, target):
        raise PermissionError(13, "каталог доступен только на чтение")

    monkeypatch.setattr(Path, "replace", refuse)

    assert store.migrate_notes_json([legacy]) == 1
    assert store.get_note("2026-09-06") == "заметка"
    assert legacy.exists(), "переименовать не вышло — файл остаётся на месте"
    assert store.migration_warnings, "неудача обязана быть видна вызывающему коду"
    assert "notes.json" in store.migration_warnings[0]
    store.close()


def test_warnings_are_reset_between_runs(tmp_path, monkeypatch):
    legacy = tmp_path / "notes.json"
    legacy.write_text(json.dumps({"2026-09-06": "заметка"}), encoding="utf-8")
    store = Storage(tmp_path / "data.db")

    def refuse(self, target):
        raise PermissionError(13, "нельзя")

    monkeypatch.setattr(Path, "replace", refuse)
    store.migrate_notes_json([legacy])
    monkeypatch.undo()

    assert store.migrate_notes_json([legacy]) == 0
    assert store.migration_warnings == []
    store.close()


# -- политика слияния при переносе -------------------------------------
def test_identical_text_is_not_duplicated(tmp_path):
    legacy = tmp_path / "notes.json"
    legacy.write_text(json.dumps({"2026-09-06": "одинаковый текст"}), encoding="utf-8")
    store = Storage(tmp_path / "data.db")
    store.set_note("2026-09-06", "одинаковый текст")

    assert store.migrate_notes_json([legacy]) == 0, "писать было нечего"
    assert store.get_note("2026-09-06") == "одинаковый текст"
    assert MERGE_MARK not in store.get_note("2026-09-06")
    store.close()


def test_conflicting_text_keeps_both_versions(tmp_path):
    """Откат: в базе версия из обновления, в файле — то, что правили в откате."""
    legacy = tmp_path / "notes.json"
    legacy.write_text(json.dumps({"2026-09-06": "правка из отката"}), encoding="utf-8")
    store = Storage(tmp_path / "data.db")
    store.set_note("2026-09-06", "версия из базы")

    assert store.migrate_notes_json([legacy]) == 1

    note = store.get_note("2026-09-06")
    assert "версия из базы" in note
    assert "правка из отката" in note
    assert MERGE_MARK in note, "перенесённый текст должен быть помечен"
    assert dt.date.today().isoformat() in note, "пометка должна нести дату переноса"
    store.close()


def test_repeated_migration_of_the_same_text_changes_nothing(tmp_path):
    legacy = tmp_path / "notes.json"
    payload = json.dumps({"2026-09-06": "правка из отката"})
    legacy.write_text(payload, encoding="utf-8")
    store = Storage(tmp_path / "data.db")
    store.set_note("2026-09-06", "версия из базы")
    store.migrate_notes_json([legacy])
    after_first = store.get_note("2026-09-06")

    legacy.write_text(payload, encoding="utf-8")

    assert store.migrate_notes_json([legacy]) == 0
    assert store.get_note("2026-09-06") == after_first, "второй перенос дописал текст"
    assert after_first.count(MERGE_MARK) == 1
    store.close()


def test_new_date_from_file_is_inserted_as_is(tmp_path):
    legacy = tmp_path / "notes.json"
    legacy.write_text(json.dumps({"2026-09-07": "новая дата"}), encoding="utf-8")
    store = Storage(tmp_path / "data.db")
    store.set_note("2026-09-06", "другая дата")

    assert store.migrate_notes_json([legacy]) == 1

    assert store.get_note("2026-09-07") == "новая дата"
    assert MERGE_MARK not in store.get_note("2026-09-07")
    assert store.get_note("2026-09-06") == "другая дата"
    store.close()


def test_non_string_values_are_skipped(tmp_path):
    legacy = tmp_path / "notes.json"
    legacy.write_text(json.dumps({"2026-09-01": 123, "2026-09-02": None,
                                  "2026-09-03": ["список"], "2026-09-04": "текст"}),
                      encoding="utf-8")
    store = Storage(tmp_path / "data.db")

    assert store.migrate_notes_json([legacy]) == 1

    assert store.get_note("2026-09-01") == ""
    assert store.get_note("2026-09-02") == ""
    assert store.get_note("2026-09-03") == ""
    assert store.get_note("2026-09-04") == "текст"
    store.close()


def test_counter_counts_written_notes_not_attempts(tmp_path):
    legacy = tmp_path / "notes.json"
    legacy.write_text(json.dumps({"2026-09-01": "совпадает",
                                  "2026-09-02": "   ",
                                  "2026-09-03": 5,
                                  "2026-09-04": "новая"}), encoding="utf-8")
    store = Storage(tmp_path / "data.db")
    store.set_note("2026-09-01", "совпадает")

    assert store.migrate_notes_json([legacy]) == 1
    store.close()


# -- версия схемы -------------------------------------------------------
def test_refuses_database_from_a_newer_version(tmp_path):
    db = tmp_path / "data.db"
    first = Storage(db)
    first.set_meta("schema_version", "2")
    first.close()

    with pytest.raises(StorageError, match="более новой версией"):
        Storage(db)


def test_refuses_database_with_unreadable_schema_version(tmp_path):
    db = tmp_path / "data.db"
    first = Storage(db)
    first.set_meta("schema_version", "неизвестно")
    first.close()

    with pytest.raises(StorageError, match="неизвестной версией"):
        Storage(db)


def test_same_schema_version_opens_normally(tmp_path):
    db = tmp_path / "data.db"
    first = Storage(db)
    first.set_note("2026-09-06", "сохранилось")
    first.close()

    second = Storage(db)

    assert second.get_note("2026-09-06") == "сохранилось"
    second.close()


# -- дневник: несколько заметок на день -------------------------------------

def test_diary_adds_multiple_entries_per_date(tmp_path):
    storage = Storage(tmp_path / "data.db")
    try:
        date = "2026-09-08"
        storage.add_diary(date, "утром: бег")
        storage.add_diary(date, "вечером: растяжка")

        texts = [e["text"] for e in storage.diary_entries_on(date)]
        assert texts == ["утром: бег", "вечером: растяжка"]
        assert storage.has_diary_notes(date)
        assert not storage.has_diary_notes("2026-09-09")
    finally:
        storage.close()


def test_diary_update_and_delete(tmp_path):
    storage = Storage(tmp_path / "data.db")
    try:
        date = "2026-09-08"
        eid = storage.add_diary(date, "черновик")

        assert storage.update_diary(eid, "исправлено")
        assert storage.diary_entries_on(date)[0]["text"] == "исправлено"

        assert storage.delete_diary(eid)
        assert storage.diary_entries_on(date) == []
        assert not storage.delete_diary(eid)
    finally:
        storage.close()


def test_sync_notes_to_diary_migrates_single_notes(tmp_path):
    storage = Storage(tmp_path / "data.db")
    try:
        storage.set_note("2026-09-07", "старая заметка")
        moved = storage.sync_notes_to_diary()

        assert moved == 1
        assert storage.diary_entries_on("2026-09-07")[0]["text"] == "старая заметка"
        assert storage.get_note("2026-09-07") == "", "legacy-строка перенесена"
        # идемпотентность
        assert storage.sync_notes_to_diary() == 0
        assert len(storage.diary_entries_on("2026-09-07")) == 1
    finally:
        storage.close()

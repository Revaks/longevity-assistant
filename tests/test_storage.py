import json
import sqlite3

import pytest

from longevity.storage import Storage


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


def test_completion_counts_over_a_week(store):
    for day in ("2026-08-31", "2026-09-01", "2026-09-02"):
        store.toggle_completion(day, "mind_greens")
    store.toggle_completion("2026-09-01", "mind_berries")

    counts = store.completion_counts("2026-08-31", "2026-09-06")

    assert counts == {"mind_greens": 3, "mind_berries": 1}


def test_settings_roundtrip_with_default(store):
    assert store.get_setting("model") is None
    assert store.get_setting("model", "qwen3.5:4b") == "qwen3.5:4b"

    store.set_setting("model", "qwen3.5:9b")
    store.set_setting("model", "qwen3.5:4b")

    assert store.get_setting("model") == "qwen3.5:4b"


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


def test_migration_is_idempotent(tmp_path):
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

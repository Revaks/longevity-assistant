import pytest

from longevity.storage import APP_PREFIX, USER_PREFIX, Storage, UnknownKeyPrefix


@pytest.fixture
def store(tmp_path):
    s = Storage(tmp_path / "data.db")
    yield s
    s.close()


def test_missing_value_returns_default(store):
    assert store.get_value("app.ollama_model") is None
    assert store.get_value("app.ollama_model", "qwen3.5:4b") == "qwen3.5:4b"


def test_preserves_string(store):
    store.set_value("app.ollama_model", "qwen3.5:4b")

    assert store.get_value("app.ollama_model") == "qwen3.5:4b"


def test_preserves_bool_and_none(store):
    store.set_value("user.gym", False)
    store.set_value("user.age", None)

    assert store.get_value("user.gym") is False, "False не должно превратиться в строку"
    assert store.get_value("user.age") is None


def test_preserves_int_and_list(store):
    store.set_value("user.age", 47)
    store.set_value("app.window_size", [1280, 820])

    assert store.get_value("user.age") == 47
    assert store.get_value("app.window_size") == [1280, 820]


def test_cyrillic_survives_roundtrip(store):
    store.set_value("user.diet", "вегетарианец")

    assert store.get_value("user.diet") == "вегетарианец"


def test_value_is_overwritten(store):
    store.set_value("app.active_page", "calendar")
    store.set_value("app.active_page", "knowledge")

    assert store.get_value("app.active_page") == "knowledge"


def test_rejects_unknown_prefix(store):
    with pytest.raises(UnknownKeyPrefix):
        store.set_value("random_key", 1)
    with pytest.raises(UnknownKeyPrefix):
        store.get_value("profile.gym")


def test_all_values_strips_prefix_and_filters(store):
    store.set_value("user.gym", True)
    store.set_value("user.diet", "omnivore")
    store.set_value("app.active_page", "calendar")

    assert store.all_values(USER_PREFIX) == {"gym": True, "diet": "omnivore"}
    assert store.all_values(APP_PREFIX) == {"active_page": "calendar"}


def test_corrupted_value_falls_back_to_default(store):
    store.set_value("app.active_page", "calendar")
    store._conn.execute("UPDATE profile SET value = '{битый' WHERE key = ?",
                        ("app.active_page",))
    store._conn.commit()

    assert store.get_value("app.active_page", "calendar") == "calendar", (
        "испорченная настройка не должна ронять приложение")


def test_old_string_api_is_gone(store):
    assert not hasattr(store, "get_setting")
    assert not hasattr(store, "set_setting")

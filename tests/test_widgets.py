"""ModelBar — общая панель выбора модели Ollama (ui/widgets.py).

Раньше две страницы держали каждая свою копию списка моделей и своего
выпадающего списка. Эти тесты бьют по логике восстановления выбора и по
тому, что панель не падает без хранилища — то, что раньше приходилось бы
дублировать в каждой странице отдельно.
"""

import time

import pytest

from ui.widgets import choose_model


def test_choose_model_prefers_saved_when_present():
    assert choose_model(["a", "b"], "b") == "b"


def test_choose_model_falls_back_to_first_when_saved_missing():
    assert choose_model(["a", "b"], "removed-model") == "a"


def test_choose_model_falls_back_to_first_when_nothing_saved():
    assert choose_model(["a", "b"], None) == "a"


def test_choose_model_empty_available_returns_empty_string():
    assert choose_model([], "a") == ""


@pytest.fixture
def bar(tmp_path):
    tk = pytest.importorskip("tkinter")
    from longevity.storage import Storage
    from ui.theme import Theme
    from ui.widgets import ModelBar

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    theme = Theme(root)
    widget = ModelBar(root, theme, storage)
    yield widget, storage
    storage.close()
    root.destroy()


def test_apply_picks_first_model_when_nothing_saved(bar):
    widget, storage = bar

    widget._apply(["qwen3-coder:30b", "qwen3.5:4b"])

    assert widget.current() == "qwen3-coder:30b"
    assert storage.get_value("app.ollama_model") == "qwen3-coder:30b"


def test_apply_restores_previously_saved_model(bar):
    """Регресс на дефект №1 задачи: по умолчанию не должна браться models[0],
    если пользователь уже выбирал другую модель раньше."""
    widget, storage = bar
    storage.set_value("app.ollama_model", "qwen3.5:9b")

    widget._apply(["qwen3-coder:30b", "qwen3.5:9b"])

    assert widget.current() == "qwen3.5:9b"


def test_apply_falls_back_to_first_when_saved_model_gone(bar):
    widget, storage = bar
    storage.set_value("app.ollama_model", "removed-model")

    widget._apply(["qwen3-coder:30b", "qwen3.5:4b"])

    assert widget.current() == "qwen3-coder:30b"


def test_apply_with_no_models_marks_bar_unavailable(bar):
    widget, storage = bar

    widget._apply([])

    assert widget.current() == ""
    assert str(widget.combo["state"]) == "disabled"


def test_selecting_in_combo_persists_choice(bar):
    widget, storage = bar
    widget._apply(["qwen3-coder:30b", "qwen3.5:4b"])

    widget.model_var.set("qwen3.5:4b")
    widget._on_select()

    assert storage.get_value("app.ollama_model") == "qwen3.5:4b"


def test_works_without_storage():
    """storage=None не должен ронять панель — так уже жили страницы раньше."""
    tk = pytest.importorskip("tkinter")
    from ui.theme import Theme
    from ui.widgets import ModelBar

    root = tk.Tk()
    root.withdraw()
    try:
        widget = ModelBar(root, Theme(root), None)
        widget._apply(["qwen3.5:4b"])
        assert widget.current() == "qwen3.5:4b"
    finally:
        root.destroy()


def test_selection_persists_across_a_new_bar_instance(tmp_path):
    """Смена модели видна следующему экземпляру панели — как при перезапуске приложения."""
    tk = pytest.importorskip("tkinter")
    from longevity.storage import Storage
    from ui.theme import Theme
    from ui.widgets import ModelBar

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        theme = Theme(root)
        first = ModelBar(root, theme, storage)
        first._apply(["qwen3-coder:30b", "qwen3.5:4b"])
        first.model_var.set("qwen3.5:4b")
        first._on_select()

        second = ModelBar(root, theme, storage)
        second._apply(["qwen3-coder:30b", "qwen3.5:4b"])

        assert second.current() == "qwen3.5:4b", \
            "выбор модели должен пережить создание новой панели (перезапуск приложения)"
    finally:
        storage.close()
        root.destroy()


def test_refresh_does_not_block_on_slow_network(monkeypatch, bar):
    """Опрос идёт в фоновом потоке — refresh() обязан вернуться немедленно,
    а не ждать ответ сети, иначе окно снова замирает на время таймаута."""
    widget, storage = bar

    def slow_list_models(timeout=3):
        time.sleep(0.3)
        return []

    monkeypatch.setattr("ui.widgets.list_models", slow_list_models)

    start = time.monotonic()
    widget.refresh()
    elapsed = time.monotonic() - start

    assert elapsed < 0.1, "refresh() заблокировал вызывающий поток"
    assert str(widget.refresh_btn["state"]) == "disabled"

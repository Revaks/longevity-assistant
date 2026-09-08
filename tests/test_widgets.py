"""ModelStore/ModelBar — общий источник истины о моделях Ollama (ui/widgets.py).

ModelStore хранит список моделей, текущий выбор и опрашивает сервис; ModelBar
— тонкое отображение поверх store, без собственной копии состояния. Эти тесты
бьют по трём вещам, которые раньше были дефектами задачи: восстановление
выбора, отсутствие падения фонового потока при закрытии окна, и то, что обе
панели показывают одно и то же состояние без ручного обновления.
"""

import threading
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
def env(tk, tmp_path):
    """Скрытый корень + хранилище + пустой ModelStore на них (без опроса)."""
    from longevity.storage import Storage
    from ui.theme import Theme
    from ui.widgets import ModelStore

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    theme = Theme(root)
    store = ModelStore(root, storage)
    yield root, theme, storage, store
    storage.close()
    root.destroy()


# -- ModelStore: восстановление и откат выбора ------------------------------

def test_apply_picks_first_model_when_nothing_saved(env):
    _, _, storage, store = env

    store._apply(["qwen3-coder:30b", "qwen3.5:4b"])

    assert store.current == "qwen3-coder:30b"
    assert storage.get_value("app.ollama_model") == "qwen3-coder:30b"


def test_apply_restores_previously_saved_model(env):
    """Регресс на дефект №1 задачи: по умолчанию не должна браться models[0],
    если пользователь уже выбирал другую модель раньше."""
    _, _, storage, store = env
    storage.set_value("app.ollama_model", "qwen3.5:9b")

    store._apply(["qwen3-coder:30b", "qwen3.5:9b"])

    assert store.current == "qwen3.5:9b"


def test_apply_falls_back_to_first_when_saved_model_gone(env):
    _, _, storage, store = env
    storage.set_value("app.ollama_model", "removed-model")

    store._apply(["qwen3-coder:30b", "qwen3.5:4b"])

    assert store.current == "qwen3-coder:30b"


def test_apply_with_no_models_marks_store_unavailable(env):
    _, _, _, store = env

    store._apply([])

    assert store.current == ""
    assert store.models == []


def test_works_without_storage(tk):
    """storage=None не должен ронять store — так уже жили страницы раньше."""
    from ui.widgets import ModelStore

    root = tk.Tk()
    root.withdraw()
    try:
        store = ModelStore(root, None)
        store._apply(["qwen3.5:4b"])
        assert store.current == "qwen3.5:4b"
    finally:
        root.destroy()


def test_selection_persists_across_a_new_store_instance(tk, tmp_path):
    """Смена модели видна следующему store — как при перезапуске приложения."""
    from longevity.storage import Storage
    from ui.widgets import ModelStore

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        first = ModelStore(root, storage)
        first._apply(["qwen3-coder:30b", "qwen3.5:4b"])
        first.select("qwen3.5:4b")

        second = ModelStore(root, storage)
        second._apply(["qwen3-coder:30b", "qwen3.5:4b"])

        assert second.current == "qwen3.5:4b", \
            "выбор модели должен пережить создание нового store (перезапуск приложения)"
    finally:
        storage.close()
        root.destroy()


def test_refresh_does_not_block_on_slow_network(monkeypatch, env):
    """Опрос идёт в фоновом потоке — refresh() обязан вернуться немедленно,
    а не ждать ответ сети, иначе окно снова замирает на время таймаута."""
    _, _, _, store = env

    def slow_list_models(timeout=3):
        time.sleep(0.3)
        return []

    monkeypatch.setattr("ui.widgets.list_models", slow_list_models)

    start = time.monotonic()
    store.refresh()
    elapsed = time.monotonic() - start

    assert elapsed < 0.1, "refresh() заблокировал вызывающий поток"
    assert store.busy is True


# -- ModelBar: чистое отображение поверх store ------------------------------

def test_bar_reflects_store_state_on_construction(env):
    from ui.widgets import ModelBar

    root, theme, _, store = env
    store._apply(["qwen3-coder:30b", "qwen3.5:4b"])

    bar = ModelBar(root, theme, store)

    assert bar.current() == "qwen3-coder:30b"
    assert str(bar.combo["state"]) == "readonly"


def test_bar_selecting_in_combo_updates_store(env):
    from ui.widgets import ModelBar

    root, theme, storage, store = env
    store._apply(["qwen3-coder:30b", "qwen3.5:4b"])
    bar = ModelBar(root, theme, store)

    bar.model_var.set("qwen3.5:4b")
    bar._on_select()

    assert store.current == "qwen3.5:4b"
    assert storage.get_value("app.ollama_model") == "qwen3.5:4b"


def test_bar_with_no_models_is_disabled(env):
    from ui.widgets import ModelBar

    root, theme, _, store = env
    store._apply([])

    bar = ModelBar(root, theme, store)

    assert bar.current() == ""
    assert str(bar.combo["state"]) == "disabled"


# -- Требование ревью 1: смена модели видна на другой панели без обновления --

def test_selecting_model_on_one_bar_updates_the_other_immediately(env):
    """Обе страницы держат свою ModelBar, но обе смотрят в один store —
    именно это заменяет прежние две независимые копии списка моделей."""
    from ui.widgets import ModelBar

    root, theme, storage, store = env
    store._apply(["qwen3-coder:30b", "qwen3.5:4b"])

    bar_assistant = ModelBar(root, theme, store)
    bar_nutrition = ModelBar(root, theme, store)
    assert bar_assistant.current() == bar_nutrition.current() == "qwen3-coder:30b"

    # Пользователь меняет модель на вкладке "Ассистент"...
    bar_assistant.model_var.set("qwen3.5:4b")
    bar_assistant._on_select()

    # ...и вкладка "Питание" видит новую модель без ручного "Обновить".
    assert bar_nutrition.current() == "qwen3.5:4b"
    assert bar_nutrition.model_var.get() == "qwen3.5:4b"
    assert storage.get_value("app.ollama_model") == "qwen3.5:4b"


# -- Требование ревью 2: опрос сервиса при старте — один раз, а не по разу на панель --

def test_creating_two_bars_polls_the_service_only_once(monkeypatch, env):
    """Раньше ModelBar сама опрашивала сервис в своём конструкторе — при
    двух страницах это был двойной опрос. Теперь опрос запускает только тот,
    кто явно вызывает store.refresh() (в реальном приложении — один раз в
    LongevityApp.__init__); создание сколь угодно многих ModelBar поверх
    одного store не должно порождать новых сетевых обращений."""
    from ui.widgets import ModelBar

    root, theme, _, store = env
    calls = []

    def counting_list_models(timeout=3):
        calls.append(1)
        return []

    monkeypatch.setattr("ui.widgets.list_models", counting_list_models)

    def settle():
        """Дать шанс любому потоку, случайно запущенному конструктором,
        реально выполниться — не полагаясь на удачу планировщика GIL."""
        if store._thread is not None:
            store._thread.join(timeout=2)
        root.update()

    ModelBar(root, theme, store)
    settle()
    assert calls == [], "конструктор ModelBar не должен сам опрашивать сервис"

    ModelBar(root, theme, store)
    settle()
    assert calls == [], "конструктор второй ModelBar тоже не должен опрашивать сервис"

    store.refresh()
    settle()

    assert len(calls) == 1, f"list_models вызван {len(calls)} раз(а) вместо одного"


# -- Требование ревью 3: закрытие окна во время опроса не роняет поток -----

def test_closing_window_during_poll_does_not_crash_background_thread(tk, monkeypatch, tmp_path):
    """Живой баг, воспроизведённый ревью: self.after(...) из фонового потока,
    вызванный после того как окно уже уничтожено, около секунды пытается
    достучаться до исчезнувшего цикла событий и затем бросает
    RuntimeError('main thread is not in main loop'). Поток обязан проглотить
    эту ошибку сам — иначе она долетает до threading.excepthook."""
    from longevity.storage import Storage
    from ui.widgets import ModelStore

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    store = ModelStore(root, storage)

    def slow_list_models(timeout=3):
        time.sleep(0.1)
        return []

    monkeypatch.setattr("ui.widgets.list_models", slow_list_models)

    errors = []
    old_hook = threading.excepthook
    threading.excepthook = lambda args: errors.append(args)
    try:
        store.refresh()
        thread = store._thread
        storage.close()
        root.destroy()  # окно закрыто раньше ответа сервиса — обычный сценарий
        # RuntimeError у self.after() из чужого потока после destroy()
        # всплывает не сразу (внутренняя попытка достучаться до цикла
        # событий занимает около секунды) — дожидаемся потока целиком,
        # а не спим наугад.
        thread.join(timeout=5)
        assert not thread.is_alive(), "фоновый поток так и не завершился"
    finally:
        threading.excepthook = old_hook

    assert errors == [], f"фоновый поток бросил исключение при закрытии окна: {errors}"


# -- Требование финального ревью: неудачная доставка не оставляет busy поднятым --

def test_failed_delivery_clears_busy_flag(tk, tmp_path):
    """Иначе кнопка «Обновить» блокируется навсегда — и сразу на обеих вкладках.

    refresh() выходит сразу, пока busy поднят, а снимает его только _apply,
    который выполняется в главном потоке. Если запланировать _apply не
    удалось, снять busy может только сама доставка.
    """
    from longevity.storage import Storage
    from ui.widgets import ModelStore

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    store = ModelStore(root, storage)
    store.busy = True
    store.status = "Опрашиваю Ollama..."
    storage.close()
    root.destroy()

    thread = threading.Thread(target=lambda: store._deliver([]))
    thread.start()
    thread.join(timeout=10)

    assert not thread.is_alive(), "фоновый поток так и не завершился"
    assert store.busy is False, "busy остался поднятым — «Обновить» больше не разблокируется"
    assert store.status == ""


def test_delivery_does_not_swallow_unexpected_errors(env, monkeypatch):
    """Перехват узкий: гаснут только ошибки закрытого окна, прочие — нет.

    Широкий `except Exception` прятал бы любую поломку доставки, включая
    опечатку в самом _apply, и наружу это выглядело бы как вечное
    «Опрашиваю Ollama...».
    """
    from types import SimpleNamespace

    _, _, _, store = env

    class Unexpected(Exception):
        pass

    def boom(*_args, **_kwargs):
        raise Unexpected("ошибка, не связанная с закрытым окном")

    monkeypatch.setattr(store, "_root", SimpleNamespace(after=boom))

    with pytest.raises(Unexpected):
        store._deliver([])

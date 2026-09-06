"""Страница «Питание»: кнопка генерации меню и доставка результата.

Оба дефекта, которые здесь закрыты, живут на одном пути — «нажал
сгенерировать, ушёл фоновый поток, вернулся результат»:

* кнопка разблокировалась последней строкой обработчика завершения, без
  гарантии: падение отрисовки меню оставляло её недоступной до перезапуска;
* доставка результата планировалась из фонового потока без защиты, и
  закрытие окна во время генерации (а идёт она до четырёх минут) роняло
  поток с RuntimeError('main thread is not in main loop').
"""

import threading
from types import SimpleNamespace

import pytest


def _make_page(root):
    from longevity.content import load_content
    from ui.nutrition_page import NutritionPage
    from ui.theme import Theme
    from ui.widgets import ModelStore

    app = SimpleNamespace(content=load_content(), theme=Theme(root),
                          storage=None, model_store=ModelStore(root, None))
    return NutritionPage(root, app)


@pytest.fixture
def page(tk):
    root = tk.Tk()
    root.withdraw()
    yield _make_page(root)
    root.destroy()


def _pretend_model_is_available(page):
    """Сделать вид, что Ollama ответила списком моделей (без сети)."""
    store = page.model_bar.store
    store.models = ["qwen3.5:4b"]
    store.current = "qwen3.5:4b"


def test_menu_done_unlocks_the_button(page):
    page.gen_btn.config(state="disabled")

    page._menu_done(page.app.content.menu, "Меню сгенерировано Ollama.")

    assert str(page.gen_btn["state"]) == "normal"
    assert page.status_var.get() == "Меню сгенерировано Ollama."


def test_button_unlocked_even_if_menu_rendering_fails(page, monkeypatch):
    """Ровно тот дефект, который в ассистенте закрыт гарантией.

    Если отрисовка меню бросит исключение, кнопка обязана всё равно
    разблокироваться: иначе сгенерировать меню больше нельзя до перезапуска
    приложения.
    """
    page.gen_btn.config(state="disabled")

    def boom(_menu):
        raise RuntimeError("сбой отрисовки меню")

    monkeypatch.setattr(page, "_fill_menu", boom)

    with pytest.raises(RuntimeError):
        page._menu_done(page.app.content.menu, "любой статус")

    assert str(page.gen_btn["state"]) == "normal", \
        "после падения отрисовки кнопка осталась заблокированной навсегда"


def test_button_unlocked_if_background_thread_cannot_start(page, monkeypatch):
    """Синхронный участок между блокировкой кнопки и стартом потока.

    Если поток не запустится, разблокировать кнопку некому — _menu_done
    никогда не будет вызван.
    """
    from ui import nutrition_page

    _pretend_model_is_available(page)

    class RefusingThread:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("не удалось создать поток")

    monkeypatch.setattr(nutrition_page.threading, "Thread", RefusingThread)

    with pytest.raises(RuntimeError):
        page.generate_menu_ollama()

    assert str(page.gen_btn["state"]) == "normal", \
        "поток не стартовал, а кнопка осталась заблокированной"


def test_without_a_model_button_stays_usable(page):
    """Ollama недоступна — показывается базовое меню, кнопка не блокируется."""
    page.generate_menu_ollama()

    assert str(page.gen_btn["state"]) == "normal"
    assert "базовое меню" in page.status_var.get()


def test_closing_window_during_generation_does_not_crash_background_thread(tk):
    """Генерация меню идёт до четырёх минут — окно закрывают именно тогда."""
    root = tk.Tk()
    root.withdraw()
    page = _make_page(root)
    menu = page.app.content.menu
    root.destroy()  # окно закрыто раньше, чем модель вернула меню

    errors = []

    def work():
        try:
            page._deliver((menu, "Меню сгенерировано Ollama."))
        except BaseException as exc:  # noqa: BLE001 — ловим ради проверки
            errors.append(f"{type(exc).__name__}: {exc}")

    thread = threading.Thread(target=work)
    thread.start()
    thread.join(timeout=10)

    assert not thread.is_alive(), "фоновый поток так и не завершился"
    assert errors == [], f"доставка меню в закрытое окно бросила исключение: {errors}"

import threading
from types import SimpleNamespace

import pytest


def _make_page(root):
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from ui.assistant_page import AssistantPage
    from ui.theme import Theme
    from ui.widgets import ModelStore

    content = load_content()
    app = SimpleNamespace(
        content=content,
        index=SearchIndex(content),
        theme=Theme(root),   # настоящая тема: страница берёт из неё шрифты при построении
        storage=None,
        # Общий store как в LongevityApp, но никто не вызывает refresh() —
        # эти тесты проверяют блокировку ввода, а не список моделей, и не
        # должны тянуть сеть.
        model_store=ModelStore(root, None),
    )
    return AssistantPage(root, app)


@pytest.fixture
def page(tk, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    root = tk.Tk()
    root.withdraw()

    yield _make_page(root)
    root.destroy()


def test_all_inputs_disabled_while_busy(page):
    page._lock_input()

    assert str(page.entry["state"]) == "disabled"
    for button in page.quick_buttons:
        assert str(button["state"]) == "disabled", "быстрые вопросы тоже должны блокироваться"
    assert str(page.ask_button["state"]) == "disabled"


def test_inputs_restored_after_unlock(page):
    page._lock_input()
    page._unlock_input()

    assert str(page.entry["state"]) == "normal"
    for button in page.quick_buttons:
        assert str(button["state"]) == "normal"


def test_second_question_ignored_while_busy(page):
    page._busy = True
    before = page.chat.get("1.0", "end")

    page.send_question("вопрос во время ответа")

    assert page.chat.get("1.0", "end") == before, "второй вопрос не должен попадать в чат"


def test_ollama_done_unlocks_after_error(page):
    """Ошибка сети не должна навсегда заблокировать интерфейс.

    _ollama_done — единственный обработчик завершения: и при успешном
    ответе, и при пойманном в work() исключении вызывается именно он
    (текст ошибки приходит как обычная строка результата). Если в нём
    забыть вызвать _unlock_input, интерфейс останется заблокированным
    навсегда после любого сбоя Ollama.
    """
    page._lock_input()

    page._ollama_done("⚠ Не удалось обратиться к Ollama: болванка ошибки")

    assert not page._busy, "после ошибки Ollama интерфейс остался заблокирован"
    assert str(page.entry["state"]) == "normal"
    assert str(page.ask_button["state"]) == "normal"
    for button in page.quick_buttons:
        assert str(button["state"]) == "normal"


def test_unlock_survives_exception_while_finishing_pending(page, monkeypatch):
    """Именно тот сценарий с устаревшей меткой pending_start.

    Если вставка готового ответа в чат (_finish_pending) бросает исключение —
    разблокировка обязана всё равно произойти, иначе пользователь не сможет
    ни спросить снова, ни отменить, только перезапустить приложение.
    """
    page._lock_input()

    def boom(_result):
        raise RuntimeError("сбой вставки ответа (устаревшая метка)")

    monkeypatch.setattr(page, "_finish_pending", boom)

    with pytest.raises(RuntimeError):
        page._ollama_done("любой ответ")

    assert not page._busy, "после падения _finish_pending интерфейс остался заблокирован"
    assert str(page.entry["state"]) == "normal"
    assert str(page.ask_button["state"]) == "normal"
    for button in page.quick_buttons:
        assert str(button["state"]) == "normal"


def test_worker_returns_safe_text_when_ollama_and_local_fallback_both_fail(page, monkeypatch):
    """Сеть недоступна, а запасной локальный поиск тоже упал.

    _ollama_answer_or_fallback выполняется в фоновом потоке и обязана
    вернуть строку, а не бросить исключение — иначе поток умрёт до вызова
    self.after(...), и разблокировки не произойдёт никогда. Дополнительно
    прогоняем результат через _ollama_done, чтобы убедиться, что вся цепочка
    восстановления доходит до реальной разблокировки.
    """
    from ui import assistant_page

    def boom_network(model, prompt):
        raise RuntimeError("сеть недоступна")

    def boom_local(query):
        raise RuntimeError("локальный поиск тоже сломан")

    monkeypatch.setattr(assistant_page, "ask_ollama", boom_network)
    monkeypatch.setattr(page, "_answer", boom_local)

    page._lock_input()
    result = page._ollama_answer_or_fallback("модель", "промпт", "вопрос про сон")
    assert isinstance(result, str) and result, \
        "воркер обязан вернуть текст, а не бросить исключение при двойном сбое"

    page._ollama_done(result)

    assert not page._busy, "после двойного сбоя интерфейс остался заблокирован"
    assert str(page.entry["state"]) == "normal"
    for button in page.quick_buttons:
        assert str(button["state"]) == "normal"


# -- распознавание темы вопроса --------------------------------------------

def test_week_wording_wins_over_day_plan(page):
    """«Расписание на неделю» — про неделю, а не про сегодня.

    Вопрос подходит под оба набора основ сразу: «расписан» — план на день,
    «недел» — календарь. Пока план проверялся первым, недельная формулировка
    отдавала расписание одного дня.
    """
    answer = page._answer("расписание на неделю")

    assert answer.startswith("Расписание на текущую неделю"), \
        f"недельный вопрос отдал не недельный ответ: {answer.splitlines()[0]!r}"


def test_day_wording_still_gives_the_day_plan(page):
    """Обратная сторона перестановки: вопрос про день не должен уехать в неделю."""
    answer = page._answer("план на сегодня")

    assert answer.startswith("План на "), \
        f"вопрос про день отдал не дневной план: {answer.splitlines()[0]!r}"
    assert "Расписание на текущую неделю" not in answer


def test_calendar_wording_gives_the_week(page):
    assert page._answer("календарь").startswith("Расписание на текущую неделю")


def test_menya_does_not_look_like_a_nutrition_question(page):
    """«У меня плохой сон» — не вопрос про питание.

    analyze("меню") == analyze("меня") == analyze("менее") == ["мен"], поэтому
    основа «мен» в наборе тем питания подмешивала в запрос к модели весь блок
    правил диеты MIND — на вопросе про сон в том числе.
    """
    assert not page._is_about_nutrition("у меня плохой сон")
    assert not page._is_about_nutrition("мне менее понятно")
    assert "Правила диеты MIND" not in page._build_ollama_prompt("у меня плохой сон")


def test_menu_question_still_pulls_the_mind_rules(page):
    """При этом само «меню» темой питания быть не перестало."""
    assert page._is_about_nutrition("составь меню на неделю")
    assert "Правила диеты MIND" in page._build_ollama_prompt("составь меню на неделю")


def test_plain_nutrition_words_still_recognised(page):
    for query in ("что есть, чтобы жить дольше", "правила питания", "диета mind"):
        assert page._is_about_nutrition(query), f"«{query}» перестал быть вопросом про питание"


def test_closing_window_during_answer_does_not_crash_background_thread(tk, tmp_path, monkeypatch):
    """Окно закрыли, пока модель думает — самый вероятный момент закрытия.

    Ответа ждут десятки секунд. after(), вызванный из фонового потока после
    того как окно уничтожено, бросает RuntimeError('main thread is not in
    main loop') — до задачи 10 это чинили только в ui/widgets.py, а здесь
    воспроизводилось живьём. Поток обязан проглотить ошибку сам, иначе она
    долетает до threading.excepthook.
    """
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    root = tk.Tk()
    root.withdraw()
    page = _make_page(root)
    root.destroy()  # пользователь закрыл окно раньше, чем ответила модель

    errors = []

    def work():
        try:
            page._deliver("готовый ответ модели")
        except BaseException as exc:  # noqa: BLE001 — ловим ради проверки
            errors.append(f"{type(exc).__name__}: {exc}")

    thread = threading.Thread(target=work)
    thread.start()
    thread.join(timeout=10)

    assert not thread.is_alive(), "фоновый поток так и не завершился"
    assert errors == [], f"доставка ответа в закрытое окно бросила исключение: {errors}"


def test_unlock_if_prompt_build_fails_before_thread_starts(page, monkeypatch):
    """Синхронный участок между блокировкой и стартом потока тоже может упасть.

    Если сборка промпта (или что угодно до threading.Thread(...).start())
    бросает исключение, поток не запустится вовсе — разблокировать ввод
    в этом случае может только сам _answer_ollama_async.
    """
    def boom(query):
        raise RuntimeError("не удалось собрать промпт")

    monkeypatch.setattr(page, "_build_ollama_prompt", boom)

    with pytest.raises(RuntimeError):
        page._answer_ollama_async("вопрос")

    assert not page._busy, "после сбоя сборки промпта интерфейс остался заблокирован"
    assert str(page.entry["state"]) == "normal"
    assert str(page.ask_button["state"]) == "normal"
    for button in page.quick_buttons:
        assert str(button["state"]) == "normal"

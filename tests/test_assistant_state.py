import pytest


@pytest.fixture
def page(tmp_path, monkeypatch):
    tk = pytest.importorskip("tkinter")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from ui.assistant_page import AssistantPage
    from ui.theme import Theme

    root = tk.Tk()
    root.withdraw()

    class FakeApp:
        content = load_content()
        index = SearchIndex(content)
        theme = Theme(root)   # настоящая тема: страница берёт из неё шрифты при построении
        storage = None

    p = AssistantPage(root, FakeApp())
    yield p
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

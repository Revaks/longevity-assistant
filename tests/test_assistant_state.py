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

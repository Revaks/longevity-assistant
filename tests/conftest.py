"""Общие приспособления тестов.

Оконные тесты нельзя защитить одним `pytest.importorskip("tkinter")`: модуль
tkinter прекрасно импортируется и без дисплея, а падает уже создание окна —
`TclError: no display name and no $DISPLAY environment variable`. Из-за этого
`env -u DISPLAY pytest` давал 13 упавших и 17 ошибок: на машине сборки без
дисплея вся оконная часть набора была красной.

Фикстура `tk` закрывает это в одном месте: она отдаёт модуль tkinter, если
окно создать есть где, и пропускает тест, если негде. Проверка именно
пробная (создать и сразу уничтожить скрытое окно), а не по переменной
DISPLAY: на Windows и macOS Tk работает и без неё.
"""

import pytest

_probe_result = None


def _display_available() -> bool:
    """Можно ли вообще создать окно. Проба выполняется один раз за прогон."""
    global _probe_result
    if _probe_result is not None:
        return _probe_result
    try:
        import tkinter
    except ImportError:
        _probe_result = False
        return _probe_result
    try:
        root = tkinter.Tk()
    except tkinter.TclError:
        _probe_result = False
    else:
        root.withdraw()
        root.destroy()
        _probe_result = True
    return _probe_result


@pytest.fixture
def tk():
    """Модуль tkinter — или пропуск теста, если Tk нет или окно создать негде."""
    module = pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("нет дисплея: Tk-окно создать негде")
    return module

"""Проверяет, что main() не роняет приложение, если базу нельзя открыть.

Обработчик ошибок старта (longevity.__main__.main) сам не должен звать
что-либо, что может снова бросить исключение — иначе трассировка уйдёт в
никуда под pythonw или в macOS-бандле, где консоли нет вовсе. Тест подменяет
диалог заглушкой, поэтому реальный дисплей не нужен: Tk() внутри
_show_start_error не создаётся.
"""

import os

import pytest


def test_unwritable_data_dir_shows_dialog_instead_of_crashing(tmp_path, monkeypatch):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)

    if os.access(locked, os.W_OK):
        pytest.skip("права каталога проигнорированы (например, тесты идут от root)")

    monkeypatch.setenv("XDG_DATA_HOME", str(locked))

    import longevity.__main__ as entrypoint

    shown = []
    monkeypatch.setattr(entrypoint, "_show_start_error",
                         lambda title, reason: shown.append((title, reason)))

    try:
        rc = entrypoint.main()
    finally:
        locked.chmod(0o700)

    assert rc != 0, "main() должен вернуть ненулевой код, а не молчать"
    assert len(shown) == 1, "диалог об ошибке должен быть показан ровно один раз"
    title, reason = shown[0]
    assert "базу данных" in title
    assert reason.strip(), "причина ошибки должна быть осмысленной, не пустой"

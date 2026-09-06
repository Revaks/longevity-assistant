"""Индикатор заметки в шапке дня.

Раньше отметка о заметке рисовалась эмодзи (" 📝" в тексте шапки) и была
убрана вместе с прочими эмодзи интерфейса. Эта проверка следит, чтобы
замена — иконка note размера 16 — действительно появлялась и исчезала
вместе с заметкой, а не осталась только в интерфейсе визуально.
"""

import datetime as dt
from types import SimpleNamespace

import pytest


def _build_page(root, storage):
    from longevity.content import load_content
    from ui.calendar_page import CalendarPage
    from ui.theme import Theme

    theme = Theme(root)
    app = SimpleNamespace(content=load_content(), storage=storage, theme=theme)
    return CalendarPage(root, app)


def test_note_icon_tracks_note_presence(tmp_path):
    tk = pytest.importorskip("tkinter")
    from longevity.storage import Storage

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        page = _build_page(root, storage)
        page.goto_today()
        today = dt.date.today()
        idx = (today - page.week_start).days
        header, _txt, _col = page.day_widgets[idx]

        assert header.cget("image") == "", "без заметки иконки быть не должно"

        storage.set_note(today.isoformat(), "проверка индикатора")
        page.refresh()
        assert header.cget("image") != "", "после сохранения заметки должна появиться иконка"

        storage.set_note(today.isoformat(), "")
        page.refresh()
        assert header.cget("image") == "", "после удаления заметки иконка должна исчезнуть"
    finally:
        storage.close()
        root.destroy()

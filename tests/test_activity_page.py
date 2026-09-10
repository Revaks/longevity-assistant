"""Вкладка «Активность»: отметки выполнения сохраняются и считаются."""

import datetime as dt
import tkinter as tk
from types import SimpleNamespace

from longevity.schedule import get_today_plan


def _build_page(root, storage, day=None):
    from longevity.content import load_content
    from ui.activity_page import ActivityPage
    from ui.theme import Theme

    theme = Theme(root)
    app = SimpleNamespace(content=load_content(), storage=storage, theme=theme)
    page = ActivityPage(root, app)
    if day is not None:
        page.selected_day = day
        page.refresh()
    return page


def test_toggle_marks_item_as_done(tk, tmp_path):
    from longevity.storage import Storage

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        monday = dt.date(2026, 9, 7)  # заведомо понедельник
        page = _build_page(root, storage, monday)
        items = get_today_plan(page.app.content, monday)
        assert items, "для понедельника должно быть расписание"
        item_id = items[0].id
        assert item_id in page._vars

        var = page._vars[item_id]
        page._toggle(item_id, var)

        assert var.get() is True
        assert item_id in storage.completions_on(monday.isoformat())

        page._toggle(item_id, var)
        assert var.get() is False
        assert item_id not in storage.completions_on(monday.isoformat())
    finally:
        storage.close()
        root.destroy()


def test_progress_label_reflects_done_count(tk, tmp_path):
    from longevity.storage import Storage

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        monday = dt.date(2026, 9, 7)
        page = _build_page(root, storage, monday)
        total = len(get_today_plan(page.app.content, monday))
        assert f"Сделано: 0 из {total}" in page.progress_label.cget("text")

        items = get_today_plan(page.app.content, monday)
        page._toggle(items[0].id, page._vars[items[0].id])
        assert f"Сделано: 1 из {total}" in page.progress_label.cget("text")
    finally:
        storage.close()
        root.destroy()

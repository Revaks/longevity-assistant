"""Вкладка «Заметки»: несколько записей на день, добавление не заменяет старые."""

import datetime as dt
import tkinter as tk
from types import SimpleNamespace


def _build_page(root, storage):
    from longevity.content import load_content
    from ui.notes_page import NotesPage
    from ui.theme import Theme

    theme = Theme(root)
    app = SimpleNamespace(content=load_content(), storage=storage, theme=theme)
    return NotesPage(root, app)


def test_save_creates_new_entry_and_does_not_replace(tk, tmp_path):
    from longevity.storage import Storage

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        page = _build_page(root, storage)
        date = dt.date.today().isoformat()

        page.note_text.insert("1.0", "первая запись")
        page.save()
        page.add_new()
        page.note_text.insert("1.0", "вторая запись")
        page.save()

        entries = storage.diary_entries_on(date)
        assert [e["text"] for e in entries] == ["первая запись", "вторая запись"], \
            "вторая запись заменила первую"
    finally:
        storage.close()
        root.destroy()


def test_selection_loads_entry_into_editor(tk, tmp_path):
    from longevity.storage import Storage

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        page = _build_page(root, storage)
        date = dt.date.today().isoformat()
        eid = storage.add_diary(date, "проверка выбора")
        page.refresh()

        page.tree.selection_set(str(eid))
        page._on_select()
        assert page.note_text.get("1.0", "end-1c") == "проверка выбора"
    finally:
        storage.close()
        root.destroy()


def test_delete_removes_only_selected_entry(tk, tmp_path):
    from longevity.storage import Storage

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        page = _build_page(root, storage)
        date = dt.date.today().isoformat()
        eid1 = storage.add_diary(date, "останется")
        eid2 = storage.add_diary(date, "удалится")
        page.refresh()

        page.tree.selection_set(str(eid2))
        page._on_select()
        page.delete_entry()

        entries = storage.diary_entries_on(date)
        assert [e["id"] for e in entries] == [eid1]
    finally:
        storage.close()
        root.destroy()

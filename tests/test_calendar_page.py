"""Календарь: индикатор заметок в шапке дня и показ записей дневника.

Раньше отметка о заметке рисовалась эмодзи (" 📝" в тексте шапки) и была
убрана вместе с прочими эмодзи интерфейса. Эти проверки следят, чтобы
замена — иконка note размера 16 — появлялась и исчезала вместе с заметками
дневника (их может быть несколько на день), а записи попадали в колонку дня.
"""

import datetime as dt
from types import SimpleNamespace


def _build_page(root, storage):
    from longevity.content import load_content
    from ui.calendar_page import CalendarPage
    from ui.theme import Theme

    theme = Theme(root)
    app = SimpleNamespace(content=load_content(), storage=storage, theme=theme)
    return CalendarPage(root, app)


def test_note_icon_tracks_note_presence(tk, tmp_path):
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

        entry_id = storage.add_diary(today.isoformat(), "проверка индикатора")
        page.refresh()
        assert header.cget("image") != "", "после добавления заметки должна появиться иконка"

        storage.delete_diary(entry_id)
        page.refresh()
        assert header.cget("image") == "", "после удаления заметки иконка должна исчезнуть"
    finally:
        storage.close()
        root.destroy()


def test_today_header_uses_light_variant_other_days_use_dark(tk, tmp_path):
    """Не просто «иконка есть», а именно тот вариант, который читаем на фоне.

    Фон «сегодня» темнее фона остальных дней (contrast_ratio проверяет это
    числом в tests/test_icons.py) — здесь проверяется, что CalendarPage
    действительно выбирает под него "note-light", а не всегда один и тот же
    файл.
    """
    from longevity.storage import Storage

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        page = _build_page(root, storage)
        page.goto_today()
        today = dt.date.today()
        other_day = page.week_start + dt.timedelta(days=(page.week_start.weekday() + 1) % 7)
        if other_day == today:
            other_day += dt.timedelta(days=1)
        assert other_day != today and page.week_start <= other_day <= page.week_start + dt.timedelta(days=6)

        storage.add_diary(today.isoformat(), "заметка на сегодня")
        storage.add_diary(other_day.isoformat(), "заметка на другой день")
        page.refresh()

        today_idx = (today - page.week_start).days
        other_idx = (other_day - page.week_start).days
        today_header, _t1, _c1 = page.day_widgets[today_idx]
        other_header, _t2, _c2 = page.day_widgets[other_idx]

        light = str(page.theme.icon("note-light", 16))
        dark = str(page.theme.icon("note", 16))

        assert today_header.cget("image") == light, (
            "сегодня фон тёмный (accent) — нужен светлый вариант иконки")
        assert other_header.cget("image") == dark, (
            "на светлом фоне обычного дня нужен тёмный вариант иконки")
    finally:
        storage.close()
        root.destroy()


def test_calendar_column_shows_all_diary_entries_of_day(tk, tmp_path):
    """Несколько записей дня отображаются в колонке календаря."""
    from longevity.storage import Storage

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        page = _build_page(root, storage)
        page.goto_today()
        today = dt.date.today()
        date = today.isoformat()
        storage.add_diary(date, "первая запись")
        storage.add_diary(date, "вторая запись")
        page.refresh()

        idx = (today - page.week_start).days
        _header, txt, _col = page.day_widgets[idx]
        text = txt.get("1.0", "end")
        assert "первая запись" in text
        assert "вторая запись" in text
    finally:
        storage.close()
        root.destroy()

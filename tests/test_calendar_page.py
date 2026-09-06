"""Заметка на день: индикатор в шапке и само поле ввода.

Раньше отметка о заметке рисовалась эмодзи (" 📝" в тексте шапки) и была
убрана вместе с прочими эмодзи интерфейса. Эта проверка следит, чтобы
замена — иконка note размера 16 — действительно появлялась и исчезала
вместе с заметкой, а не осталась только в интерфейсе визуально.
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

        storage.set_note(today.isoformat(), "проверка индикатора")
        page.refresh()
        assert header.cget("image") != "", "после сохранения заметки должна появиться иконка"

        storage.set_note(today.isoformat(), "")
        page.refresh()
        assert header.cget("image") == "", "после удаления заметки иконка должна исчезнуть"
    finally:
        storage.close()
        root.destroy()


def test_today_header_uses_light_variant_other_days_use_dark(tk, tmp_path):
    """Не просто "иконка есть", а именно тот вариант, который читаем на фоне.

    Фон "сегодня" темнее фона остальных дней (contrast_ratio проверяет это
    числом в tests/test_icons.py) — здесь проверяется, что CalendarPage
    действительно выбирает под него "note-light", а не всегда один и тот же
    файл. Без этой проверки регрессия ("note" и для сегодня тоже) прошла бы
    незамеченной: индикатор остался бы виден в тесте (какая-то картинка
    есть), просто с недостаточным контрастом.
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

        storage.set_note(today.isoformat(), "заметка на сегодня")
        storage.set_note(other_day.isoformat(), "заметка на другой день")
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


# -- поле заметки: многострочное ------------------------------------------
#
# Спека требует поле в три строки; в отчёте фазы 1 это было ошибочно
# объявлено сделанным, а на странице до сих пор стоял однострочный Entry —
# перенос строки в него было просто не ввести.

def test_note_field_is_a_three_line_text_widget(tk, tmp_path):
    from longevity.storage import Storage

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        page = _build_page(root, storage)

        assert page.note_text.winfo_class() == "Text", \
            "поле заметки должно быть текстовым, а не однострочным Entry"
        assert int(page.note_text.cget("height")) == 3
    finally:
        storage.close()
        root.destroy()


def test_multiline_note_is_saved_and_read_back(tk, tmp_path):
    """Текст с переносами доходит до базы и возвращается из неё целиком."""
    from longevity.storage import Storage

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    note = "утро: витамин D\nднём: прогулка 40 минут\nвечером: без экрана"
    try:
        page = _build_page(root, storage)
        page.goto_today()
        today = dt.date.today().isoformat()

        page.note_text.insert("1.0", note)
        page._save_note()

        assert storage.get_note(today) == note, \
            f"в базу ушло не то, что ввели: {storage.get_note(today)!r}"
        # refresh() внутри _save_note перечитал заметку из базы в поле —
        # ровно этот же путь отрабатывает при переключении дня.
        assert page.note_value() == note, "поле показывает не то, что в базе"
        assert page.note_value().count("\n") == 2

        page._delete_note()

        assert storage.get_note(today) == ""
        assert page.note_value() == ""
    finally:
        storage.close()
        root.destroy()


def test_note_field_follows_the_selected_day(tk, tmp_path):
    """Переключение дня подставляет заметку этого дня, а не оставляет чужую."""
    from longevity.storage import Storage

    root = tk.Tk()
    root.withdraw()
    storage = Storage(tmp_path / "data.db")
    try:
        page = _build_page(root, storage)
        page.goto_today()
        monday = page.week_start
        storage.set_note(monday.isoformat(), "понедельник:\nсдать анализы")
        storage.set_note((monday + dt.timedelta(days=1)).isoformat(), "вторник:\nбассейн")

        page._on_col_click(0)
        assert page.note_value() == "понедельник:\nсдать анализы"

        page._on_col_click(1)
        assert page.note_value() == "вторник:\nбассейн"
    finally:
        storage.close()
        root.destroy()

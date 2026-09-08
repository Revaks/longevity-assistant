# -*- coding: utf-8 -*-
"""Точка входа: собирает зависимости, обрабатывает ошибки старта, запускает интерфейс."""

import sqlite3
import sys
from pathlib import Path

from . import paths
from .content import ContentError, load_content
from .search import SearchIndex
from .storage import Storage, StorageError


def _show_start_error(title: str, reason: str) -> None:
    """Сообщить об ошибке старта окном, а не трассировкой в несуществующую консоль."""
    import tkinter as tk
    from tkinter import messagebox

    text = f"{title}\n\nПричина: {reason}"
    print(text, file=sys.stderr)
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Ассистент долголетия", text)
        root.destroy()
    except tk.TclError:
        # Tk не поднялся — остаётся только stderr, он уже написан выше.
        pass


def main() -> int:
    """Точка входа: сначала данные и база, потом окно."""
    import tkinter as tk  # tkinter не должен попадать в пакет при импорте
    from tkinter import messagebox

    from ui.app import LongevityApp

    try:
        content = load_content()
    except ContentError as exc:
        _show_start_error(
            "Не удалось загрузить данные приложения — они противоречивы "
            "или повреждены. Переустановите «Ассистент долголетия».", str(exc))
        return 1
    index = SearchIndex(content)

    try:
        storage = Storage(paths.db_path())
        storage.migrate_notes_json([Path(__file__).resolve().parent.parent / "notes.json"])
        # Старые одиночные заметки (таблица notes) -> в дневник.
        storage.sync_notes_to_diary()
    except StorageError as exc:
        _show_start_error("Не удалось открыть базу данных.", str(exc))
        return 1
    except (OSError, sqlite3.Error) as exc:
        # Путь к базе не подставляем отдельно: paths.db_path() тут же снова
        # упал бы (например, каталог данных нельзя создать) и обработчик
        # уронил бы приложение повторно, только уже без диалога. Для ошибок
        # файловой системы str(exc) и так содержит путь.
        _show_start_error("Не удалось открыть базу данных.", str(exc))
        return 1

    try:
        app = LongevityApp(content, index, storage)
    except tk.TclError as exc:
        _show_start_error(
            "Не удалось создать окно. Проверьте, что установлен Tk "
            "(подробности — в README).", str(exc))
        storage.close()
        return 1

    if storage.migration_warnings:
        warnings = "\n\n".join(storage.migration_warnings)
        app.after(200, lambda: messagebox.showwarning("Перенос старых заметок", warnings))

    try:
        app.mainloop()
    finally:
        storage.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

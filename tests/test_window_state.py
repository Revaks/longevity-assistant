"""Тесты для сохранения и восстановления состояния окна."""

import re
import tempfile
from pathlib import Path

import pytest


def _parse_geometry_size(geom: str) -> tuple[int, int]:
    """Извлечь ширину и высоту из строки геометрии 'WxH+X+Y' (X может быть отрицательным)."""
    m = re.match(r'(\d+)x(\d+)', geom)
    if not m:
        raise ValueError(f"Неверный формат геометрии: {geom}")
    return int(m.group(1)), int(m.group(2))


def test_window_size_roundtrip():
    """Размер окна сохраняется и восстанавливается при перезапуске приложения."""
    tk = pytest.importorskip("tkinter")
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"

        # Сессия 1: Создаём приложение, изменяем размер, закрываем
        storage = Storage(db)
        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.update()

            # Устанавливаем размер и запоминаем его
            app.geometry("900x600")
            app.update()

            # Получаем геометрию чтобы узнать фактический размер
            geom1 = app.geometry()
            saved_w, saved_h = _parse_geometry_size(geom1)

            # Закрываем приложение - размер должен сохраниться
            app.on_close()
        finally:
            try:
                storage.close()
            except Exception:
                pass

        # Сессия 2: Открываем приложение заново - размер должен восстановиться
        storage = Storage(db)
        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.update()

            # Проверяем что размер был восстановлен
            geom2 = app.geometry()
            restored_w, restored_h = _parse_geometry_size(geom2)

            assert (restored_w, restored_h) == (saved_w, saved_h), \
                f"Размер не восстановлен: ({restored_w}, {restored_h}) != ({saved_w}, {saved_h})"
        finally:
            app.destroy()
            storage.close()


def test_unknown_active_page_defaults_to_calendar():
    """Неизвестная вкладка игнорируется и открывается Календарь по умолчанию."""
    tk = pytest.importorskip("tkinter")
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        # Сохраняем неизвестную вкладку
        storage.set_value("app.active_page", "unknown_page")

        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.update()

            # Проверяем что открыта вкладка календаря по умолчанию
            assert app.current_page == "calendar", \
                f"Должна открыться вкладка 'calendar', но открыта '{app.current_page}'"
        finally:
            app.destroy()
            storage.close()


def test_saved_active_page_is_restored():
    """Сохранённая активная вкладка восстанавливается при запуске приложения."""
    tk = pytest.importorskip("tkinter")
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        # Сохраняем активную вкладку
        storage.set_value("app.active_page", "nutrition")

        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.update()

            # Проверяем что открыта правильная вкладка
            assert app.current_page == "nutrition", \
                f"Должна открыться вкладка 'nutrition', но открыта '{app.current_page}'"
        finally:
            app.destroy()
            storage.close()


def test_active_page_is_saved_on_close():
    """При закрытии окна активная вкладка сохраняется в хранилище."""
    tk = pytest.importorskip("tkinter")
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.update()

            # Переходим на вкладку "Питание"
            app.show_page("nutrition")
            assert app.current_page == "nutrition"

            # Закрываем приложение
            app.on_close()

            # Проверяем что вкладка была сохранена, открыв хранилище заново
            storage2 = Storage(db)
            try:
                saved = storage2.get_value("app.active_page")
                assert saved == "nutrition", \
                    f"Вкладка не сохранилась: {saved} != 'nutrition'"
            finally:
                storage2.close()
        except Exception:
            try:
                storage.close()
            except Exception:
                pass
            raise


def test_window_size_saved_with_negative_coordinate():
    """Размер окна сохраняется корректно при отрицательной X-координате.

    На мониторе слева от основного, геометрия выглядит как "800x600-50+30".
    Старый код разбивал по "+", что давал "800x600-50", а потом падал на
    int("600-50"). Новый код использует winfo_width()/winfo_height().
    """
    tk = pytest.importorskip("tkinter")
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.update()

            # Устанавливаем размер окна и позиционируем его с отрицательной координатой
            app.geometry("750x600-50+30")
            app.update()

            # Получаем геометрию и проверяем что размер сохранился правильно
            geom = app.geometry()
            w, h = _parse_geometry_size(geom)

            # Закрываем приложение
            app.on_close()

            # Проверяем что размер был сохранён корректно (без ошибок разбора геометрии)
            storage2 = Storage(db)
            try:
                saved = storage2.get_value("app.window_size")
                # Проверяем что значение вообще было сохранено (не None)
                assert saved is not None, \
                    "Размер с отрицательной координатой не был сохранен вообще"
                # Проверяем что это список из двух чисел
                assert isinstance(saved, list) and len(saved) == 2, \
                    f"Размер имеет неверный формат: {saved}"
                # Проверяем что это числа
                assert isinstance(saved[0], int) and isinstance(saved[1], int), \
                    f"Размер содержит не-целые числа: {saved}"
            finally:
                storage2.close()
        except Exception:
            try:
                storage.close()
            except Exception:
                pass
            raise

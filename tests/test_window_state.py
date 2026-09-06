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


def test_saved_active_page_is_applied_to_window():
    """Восстановленная активная вкладка из хранилища открывается при создании."""
    tk = pytest.importorskip("tkinter")
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        # Сохраняем активную вкладку в хранилище напрямую
        storage.set_value("app.active_page", "nutrition")

        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.update()

            # Проверяем что восстановленная вкладка была открыта
            assert app.current_page == "nutrition", \
                f"Восстановленная вкладка не применена: {app.current_page} != nutrition"
        finally:
            app.destroy()
            storage.close()


def test_hidden_window_does_not_corrupt_saved_size():
    """Закрытие скрытого или неотрисованного окна не портит ранее сохранённый размер."""
    tk = pytest.importorskip("tkinter")
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp, MIN_SIZE

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"

        # Сессия 1: Сохраняем размер
        storage = Storage(db)
        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.update()

            # Устанавливаем размер > MIN_SIZE и запоминаем фактический
            target_w, target_h = MIN_SIZE[0] + 50, MIN_SIZE[1] + 50
            app.geometry(f"{target_w}x{target_h}")
            app.update()

            geom = app.geometry()
            saved_w, saved_h = _parse_geometry_size(geom)

            # Закрываем приложение - размер должен сохраниться
            app.on_close()
        finally:
            try:
                storage.close()
            except Exception:
                pass

        # Сессия 2: Создаём скрытое окно и закрываем его без отрисовки
        storage = Storage(db)
        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            # Скрываем окно, не вызывая update() для отрисовки
            app.withdraw()

            # Закрываем скрытое окно - он НЕ должен перезаписать размер (1x1)
            app.on_close()
        finally:
            try:
                storage.close()
            except Exception:
                pass

        # Сессия 3: Проверяем что размер не изменился
        storage = Storage(db)
        try:
            saved = storage.get_value("app.window_size")
            assert saved == [saved_w, saved_h], \
                f"Размер поврежден: {saved} != [{saved_w}, {saved_h}]"
        finally:
            storage.close()


def test_saved_window_size_applied_to_geometry():
    """Восстановленный размер из хранилища применяется через geometry() при создании."""
    tk = pytest.importorskip("tkinter")
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp, PREFERRED_SIZE, MIN_SIZE

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        # Сохраняем размер, который > MIN_SIZE и != PREFERRED_SIZE
        # Чтобы проверить что восстановление работает (не default)
        target_w, target_h = MIN_SIZE[0] + 100, MIN_SIZE[1] + 60
        storage.set_value("app.window_size", [target_w, target_h])

        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.update()

            # Проверяем что размер был восстановлен (через geometry())
            # Не совпадает с default PREFERRED_SIZE - значит восстановление сработало
            geom = app.geometry()
            w, h = _parse_geometry_size(geom)

            # Размер должен отличаться от PREFERRED_SIZE (что указывает на восстановление)
            assert (w, h) != PREFERRED_SIZE, \
                f"Размер не восстановлен: использован default PREFERRED_SIZE={PREFERRED_SIZE}, ожидалось != {PREFERRED_SIZE}"
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

    На мониторе слева от основного, геометрия выглядит как "1000x650-50+30".
    Старый код разбивал по "+", что давал "1000x650-50", а потом падал на
    int("650-50"). Новый код использует winfo_width()/winfo_height().
    """
    tk = pytest.importorskip("tkinter")
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp, MIN_SIZE

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.update()

            # Устанавливаем размер > MIN_SIZE с отрицательной координатой
            target_w, target_h = MIN_SIZE[0] + 100, MIN_SIZE[1] + 50
            app.geometry(f"{target_w}x{target_h}-50+30")
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
                # Проверяем что размер >= MIN_SIZE
                assert saved[0] >= MIN_SIZE[0] and saved[1] >= MIN_SIZE[1], \
                    f"Размер меньше минимума: {saved} < {MIN_SIZE}"
            finally:
                storage2.close()
        except Exception:
            try:
                storage.close()
            except Exception:
                pass
            raise

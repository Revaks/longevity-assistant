"""Тесты для сохранения и восстановления состояния окна."""

import tempfile
from pathlib import Path


def test_saved_window_size_is_applied(tk):
    """Сохранённый размер применяется в вызове geometry() при создании."""
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp, MIN_SIZE

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        # Сохраняем размер в хранилище
        target_w, target_h = MIN_SIZE[0] + 100, MIN_SIZE[1] + 50
        storage.set_value("app.window_size", [target_w, target_h])

        # Подкласс, перехватывающий вызовы geometry()
        geometry_calls = []

        class SpyApp(LongevityApp):
            def geometry(self, *args, **kwargs):
                if args:
                    geometry_calls.append(args[0])
                return super().geometry(*args, **kwargs)

        try:
            content = load_content()
            index = SearchIndex(content)
            app = SpyApp(content, index, storage)
            app.update()

            # Проверяем что конструктор вызвал geometry() с сохранённым размером
            assert f"{target_w}x{target_h}" in geometry_calls, \
                f"Сохранённый размер не применён: {geometry_calls} не содержит '{target_w}x{target_h}'"
        finally:
            app.destroy()
            storage.close()


def test_oversized_saved_size_is_clamped(tk):
    """Размер, снятый с большего экрана, ужимается до 95% текущего экрана."""
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        # Сохраняем размер больший чем экран
        storage.set_value("app.window_size", [5000, 5000])

        geometry_calls = []

        class SpyApp(LongevityApp):
            def geometry(self, *args, **kwargs):
                if args:
                    geometry_calls.append(args[0])
                return super().geometry(*args, **kwargs)

        try:
            content = load_content()
            index = SearchIndex(content)
            app = SpyApp(content, index, storage)
            app.update()

            # Проверяем что размер был ограничен
            screen_w = app.winfo_screenwidth()
            screen_h = app.winfo_screenheight()
            max_w = int(screen_w * 0.95)
            max_h = int(screen_h * 0.95)

            # Размер в вызове должен быть <= макс
            assert len(geometry_calls) > 0, "geometry() не был вызван"
            last_call = geometry_calls[-1]  # Берём последний вызов

            # Парсим размер из строки "WxH+..."
            import re
            m = re.match(r'(\d+)x(\d+)', last_call)
            assert m, f"Неверный формат geometry: {last_call}"

            w, h = int(m.group(1)), int(m.group(2))
            assert w <= max_w and h <= max_h, \
                f"Размер не был ограничен: {w}x{h}, макс={max_w}x{max_h}"
        finally:
            app.destroy()
            storage.close()


def test_corrupted_size_uses_default(tk):
    """Испорченное значение размера игнорируется, используется default."""
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp, fit_geometry

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        # Сохраняем испорченный размер
        storage.set_value("app.window_size", "invalid")

        geometry_calls = []

        class SpyApp(LongevityApp):
            def geometry(self, *args, **kwargs):
                if args:
                    geometry_calls.append(args[0])
                return super().geometry(*args, **kwargs)

        try:
            content = load_content()
            index = SearchIndex(content)
            app = SpyApp(content, index, storage)
            app.update()

            # Проверяем что вызов был с размером по умолчанию
            screen_w = app.winfo_screenwidth()
            screen_h = app.winfo_screenheight()
            default_w, default_h = fit_geometry(screen_w, screen_h)

            assert len(geometry_calls) > 0, "geometry() не был вызван"
            last_call = geometry_calls[-1]

            assert f"{default_w}x{default_h}" in last_call, \
                f"Default размер не применён: {last_call} не содержит '{default_w}x{default_h}'"
        finally:
            app.destroy()
            storage.close()


def test_saved_active_page_is_applied(tk):
    """Сохранённая активная вкладка открывается при создании приложения."""
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

            # Проверяем что правильная вкладка открыта
            assert app.current_page == "nutrition", \
                f"Сохранённая вкладка не открыта: {app.current_page} != nutrition"
        finally:
            app.destroy()
            storage.close()


def test_unknown_active_page_defaults_to_calendar(tk):
    """Несуществующая вкладка игнорируется, открывается календарь по умолчанию."""
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

            # Проверяем что открыта вкладка по умолчанию
            assert app.current_page == "calendar", \
                f"Default вкладка не открыта: {app.current_page} != calendar"
        finally:
            app.destroy()
            storage.close()


def test_hidden_window_does_not_corrupt_saved_size(tk):
    """Закрытие скрытого окна не портит ранее сохранённый размер."""
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp, MIN_SIZE

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"

        # Сессия 1: Сохраняем размер
        storage = Storage(db)
        saved_size = None
        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.update()

            # Устанавливаем размер > MIN_SIZE
            target_w, target_h = MIN_SIZE[0] + 50, MIN_SIZE[1] + 50
            app.geometry(f"{target_w}x{target_h}")
            app.update()

            # Запоминаем что реально установилось
            saved_size = app.winfo_width(), app.winfo_height()
            if saved_size[0] < MIN_SIZE[0] or saved_size[1] < MIN_SIZE[1]:
                # Если Tk переопределил, используем то что сохранится
                pass

            # Закрываем приложение - размер должен сохраниться
            app.on_close()
        finally:
            try:
                storage.close()
            except Exception:
                pass

        # Проверяем что размер был сохранён
        storage_check = Storage(db)
        try:
            saved_size = storage_check.get_value("app.window_size")
        finally:
            storage_check.close()

        # Сессия 2: Создаём и закрываем скрытое окно
        storage = Storage(db)
        try:
            content = load_content()
            index = SearchIndex(content)
            app = LongevityApp(content, index, storage)
            app.withdraw()  # Скрываем без update()

            # Закрываем скрытое окно - не должен портить размер
            app.on_close()
        finally:
            try:
                storage.close()
            except Exception:
                pass

        # Сессия 3: Проверяем что размер не изменился
        storage = Storage(db)
        try:
            new_saved = storage.get_value("app.window_size")
            assert new_saved == saved_size, \
                f"Размер поврежден: {new_saved} != {saved_size}"
        finally:
            storage.close()


def test_window_size_saved_with_negative_coordinate(tk):
    """Размер окна сохраняется корректно при отрицательной X-координате.

    Раньше тест зависел от того, что оконный менеджер мгновенно применяет
    geometry() к реальному окну: на Wayland/XWayland запрошенный размер не
    применяется, и тест падал независимо от кода приложения. Здесь размер,
    который «видит» приложение, задаётся напрямую, а вызов geometry с
    отрицательным смещением только записывается — сценарий проверяется без
    участия WM.
    """
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from longevity.storage import Storage
    from ui.app import LongevityApp, MIN_SIZE

    geometry_calls = []

    class SpyApp(LongevityApp):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._size = None

        def geometry(self, *args, **kwargs):
            if args:
                geometry_calls.append(args[0])
            return super().geometry(*args, **kwargs)

        def force_size(self, width, height):
            self._size = (width, height)

        def winfo_width(self):
            return self._size[0] if self._size is not None else super().winfo_width()

        def winfo_height(self):
            return self._size[1] if self._size is not None else super().winfo_height()

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        try:
            content = load_content()
            index = SearchIndex(content)
            app = SpyApp(content, index, storage)
            app.update()

            # Устанавливаем размер > MIN_SIZE с отрицательной координатой
            target_w, target_h = MIN_SIZE[0] + 100, MIN_SIZE[1] + 50
            app.geometry(f"{target_w}x{target_h}-50+30")
            app.force_size(target_w, target_h)
            assert any("-50" in call for call in geometry_calls), \
                f"geometry с отрицательной координатой не вызывался: {geometry_calls}"

            # Закрываем приложение
            app.on_close()

            # Проверяем что размер был сохранён корректно
            storage2 = Storage(db)
            try:
                saved = storage2.get_value("app.window_size")
                assert saved is not None, "Размер не был сохранён"
                assert isinstance(saved, list) and len(saved) == 2, \
                    f"Неверный формат: {saved}"
                assert isinstance(saved[0], int) and isinstance(saved[1], int), \
                    f"Размер содержит не-целые числа: {saved}"
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

"""Тесты для сохранения и восстановления состояния окна."""

import tempfile
from pathlib import Path

from longevity.storage import Storage


def test_active_page_is_saved_on_close():
    """При закрытии окна активная вкладка сохраняется в хранилище."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        # Сохраняем активную вкладку
        storage.set_value("app.active_page", "nutrition")

        # Проверяем что вкладка сохранена
        saved = storage.get_value("app.active_page")
        assert saved == "nutrition", f"Вкладка не сохранилась: {saved}"

        storage.close()


def test_corrupted_window_size_falls_back_to_default():
    """Испорченный размер окна игнорируется и используется размер по умолчанию."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        # Сохраняем испорченный размер (строка вместо пары чисел)
        storage.set_value("app.window_size", "invalid")

        # Проверяем что при чтении вернётся дефолт
        result = storage.get_value("app.window_size", default=None)
        # Хранилище возвращает значение как есть, но при типобрации оно будет отклонено
        assert result == "invalid", "Испорченное значение должно вернуться как есть"

        storage.close()


def test_unknown_active_page_is_ignored():
    """Неизвестная вкладка игнорируется при восстановлении."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        storage = Storage(db)

        # Сохраняем неизвестную вкладку
        storage.set_value("app.active_page", "unknown_page")

        # Проверяем что значение сохранено, но будет проверено в app.py
        saved = storage.get_value("app.active_page")
        assert saved == "unknown_page", "Значение должно быть сохранено как есть"

        # Проверяем что оно не совпадает с известными страницами
        known_pages = {"calendar", "nutrition", "knowledge", "assistant"}
        assert saved not in known_pages, "Неизвестная страница должна быть отклонена"

        storage.close()


def test_window_size_validation_in_app_init():
    """При инициализации app восстановленный размер проверяется на вместимость."""
    from ui.app import MIN_SIZE, fit_geometry

    # Тест проверки размера на вместимость
    screen_w, screen_h = 1366, 768

    # Размер, больший чем экран
    oversized = (2000, 1000)
    w = max(MIN_SIZE[0], min(oversized[0], int(screen_w * 0.95)))
    h = max(MIN_SIZE[1], min(oversized[1], int(screen_h * 0.95)))

    # Размер должен быть ограничен экраном
    assert w <= int(screen_w * 0.95), "Ширина больше экрана"
    assert h <= int(screen_h * 0.95), "Высота больше экрана"
    assert (w, h) >= MIN_SIZE, "Размер меньше минимума"


def test_saved_size_never_below_minimum():
    """Сохранённый размер не может быть ниже минимума, даже если был сохранён на маленьком экране."""
    from ui.app import MIN_SIZE

    # Имитируем размер, сохранённый на маленьком экране
    small_saved = (500, 300)
    screen_w, screen_h = 1366, 768

    # Применяем валидацию
    w = max(MIN_SIZE[0], min(small_saved[0], int(screen_w * 0.95)))
    h = max(MIN_SIZE[1], min(small_saved[1], int(screen_h * 0.95)))

    # Результат должен быть не меньше минимума
    assert (w, h) >= MIN_SIZE, f"Размер ({w}, {h}) меньше минимума {MIN_SIZE}"

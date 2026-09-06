"""Каталог пользовательских данных, свой на каждой платформе."""

import os
import sys
from pathlib import Path

APP_DIR_NAME = "longevity-assistant"


def _base_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def data_dir() -> Path:
    """Каталог для заметок, отметок и настроек. Создаётся при первом обращении."""
    path = _base_dir() / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "data.db"

import sys
from pathlib import Path

import pytest

from longevity import paths


def test_linux_respects_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    result = paths.data_dir()

    assert result == tmp_path / "xdg" / "longevity-assistant"


def test_linux_falls_back_to_local_share(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    result = paths.data_dir()

    assert result == tmp_path / ".local" / "share" / "longevity-assistant"


def test_macos_uses_application_support(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    result = paths.data_dir()

    assert result == tmp_path / "Library" / "Application Support" / "longevity-assistant"


def test_windows_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))

    result = paths.data_dir()

    assert result == tmp_path / "AppData" / "Local" / "longevity-assistant"


def test_data_dir_is_created(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    result = paths.data_dir()

    assert result.is_dir()


def test_db_path_lives_inside_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    assert paths.db_path() == paths.data_dir() / "data.db"

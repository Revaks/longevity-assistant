import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_app_py_is_a_thin_wrapper():
    lines = [l for l in (ROOT / "app.py").read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]

    assert len(lines) <= 10, f"app.py должен быть обёрткой, в нём {len(lines)} строк"


def test_every_page_has_its_own_module():
    for name in ("calendar_page", "knowledge_page", "nutrition_page", "assistant_page"):
        assert (ROOT / "ui" / f"{name}.py").is_file(), f"нет модуля ui/{name}.py"


def test_no_ui_module_is_oversized():
    for path in (ROOT / "ui").glob("*.py"):
        count = len(path.read_text(encoding="utf-8").splitlines())
        assert count < 400, f"{path.name}: {count} строк — пора делить дальше"


def test_package_still_headless():
    code = ("import pkgutil, importlib, sys, longevity\n"
            "[importlib.import_module(m.name) for m in "
            "pkgutil.walk_packages(longevity.__path__, 'longevity.')]\n"
            "assert 'tkinter' not in sys.modules")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, cwd=ROOT)

    assert result.returncode == 0, result.stderr.decode()


def test_entry_point_declared():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "longevity-assistant" in text
    assert "longevity.__main__:main" in text

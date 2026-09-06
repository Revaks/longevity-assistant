def test_package_exposes_version():
    import longevity

    assert isinstance(longevity.__version__, str)
    assert longevity.__version__


def test_package_does_not_import_tkinter():
    """Ни один модуль пакета longevity не тянет tkinter — прямо или транзитивно.

    Проверяются не только longevity/__init__.py, но и каждый модуль пакета
    (обход через pkgutil.walk_packages), чтобы регрессия в любом будущем
    модуле (например, longevity/content.py) была поймана автоматически.
    """
    import subprocess
    import sys

    code = """
import importlib
import pkgutil
import sys

import longevity

def _on_walk_error(name):
    raise RuntimeError(f"не удалось обойти пакет {name}")

module_names = [
    name
    for _, name, _ in pkgutil.walk_packages(
        longevity.__path__, prefix="longevity.", onerror=_on_walk_error
    )
]

for name in ["longevity"] + module_names:
    importlib.import_module(name)
    if "tkinter" in sys.modules:
        sys.exit(f"{name} импортирует tkinter (прямо или транзитивно)")

print("OK")
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert result.returncode == 0, (result.stdout + result.stderr).decode()

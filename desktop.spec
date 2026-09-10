# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-сборка «Ассистента долголетия» в один исполняемый файл.

Данные приложения (longevity/data/*.json, icons/*.png) собираются через
collect_data_files("longevity") и попадают в sys._MEIPASS — их читает
importlib.resources (см. longevity/content.py и ui/theme.py).

Сборка:
    pip install pyinstaller .
    pyinstaller --noconfirm --clean desktop.spec

Результат: dist/longevity-assistant (Linux) или dist/longevity-assistant.exe
(Windows). На Windows console=False — приложение без чёрного окна консоли.
"""

# Данные приложения: копируем каталог longevity/data целиком (JSON + иконки).
# collect_data_files не подходит — пакет при сборке может быть не установлен.
datas = [("longevity/data", "longevity/data")]

# resources.files("longevity.data") импортирует пакет по строке — статический
# анализ PyInstaller этого не видит, поэтому пакет данных добавляем явно.
hiddenimports = ["longevity.data"]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="longevity-assistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

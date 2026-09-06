def test_package_exposes_version():
    import longevity

    assert isinstance(longevity.__version__, str)
    assert longevity.__version__


def test_package_does_not_import_tkinter():
    """longevity/ обязан оставаться headless: тесты идут без дисплея."""
    import subprocess
    import sys

    code = "import longevity, sys; assert 'tkinter' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()

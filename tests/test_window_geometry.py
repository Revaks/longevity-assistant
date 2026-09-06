from ui.app import MIN_SIZE, PREFERRED_SIZE, fit_geometry


def test_fits_small_laptop_screen():
    w, h = fit_geometry(1366, 768)

    assert w <= 1366 * 0.95 and h <= 768 * 0.95
    assert (w, h) >= MIN_SIZE


def test_uses_preferred_size_on_large_screen():
    assert fit_geometry(2560, 1440) == PREFERRED_SIZE


def test_never_goes_below_minimum():
    w, h = fit_geometry(800, 600)

    assert (w, h) == MIN_SIZE, "ниже минимума опускаться нельзя, даже если экран мал"


def test_minimum_fits_the_content():
    assert MIN_SIZE[0] <= 900 and MIN_SIZE[1] <= 600

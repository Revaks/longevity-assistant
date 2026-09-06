"""Шрифты, палитра и иконки — единственное место, где интерфейс задаёт вид."""

from tkinter import font as tkfont

FONT_CANDIDATES = (
    "Noto Sans", "DejaVu Sans", "Segoe UI", "Helvetica Neue", "SF Pro Text",
    "Cantarell", "Liberation Sans", "Arial",
)

PALETTE = {
    "bg": "#f4f5f7",
    "sidebar": "#1f2937",
    "sidebar_active": "#374151",
    "accent": "#0f766e",
    "text": "#111827",
    "muted": "#6b7280",
    "card": "#ffffff",
}


def pick_family(available: set[str]) -> str:
    for candidate in FONT_CANDIDATES:
        if candidate in available:
            return candidate
    return "TkDefaultFont"


class Theme:
    def __init__(self, root):
        self.family = pick_family(set(tkfont.families(root)))
        self.colors = dict(PALETTE)
        self._cache: dict[tuple, tkfont.Font] = {}

    def font(self, size: int = 10, weight: str = "normal", slant: str = "roman"):
        key = (size, weight, slant)
        if key not in self._cache:
            self._cache[key] = tkfont.Font(
                family=self.family, size=size, weight=weight, slant=slant)
        return self._cache[key]

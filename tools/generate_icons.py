# -*- coding: utf-8 -*-
"""Генератор PNG-иконок сайдбара.

Иконки лежат в поставке (`longevity/data/icons/*.png`), а не рисуются
эмодзи-шрифтом: на части целевых машин такого шрифта нет вовсе (проверено —
`📅` рисуется пустым прямоугольником), а Tk 8.6 умеет грузить в `PhotoImage`
только PNG/GIF — SVG появится лишь в Tk 8.7. PNG не требует ни Pillow, ни
других зависимостей в рантайме, поэтому этот скрипт — исключительно
инструмент разработчика. Он коммитится вместе с результатом, чтобы набор
можно было перерисовать одной правкой при смене палитры.

Пиктограммы рисуются примитивами `ImageDraw` в четырёхкратном разрешении и
уменьшаются с `Image.LANCZOS` — так получается сглаживание краёв без ручного
антиалиасинга.

Запуск: python3 tools/generate_icons.py
Требует Pillow: pip install -e ".[dev]"
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui.theme import PALETTE  # noqa: E402  (нужен sys.path.insert выше)

OUT_DIR = ROOT / "longevity" / "data" / "icons"

#: Во сколько раз рисовать крупнее целевого размера перед уменьшением.
SCALE = 4

#: Итоговые размеры иконок.
SIZES = (16, 32)

#: Цвет каждой иконки — по тому, на каком фоне она реально стоит в интерфейсе.
#: Четыре пункта меню лежат на тёмном фоне сайдбара (PALETTE["sidebar"]), поэтому
#: рисуются светлым — тем же PALETTE["card"], каким там же написан текст. Иконка
#: заметки и часы стоят на светлых поверхностях (шапка дня, карточки), поэтому
#: рисуются тёмным — PALETTE["sidebar"]. Цвет — параметр функций рисования,
#: смена палитры — правка одного этого словаря.
COLOR_BY_NAME = {
    "calendar": PALETTE["card"],
    "nutrition": PALETTE["card"],
    "knowledge": PALETTE["card"],
    "assistant": PALETTE["card"],
    "note": PALETTE["sidebar"],
    "clock": PALETTE["sidebar"],
}


def _canvas(s: int) -> Image.Image:
    return Image.new("RGBA", (s, s), (0, 0, 0, 0))


def _finish(img: Image.Image, size: int) -> Image.Image:
    return img.resize((size, size), Image.LANCZOS)


def draw_calendar(s: int, color: str) -> Image.Image:
    """Прямоугольник со скруглением, отрывной корешок сверху, сетка 3×2."""
    img = _canvas(s)
    d = ImageDraw.Draw(img)
    margin = s * 0.10
    top = s * 0.26
    bottom = s * 0.90
    stroke = max(1, round(s * 0.09))

    # ушки отрывного корешка над верхней гранью
    ring_w = s * 0.09
    for cx in (s * 0.32, s * 0.68):
        d.rounded_rectangle(
            [cx - ring_w / 2, s * 0.06, cx + ring_w / 2, top + s * 0.05],
            radius=ring_w / 2, fill=color)

    # корпус
    d.rounded_rectangle([margin, top, s - margin, bottom],
                         radius=s * 0.08, outline=color, width=stroke)

    # полоса-заголовок (оторванная часть)
    head_bottom = top + s * 0.20
    d.line([(margin, head_bottom), (s - margin, head_bottom)],
           fill=color, width=stroke)

    # сетка 3×2
    dot = s * 0.09
    for y in (s * 0.58, s * 0.77):
        for x in (s * 0.30, s * 0.50, s * 0.70):
            d.ellipse([x - dot / 2, y - dot / 2, x + dot / 2, y + dot / 2], fill=color)
    return img


def draw_nutrition(s: int, color: str) -> Image.Image:
    """Круг тарелки с дугой и вертикальной чертой (вилка)."""
    img = _canvas(s)
    d = ImageDraw.Draw(img)
    stroke = max(1, round(s * 0.08))

    cx, cy, r = s * 0.40, s * 0.50, s * 0.34
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=stroke)
    inner = r * 0.55
    d.arc([cx - inner, cy - inner, cx + inner, cy + inner], start=200, end=340,
          fill=color, width=max(1, round(s * 0.05)))

    # вилка справа от тарелки
    fx = s * 0.86
    d.line([(fx, s * 0.14), (fx, s * 0.90)], fill=color, width=stroke)
    for dx in (-s * 0.07, 0, s * 0.07):
        d.line([(fx + dx, s * 0.14), (fx + dx, s * 0.30)], fill=color,
               width=max(1, round(s * 0.045)))
    return img


def draw_knowledge(s: int, color: str) -> Image.Image:
    """Два прямоугольника раскрытой книги с корешком посередине."""
    img = _canvas(s)
    d = ImageDraw.Draw(img)
    stroke = max(1, round(s * 0.08))
    top, bottom = s * 0.22, s * 0.82
    cx = s * 0.5
    gap = s * 0.03

    d.rounded_rectangle([s * 0.10, top, cx - gap, bottom], radius=s * 0.05,
                         outline=color, width=stroke)
    d.rounded_rectangle([cx + gap, top, s * 0.90, bottom], radius=s * 0.05,
                         outline=color, width=stroke)
    d.line([(cx, top - s * 0.02), (cx, bottom + s * 0.02)], fill=color, width=stroke)
    return img


def draw_assistant(s: int, color: str) -> Image.Image:
    """Скруглённый прямоугольник с двумя точками-глазами и антенной."""
    img = _canvas(s)
    d = ImageDraw.Draw(img)
    stroke = max(1, round(s * 0.08))

    # антенна
    d.line([(s * 0.5, s * 0.08), (s * 0.5, s * 0.22)], fill=color, width=stroke)
    tip = s * 0.05
    d.ellipse([s * 0.5 - tip, s * 0.08 - tip, s * 0.5 + tip, s * 0.08 + tip], fill=color)

    # голова
    d.rounded_rectangle([s * 0.16, s * 0.24, s * 0.84, s * 0.86], radius=s * 0.16,
                         outline=color, width=stroke)

    # глаза
    eye = s * 0.07
    for ex in (s * 0.36, s * 0.64):
        ey = s * 0.52
        d.ellipse([ex - eye / 2, ey - eye / 2, ex + eye / 2, ey + eye / 2], fill=color)
    return img


def draw_note(s: int, color: str) -> Image.Image:
    """Лист с загнутым углом и тремя линиями текста."""
    img = _canvas(s)
    d = ImageDraw.Draw(img)
    stroke = max(1, round(s * 0.07))
    left, top, right, bottom = s * 0.20, s * 0.12, s * 0.80, s * 0.88
    fold = s * 0.16

    d.polygon([(left, top), (right - fold, top), (right, top + fold),
               (right, bottom), (left, bottom)], outline=color, width=stroke)
    d.line([(right - fold, top), (right - fold, top + fold), (right, top + fold)],
           fill=color, width=stroke)

    for y in (s * 0.42, s * 0.58, s * 0.74):
        d.line([(left + s * 0.10, y), (right - s * 0.10, y)], fill=color,
               width=max(1, round(s * 0.045)))
    return img


def draw_clock(s: int, color: str) -> Image.Image:
    """Окружность со стрелками."""
    img = _canvas(s)
    d = ImageDraw.Draw(img)
    stroke = max(1, round(s * 0.08))
    cx, cy, r = s * 0.5, s * 0.5, s * 0.38

    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=stroke)
    d.line([(cx, cy), (cx, cy - r * 0.55)], fill=color, width=stroke)  # минутная
    d.line([(cx, cy), (cx + r * 0.42, cy + r * 0.20)], fill=color, width=stroke)  # часовая
    dot = s * 0.05
    d.ellipse([cx - dot / 2, cy - dot / 2, cx + dot / 2, cy + dot / 2], fill=color)
    return img


ICONS = {
    "calendar": draw_calendar,
    "nutrition": draw_nutrition,
    "knowledge": draw_knowledge,
    "assistant": draw_assistant,
    "note": draw_note,
    "clock": draw_clock,
}


def generate(colors: dict[str, str] = COLOR_BY_NAME, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, draw_fn in ICONS.items():
        for size in SIZES:
            img = draw_fn(size * SCALE, colors[name])
            img = _finish(img, size)
            path = out_dir / f"{name}-{size}.png"
            img.save(path)
            print(f"написано {path.relative_to(ROOT)} ({path.stat().st_size} байт)")


if __name__ == "__main__":
    generate()

"""Загрузка данных приложения из JSON и проверка их целостности."""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Any

ANCHORS = ("clock", "morning", "allday")


class ContentError(Exception):
    """Данные приложения противоречивы и работать с ними нельзя."""


@dataclass(frozen=True)
class Tip:
    id: str
    cat: str
    title: str
    text: str
    sched: str
    source: str
    tags: str
    age_min: int | None
    rx: bool


@dataclass(frozen=True)
class ScheduleItem:
    id: str
    title: str
    detail: str
    cat: str
    days: tuple[int, ...]
    anchor: str
    time: str | None
    tips: tuple[str, ...]
    requires: dict[str, Any]
    alt: dict[str, str] | None


@dataclass(frozen=True)
class RotationVariant:
    """Вариант пункта расписания для ротации по неделям."""
    level: int
    title: str
    detail: str


@dataclass(frozen=True)
class FocusWeek:
    """Тема недели («фокус») с заданиями."""
    id: str
    title: str
    detail: str
    tasks: tuple[str, ...]


@dataclass(frozen=True)
class Screening:
    """Профилактическое обследование с ориентировочной периодичностью."""
    id: str
    title: str
    detail: str
    period_months: int
    age_min: int
    sex: str | None


@dataclass(frozen=True)
class MindGroup:
    name: str
    amount: str
    note: str


@dataclass(frozen=True)
class Book:
    id: str
    title: str
    subtitle: str
    author: str


@dataclass(frozen=True)
class Passage:
    """Отрывок книги — единица поиска по книгам и контекста RAG."""
    id: str
    book: str
    section: str
    text: str



@dataclass(frozen=True)
class MenuDay:
    day: str
    breakfast: str
    lunch: str
    dinner: str
    snack: str


@dataclass(frozen=True)
class Content:
    tips: tuple[Tip, ...]
    schedule: tuple[ScheduleItem, ...]
    synonyms: dict[str, str]
    mind_good: tuple[MindGroup, ...]
    mind_limit: tuple[MindGroup, ...]
    menu: tuple[MenuDay, ...]
    app_title: str
    app_subtitle: str
    disclaimer: str
    categories: tuple[str, ...]
    cat_colors: dict[str, str]
    quick_questions: tuple[str, ...]
    books: tuple[Book, ...] = ()
    passages: tuple[Passage, ...] = ()
    rotations: dict[str, tuple[RotationVariant, ...]] = field(default_factory=dict)
    focus: tuple[FocusWeek, ...] = ()
    screenings: tuple[Screening, ...] = ()

    def tip(self, tip_id: str) -> Tip:
        for tip in self.tips:
            if tip.id == tip_id:
                return tip
        raise KeyError(tip_id)

    def book(self, book_id: str) -> Book:
        for book in self.books:
            if book.id == book_id:
                return book
        raise KeyError(book_id)

    def passage(self, passage_id: str) -> Passage:
        for passage in self.passages:
            if passage.id == passage_id:
                return passage
        raise KeyError(passage_id)

    @classmethod
    def build(cls, tips, schedule, synonyms, mind, meta, books=None, extras=None) -> "Content":
        categories = tuple(_field(meta, "categories", "list", "meta.json"))
        tip_objects = tuple(_build_tip(t, i) for i, t in enumerate(_records(tips, "tips.json"), 1))
        _check_tips(tip_objects, categories)

        item_objects = tuple(
            _build_item(s, i) for i, s in enumerate(_records(schedule, "schedule.json"), 1)
        )
        _check_schedule(item_objects, {t.id for t in tip_objects})

        if not isinstance(synonyms, dict):
            raise ContentError(
                f"synonyms.json: ожидался объект, получено {type(synonyms).__name__}")

        if books is None:
            book_objects, passage_objects = (), ()
        else:
            book_objects, passage_objects = _build_books(books)

        rotations, focus, screenings = _build_extras(
            extras, {item.id for item in item_objects})

        return cls(
            tips=tip_objects,
            schedule=item_objects,
            synonyms=dict(synonyms),
            mind_good=tuple(
                _build_group(g, i, "good")
                for i, g in enumerate(_field(mind, "good", "list", "mind.json"), 1)
            ),
            mind_limit=tuple(
                _build_group(g, i, "limit")
                for i, g in enumerate(_field(mind, "limit", "list", "mind.json"), 1)
            ),
            menu=tuple(
                _build_menu_day(row, i)
                for i, row in enumerate(_field(mind, "menu", "list", "mind.json"), 1)
            ),
            app_title=_field(meta, "app_title", "str", "meta.json"),
            app_subtitle=_field(meta, "app_subtitle", "str", "meta.json"),
            disclaimer=_field(meta, "disclaimer", "str", "meta.json"),
            categories=categories,
            cat_colors=dict(_field(meta, "cat_colors", "dict", "meta.json")),
            quick_questions=tuple(_field(meta, "quick_questions", "list", "meta.json")),
            books=book_objects,
            passages=passage_objects,
            rotations=rotations,
            focus=focus,
            screenings=screenings,
        )


# ----------------------------------------------------------------------
# Чтение полей: отсутствующий или неверного типа ключ должен называть
# и совет, и поле, а не улетать наверх сырым KeyError.
# ----------------------------------------------------------------------
_CHECKS = {
    "str": (lambda v: isinstance(v, str), "строкой"),
    "str?": (lambda v: v is None or isinstance(v, str), "строкой или null"),
    "bool": (lambda v: isinstance(v, bool), "true или false"),
    "int?": (lambda v: v is None or (isinstance(v, int) and not isinstance(v, bool)),
             "целым числом или null"),
    "list": (lambda v: isinstance(v, list), "списком"),
    "dict": (lambda v: isinstance(v, dict), "объектом"),
    "dict?": (lambda v: v is None or isinstance(v, dict), "объектом или null"),
}


def _field(record, key: str, check: str, where: str):
    """Значение поля с понятной ошибкой вместо KeyError и TypeError."""
    if not isinstance(record, dict):
        raise ContentError(f"{where}: ожидался объект, получено {type(record).__name__}")
    if key not in record:
        raise ContentError(f"{where}: нет обязательного поля {key!r}")
    ok, expected = _CHECKS[check]
    value = record[key]
    if not ok(value):
        raise ContentError(
            f"{where}: поле {key!r} должно быть {expected}, "
            f"а не {type(value).__name__}"
        )
    return value


def _optional_field(record, key: str, check: str, where: str, default):
    """То же, но поля может не быть — тип проверяется, только если оно есть."""
    if not isinstance(record, dict):
        raise ContentError(f"{where}: ожидался объект, получено {type(record).__name__}")
    if key not in record:
        return default
    return _field(record, key, check, where)


def _records(raw, where: str) -> list:
    if not isinstance(raw, list):
        raise ContentError(f"{where}: ожидался список, получено {type(raw).__name__}")
    return raw


def _where(record, index: int, kind: str) -> str:
    """Имя записи для сообщения: идентификатор, если он есть, иначе номер."""
    if isinstance(record, dict) and isinstance(record.get("id"), str) and record["id"]:
        return f"{kind} {record['id']}"
    return f"{kind} №{index}"


def _build_tip(t, index: int) -> Tip:
    where = _where(t, index, "совет")
    return Tip(
        id=_field(t, "id", "str", where),
        cat=_field(t, "cat", "str", where),
        title=_field(t, "title", "str", where),
        text=_field(t, "text", "str", where),
        sched=_field(t, "sched", "str", where),
        source=_field(t, "source", "str", where),
        tags=_field(t, "tags", "str", where),
        age_min=_field(t, "age_min", "int?", where),
        rx=_field(t, "rx", "bool", where),
    )


def _build_item(s, index: int) -> ScheduleItem:
    where = _where(s, index, "пункт расписания")
    return ScheduleItem(
        id=_field(s, "id", "str", where),
        title=_field(s, "title", "str", where),
        detail=_field(s, "detail", "str", where),
        cat=_field(s, "cat", "str", where),
        days=tuple(_field(s, "days", "list", where)),
        anchor=_field(s, "anchor", "str", where),
        time=_field(s, "time", "str?", where),
        tips=tuple(_optional_field(s, "tips", "list", where, [])),
        requires=dict(_optional_field(s, "requires", "dict", where, {})),
        alt=_optional_field(s, "alt", "dict?", where, None),
    )


def _build_group(g, index: int, section: str) -> MindGroup:
    where = f"mind.json, {section} №{index}"
    return MindGroup(
        name=_field(g, "name", "str", where),
        amount=_field(g, "amount", "str", where),
        note=_field(g, "note", "str", where),
    )


def _build_menu_day(row, index: int) -> MenuDay:
    where = f"mind.json, меню, день №{index}"
    return MenuDay(
        day=_field(row, "day", "str", where),
        breakfast=_field(row, "breakfast", "str", where),
        lunch=_field(row, "lunch", "str", where),
        dinner=_field(row, "dinner", "str", where),
        snack=_field(row, "snack", "str", where),
    )


def _build_books(raw) -> tuple[tuple[Book, ...], tuple[Passage, ...]]:
    """Разбор books.json: книги и отрывки с проверкой ссылок.

    Поломанный или противоречивый файл останавливает запуск так же, как
    повреждённые советы: тихо «не те» отрывки хуже явной ошибки.
    """
    if not isinstance(raw, dict):
        raise ContentError(f"books.json: ожидался объект, получено {type(raw).__name__}")
    book_rows = _records(_field(raw, "books", "list", "books.json"), "books.json")
    passage_rows = _records(_field(raw, "passages", "list", "books.json"), "books.json")

    books: list[Book] = []
    seen_ids: set[str] = set()
    for i, row in enumerate(book_rows, 1):
        where = _where(row, i, "книга")
        book = Book(
            id=_field(row, "id", "str", where),
            title=_field(row, "title", "str", where),
            subtitle=_field(row, "subtitle", "str", where),
            author=_field(row, "author", "str", where),
        )
        if book.id in seen_ids:
            raise ContentError(f"books.json: дублирующийся id книги: {book.id}")
        if not book.title.strip():
            raise ContentError(f"{where}: пустое название")
        seen_ids.add(book.id)
        books.append(book)

    book_ids = set(seen_ids)
    passages: list[Passage] = []
    seen: set[str] = set()
    for i, row in enumerate(passage_rows, 1):
        where = _where(row, i, "отрывок")
        passage = Passage(
            id=_field(row, "id", "str", where),
            book=_field(row, "book", "str", where),
            section=_field(row, "section", "str", where),
            text=_field(row, "text", "str", where),
        )
        if passage.id in seen:
            raise ContentError(f"books.json: дублирующийся id отрывка: {passage.id}")
        if passage.book not in book_ids:
            raise ContentError(
                f"{where}: ссылка на несуществующую книгу {passage.book!r}")
        if not passage.text.strip():
            raise ContentError(f"{where}: пустой текст отрывка")
        seen.add(passage.id)
        passages.append(passage)
    return tuple(books), tuple(passages)


def _build_extras(raw, schedule_ids: set[str]):
    """Разбор extras.json: ротация пунктов, фокусы недель, обследования.

    Возвращает (rotations, focus, screenings). Отсутствующий файл (raw is None)
    даёт пустые наборы — без extras календарь работает, просто без ротации.
    """
    if raw is None:
        return {}, (), ()
    if not isinstance(raw, dict):
        raise ContentError(f"extras.json: ожидался объект, получено {type(raw).__name__}")

    rotations: dict[str, tuple[RotationVariant, ...]] = {}
    for i, row in enumerate(_records(_field(raw, "rotations", "list", "extras.json"), "extras.json"), 1):
        where = _where(row, i, "ротация")
        item_id = _field(row, "item_id", "str", where)
        if item_id not in schedule_ids:
            raise ContentError(f"{where}: ссылка на несуществующий пункт расписания {item_id!r}")
        variants: list[RotationVariant] = []
        for vi, v in enumerate(_records(_field(row, "variants", "list", where), where), 1):
            vw = f"{where}, вариант №{vi}"
            level = _field(v, "level", "int?", vw)
            if level is None:
                level = 0
            if isinstance(level, bool) or not 0 <= level <= 2:
                raise ContentError(f"{vw}: level должен быть 0..2")
            variants.append(RotationVariant(
                level=level,
                title=_field(v, "title", "str", vw),
                detail=_field(v, "detail", "str", vw),
            ))
        if not variants:
            raise ContentError(f"{where}: нет ни одного варианта")
        rotations[item_id] = tuple(variants)

    focus: list[FocusWeek] = []
    seen_focus: set[str] = set()
    for i, row in enumerate(_records(_field(raw, "focus", "list", "extras.json"), "extras.json"), 1):
        where = _where(row, i, "фокус недели")
        tasks_raw = _records(_field(row, "tasks", "list", where), where)
        tasks: list[str] = []
        for ti, task in enumerate(tasks_raw, 1):
            if not isinstance(task, str):
                raise ContentError(f"{where}: задание №{ti} должно быть строкой")
            tasks.append(task)
        if not tasks:
            raise ContentError(f"{where}: нет заданий")
        fw = FocusWeek(
            id=_field(row, "id", "str", where),
            title=_field(row, "title", "str", where),
            detail=_field(row, "detail", "str", where),
            tasks=tuple(tasks),
        )
        if fw.id in seen_focus:
            raise ContentError(f"extras.json: дублирующийся id фокуса: {fw.id}")
        seen_focus.add(fw.id)
        focus.append(fw)

    screenings: list[Screening] = []
    seen_screen: set[str] = set()
    for i, row in enumerate(_records(_field(raw, "screenings", "list", "extras.json"), "extras.json"), 1):
        where = _where(row, i, "обследование")
        sex = _field(row, "sex", "str?", where)
        if sex is not None and sex not in ("м", "ж"):
            raise ContentError(f"{where}: пол должен быть 'м', 'ж' или отсутствовать")
        period = _field(row, "period_months", "int?", where)
        if period is None:
            period = 12
        if isinstance(period, bool) or period <= 0:
            raise ContentError(f"{where}: period_months должен быть больше нуля")
        age_min = _field(row, "age_min", "int?", where)
        if age_min is None:
            age_min = 18
        if isinstance(age_min, bool) or age_min < 0:
            raise ContentError(f"{where}: age_min не может быть отрицательным")
        sc = Screening(
            id=_field(row, "id", "str", where),
            title=_field(row, "title", "str", where),
            detail=_field(row, "detail", "str", where),
            period_months=period,
            age_min=age_min,
            sex=sex,
        )
        if sc.id in seen_screen:
            raise ContentError(f"extras.json: дублирующийся id обследования: {sc.id}")
        seen_screen.add(sc.id)
        screenings.append(sc)

    return rotations, tuple(focus), tuple(screenings)


def _check_tips(tips: tuple[Tip, ...], categories: tuple[str, ...]) -> None:
    seen: set[str] = set()
    for tip in tips:
        if tip.id in seen:
            raise ContentError(f"дублирующийся id совета: {tip.id}")
        seen.add(tip.id)
        if tip.cat not in categories:
            raise ContentError(f"{tip.id}: неизвестная категория {tip.cat!r}")
        if not tip.source.strip():
            raise ContentError(f"{tip.id}: пустой источник")


def _check_schedule(items: tuple[ScheduleItem, ...], tip_ids: set[str]) -> None:
    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            raise ContentError(f"дублирующийся id пункта расписания: {item.id}")
        seen.add(item.id)
        if item.anchor not in ANCHORS:
            raise ContentError(f"{item.id}: неизвестный anchor {item.anchor!r}")
        if item.anchor == "clock" and not item.time:
            raise ContentError(f"{item.id}: clock-пункт без времени")
        if item.anchor != "clock" and item.time is not None:
            raise ContentError(f"{item.id}: время указано у пункта с anchor={item.anchor}")
        for ref in item.tips:
            if ref not in tip_ids:
                raise ContentError(f"{item.id}: ссылка на несуществующий совет {ref}")
        if item.requires and not item.alt:
            raise ContentError(f"{item.id}: есть requires, но нет альтернативы alt")


def _read(name: str):
    try:
        with resources.files("longevity.data").joinpath(name).open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        # ValueError покрывает и битый JSON, и оборванный UTF-8. Наверх уходит
        # ContentError, чтобы у запуска был один тип ошибки для показа.
        raise ContentError(f"{name}: файл данных не читается ({exc})") from exc


@lru_cache(maxsize=1)
def load_content() -> Content:
    return Content.build(
        tips=_read("tips.json"),
        schedule=_read("schedule.json"),
        synonyms=_read("synonyms.json"),
        mind=_read("mind.json"),
        meta=_read("meta.json"),
        books=_read("books.json"),
        extras=_read("extras.json"),
    )

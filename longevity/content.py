"""Загрузка данных приложения из JSON и проверка их целостности."""

import json
from dataclasses import dataclass
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
class MindGroup:
    name: str
    amount: str
    note: str


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

    def tip(self, tip_id: str) -> Tip:
        for tip in self.tips:
            if tip.id == tip_id:
                return tip
        raise KeyError(tip_id)

    @classmethod
    def build(cls, tips, schedule, synonyms, mind, meta) -> "Content":
        categories = tuple(meta["categories"])
        tip_objects = tuple(
            Tip(id=t["id"], cat=t["cat"], title=t["title"], text=t["text"],
                sched=t["sched"], source=t["source"], tags=t["tags"],
                age_min=t["age_min"], rx=t["rx"])
            for t in tips
        )
        _check_tips(tip_objects, categories)

        item_objects = tuple(
            ScheduleItem(
                id=s["id"], title=s["title"], detail=s["detail"], cat=s["cat"],
                days=tuple(s["days"]), anchor=s["anchor"], time=s["time"],
                tips=tuple(s.get("tips", ())), requires=dict(s.get("requires", {})),
                alt=s.get("alt"),
            )
            for s in schedule
        )
        _check_schedule(item_objects, {t.id for t in tip_objects})

        return cls(
            tips=tip_objects,
            schedule=item_objects,
            synonyms=dict(synonyms),
            mind_good=tuple(MindGroup(**g) for g in mind["good"]),
            mind_limit=tuple(MindGroup(**g) for g in mind["limit"]),
            menu=tuple(MenuDay(**row) for row in mind["menu"]),
            app_title=meta["app_title"],
            app_subtitle=meta["app_subtitle"],
            disclaimer=meta["disclaimer"],
            categories=categories,
            cat_colors=dict(meta["cat_colors"]),
            quick_questions=tuple(meta["quick_questions"]),
        )


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
    with resources.files("longevity.data").joinpath(name).open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_content() -> Content:
    return Content.build(
        tips=_read("tips.json"),
        schedule=_read("schedule.json"),
        synonyms=_read("synonyms.json"),
        mind=_read("mind.json"),
        meta=_read("meta.json"),
    )

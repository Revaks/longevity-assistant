"""Серии, прогресс недели и проблемные пункты."""

import datetime as dt

from longevity.habits import daily_ratios, streaks, weak_spots, week_progress


def test_streak_counts_consecutive_scheduled_days_and_skips_other_days():
    today = dt.date(2026, 9, 9)

    def scheduled(day):
        return {"a"} if day.day % 2 == 1 else set()

    def done(day):
        return {"a"} if day.day in (9, 7, 5) else set()

    assert streaks(["a"], today, scheduled, done)["a"] == 3


def test_today_not_done_yet_does_not_break_the_streak():
    today = dt.date(2026, 9, 9)

    def scheduled(day):
        return {"a"}

    def done(day):
        return {"a"} if day < today else set()

    assert streaks(["a"], today, scheduled, done)["a"] == 180


def test_missed_scheduled_day_breaks_the_streak():
    today = dt.date(2026, 9, 9)

    def scheduled(day):
        return {"a"}

    def done(day):
        return set() if day.day == 8 else {"a"}

    assert streaks(["a"], today, scheduled, done)["a"] == 1


def test_streak_is_zero_when_never_done():
    today = dt.date(2026, 9, 9)
    assert streaks(["a"], today, lambda day: {"a"}, lambda day: set())["a"] == 0


def test_week_progress_counts_only_planned_and_ignores_future_days():
    monday = dt.date(2026, 9, 7)
    today = dt.date(2026, 9, 9)  # среда
    planned_by_day = {
        monday: {"a", "b"},
        monday + dt.timedelta(days=1): {"a"},
        monday + dt.timedelta(days=2): {"a", "b"},
        monday + dt.timedelta(days=3): {"a"},  # будущее — не считаем
    }
    done_by_day = {
        monday: {"a"},
        monday + dt.timedelta(days=1): {"a"},
        monday + dt.timedelta(days=2): set(),
    }

    completed, total = week_progress(
        monday, today,
        item_ids_for=lambda day: planned_by_day.get(day, set()),
        done=lambda day: done_by_day.get(day, set()),
    )
    assert completed == 2
    assert total == 5

    ratios = daily_ratios(
        monday, today,
        item_ids_for=lambda day: planned_by_day.get(day, set()),
        done=lambda day: done_by_day.get(day, set()),
    )
    assert len(ratios) == 7
    assert ratios[0] == 0.5
    assert ratios[1] == 1.0
    assert ratios[2] == 0.0
    assert ratios[5] == 0.0  # будущий день


def test_weak_spots_are_sorted_by_completion_ratio():
    planned = {"a": 10, "b": 10, "c": 10, "rare": 1}
    done = {"a": 9, "b": 2, "c": 5, "rare": 0}
    weak = weak_spots(planned, done, limit=3, min_planned=3)
    assert [item_id for item_id, _ in weak] == ["b", "c", "a"]
    assert all(ratio <= 0.9 for _, ratio in weak)

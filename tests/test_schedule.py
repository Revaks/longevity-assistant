import datetime as dt

from longevity.content import ScheduleItem, load_content
from longevity.schedule import _time_key, display_time, get_today_plan

# Порядок, снятый с app.py до переноса логики в longevity/schedule.py.
# Любое расхождение означает, что календарь стал показывать пункты иначе.
EXPECTED_PLAN = {
    0: ["sleep_wake", "meal_breakfast", "train_aerobic", "train_strength",
        "supp_omega_d", "meal_lunch", "green_tea", "mental_load", "meal_dinner",
        "evening_walk", "dim_light", "sleep_start",
        "mind_greens", "mind_nuts", "mind_grains", "mind_legumes"],
    1: ["sleep_wake", "meal_breakfast", "train_walk", "supp_omega_d",
        "meal_lunch", "green_tea", "mental_load", "meal_dinner",
        "evening_walk", "dim_light", "sleep_start",
        "mind_greens", "mind_berries", "mind_grains", "mind_poultry"],
    2: ["sleep_wake", "meal_breakfast", "train_aerobic", "supp_omega_d",
        "meal_lunch", "green_tea", "mental_load", "meal_dinner",
        "evening_walk", "dim_light", "sleep_start",
        "mind_fish", "mind_greens", "mind_nuts", "mind_grains", "mind_legumes"],
    3: ["sleep_wake", "meal_breakfast", "train_walk", "train_strength",
        "supp_omega_d", "meal_lunch", "green_tea", "mental_load", "meal_dinner",
        "evening_walk", "dim_light", "sleep_start",
        "mind_greens", "mind_grains"],
    4: ["sleep_wake", "meal_breakfast", "train_aerobic", "supp_omega_d",
        "meal_lunch", "green_tea", "mental_load", "meal_dinner",
        "evening_walk", "dim_light", "sleep_start",
        "mind_fish", "mind_greens", "mind_nuts", "mind_grains",
        "mind_legumes", "mind_poultry"],
    5: ["sleep_wake", "meal_breakfast", "train_walk", "supp_omega_d",
        "meal_lunch", "green_tea", "mental_load", "meal_dinner",
        "evening_walk", "dim_light", "sleep_start",
        "sauna", "mind_greens", "mind_berries", "mind_nuts", "mind_grains"],
    6: ["weekly_review", "sleep_wake", "meal_breakfast", "supp_omega_d",
        "meal_lunch", "green_tea", "mental_load", "meal_dinner",
        "evening_walk", "dim_light", "sleep_start",
        "mind_fish", "mind_nuts", "mind_grains"],
}

# Понедельник, чтобы day.weekday() совпадал со смещением от этой даты.
MONDAY = dt.date(2026, 9, 7)


def _item(item_id: str, anchor: str, time=None, days=(0, 1, 2, 3, 4, 5, 6)) -> ScheduleItem:
    return ScheduleItem(id=item_id, title=item_id, detail="", cat="Питание",
                        days=tuple(days), anchor=anchor, time=time,
                        tips=(), requires={}, alt=None)


# -- подпись времени ---------------------------------------------------
def test_display_time_for_clock_anchor():
    assert display_time(_item("s", "clock", "06:30")) == "06:30"


def test_display_time_for_morning_anchor():
    assert display_time(_item("s", "morning")) == "утро"


def test_display_time_for_allday_anchor():
    assert display_time(_item("s", "allday")) == "весь день"


# -- порядок сортировки ------------------------------------------------
def test_clock_items_are_ordered_by_hour_and_minute():
    assert _time_key("06:30") < _time_key("07:00") < _time_key("22:30")


def test_morning_lands_before_the_earliest_clock_item():
    assert _time_key("утро") < _time_key("06:30")


def test_allday_lands_after_every_clock_item():
    assert _time_key("весь день") > _time_key("23:59")


def test_all_three_anchors_sort_morning_clock_allday():
    items = [_item("allday", "allday"), _item("clock", "clock", "13:00"),
             _item("morning", "morning")]

    ordered = sorted(items, key=lambda s: _time_key(display_time(s)))

    assert [s.id for s in ordered] == ["morning", "clock", "allday"]


def test_single_digit_hour_is_parsed_as_clock():
    assert _time_key("9:05") == (0, 9, 5)


# -- состав плана ------------------------------------------------------
def test_plan_for_every_weekday_matches_the_pre_move_order():
    content = load_content()

    for offset, expected in EXPECTED_PLAN.items():
        day = MONDAY + dt.timedelta(days=offset)
        assert day.weekday() == offset
        assert [s.id for s in get_today_plan(content, day)] == expected, (
            f"изменился порядок пунктов для дня недели {offset}"
        )


def test_plan_only_contains_items_scheduled_for_that_weekday():
    content = load_content()

    for offset in range(7):
        day = MONDAY + dt.timedelta(days=offset)
        for item in get_today_plan(content, day):
            assert offset in item.days


def test_plan_is_sorted_by_the_shown_time():
    content = load_content()

    for offset in range(7):
        day = MONDAY + dt.timedelta(days=offset)
        keys = [_time_key(display_time(s)) for s in get_today_plan(content, day)]
        assert keys == sorted(keys)


def test_weekly_review_appears_only_on_sunday():
    content = load_content()

    for offset in range(7):
        day = MONDAY + dt.timedelta(days=offset)
        ids = [s.id for s in get_today_plan(content, day)]
        assert ("weekly_review" in ids) is (offset == 6)

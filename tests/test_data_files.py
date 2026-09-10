import json
from importlib import resources


def load(name: str):
    with resources.files("longevity.data").joinpath(name).open(encoding="utf-8") as f:
        return json.load(f)


def test_tips_file_has_eighty_two_tips():
    tips = load("tips.json")

    assert len(tips) == 82
    assert len({t["id"] for t in tips}) == 82, "id советов должны быть уникальны"


def test_every_tip_keeps_its_source():
    for tip in load("tips.json"):
        assert tip["source"].strip(), f"{tip['id']} потерял ссылку на главу"


def test_tip_text_survived_the_move():
    tips = {t["id"]: t for t in load("tips.json")}

    assert tips["zh06"]["title"] == "Ложиться спать около 23:00"
    assert "мелатонина" in tips["zh06"]["text"]
    assert tips["zh06"]["cat"] == "Образ жизни"


def test_synonyms_and_meta():
    assert len(load("synonyms.json")) == 43

    meta = load("meta.json")
    assert meta["app_title"] == "Ассистент долголетия"
    assert len(meta["categories"]) == 4
    assert len(meta["quick_questions"]) == 8
    assert set(meta["cat_colors"]) == set(meta["categories"])
    assert meta["disclaimer"].strip()


def test_mind_groups_and_menu():
    mind = load("mind.json")

    assert len(mind["good"]) == 10
    assert len(mind["limit"]) == 5
    assert len(mind["menu"]) == 7
    assert mind["menu"][0]["day"] == "Понедельник"
    assert set(mind["menu"][0]) == {"day", "breakfast", "lunch", "dinner", "snack"}


def test_schedule_has_stable_ids():
    schedule = load("schedule.json")

    assert len(schedule) == 24
    ids = [item["id"] for item in schedule]
    assert len(set(ids)) == 24, "id пунктов расписания должны быть уникальны"
    assert all(item_id.strip() for item_id in ids), "пустой id недопустим"


def test_schedule_anchors_replace_time_parsing():
    schedule = {item["id"]: item for item in load("schedule.json")}

    assert schedule["sleep_wake"]["anchor"] == "clock"
    assert schedule["sleep_wake"]["time"] == "06:30"

    assert schedule["weekly_review"]["anchor"] == "morning"
    assert schedule["weekly_review"]["time"] is None

    assert schedule["mind_greens"]["anchor"] == "allday"
    assert schedule["mind_greens"]["time"] is None


def test_clock_items_have_time_and_others_do_not():
    for item in load("schedule.json"):
        if item["anchor"] == "clock":
            assert item["time"], f"{item['id']}: clock-пункт без времени"
        else:
            assert item["time"] is None, f"{item['id']}: время у не-clock пункта"


def test_schedule_links_to_tips():
    tip_ids = {t["id"] for t in load("tips.json")}

    for item in load("schedule.json"):
        assert item["tips"], f"{item['id']} не сослался ни на один совет"
        for ref in item["tips"]:
            assert ref in tip_ids, f"{item['id']} ссылается на несуществующий {ref}"


def test_strength_training_has_alternative_without_gym():
    schedule = {item["id"]: item for item in load("schedule.json")}
    item = schedule["train_strength"]

    assert item["requires"] == {"gym": True}
    assert item["alt"]["title"]
    assert item["alt"]["detail"]


def test_fish_day_has_vegetarian_alternative():
    schedule = {item["id"]: item for item in load("schedule.json")}
    item = schedule["mind_fish"]

    assert item["requires"] == {"diet": "omnivore"}
    assert "льняно" in item["alt"]["detail"].lower(), "омега-3 должна остаться в рационе"


def test_every_tip_declares_age_and_rx():
    for tip in load("tips.json"):
        assert "age_min" in tip, f"{tip['id']} без age_min"
        assert "rx" in tip, f"{tip['id']} без rx"
        assert tip["age_min"] is None or isinstance(tip["age_min"], int)
        assert isinstance(tip["rx"], bool)


def test_age_restricted_tips():
    tips = {t["id"]: t for t in load("tips.json")}

    assert tips["pit03"]["age_min"] == 50, "белок ограничивают с 50 лет"
    assert tips["dob14"]["age_min"] == 50, "мелатонин обсуждают после 50"
    assert tips["zh06"]["age_min"] is None, "спать вовремя полезно в любом возрасте"


def test_prescription_only_tips_are_flagged():
    tips = {t["id"]: t for t in load("tips.json")}
    expected_rx = {"proc04", "proc05", "proc06", "dob13", "dob14"}

    for tip_id in expected_rx:
        assert tips[tip_id]["rx"] is True, f"{tip_id} применяется только по назначению врача"

    flagged = {t["id"] for t in tips.values() if t["rx"]}
    assert flagged == expected_rx


def test_rx_matches_the_wording_criterion():
    """Критерий из плана считается прямо по тексту, а не держится на списке.

    Пометку rx получает совет, в тексте которого есть «только по назначению
    врача» или «самолечение опасно». Отдельно проверяется dob03: там формула
    другая («по анализу крови»), критерий не срабатывает, rx остаётся false —
    решение принято и зафиксировано в Task 5.
    """
    matched = set()
    for tip in load("tips.json"):
        haystack = " ".join(
            str(tip[field]) for field in ("title", "text", "sched", "tags")
        ).lower().replace("ё", "е")
        if "только по назначению врача" in haystack or "самолечение опасно" in haystack:
            matched.add(tip["id"])

    flagged = {t["id"] for t in load("tips.json") if t["rx"]}
    assert matched == flagged, "список rx разошёлся с критерием из плана"
    assert "dob03" not in matched


def test_new_book_tips_exist_with_book_sources():
    """Советы из «Мозга долгожителя» (mz*) и «Кишечника долгожителя» (kg*)."""
    tips = {t["id"]: t for t in load("tips.json")}

    for tip_id in ("mz01", "mz03", "mz06", "kg02", "kg03", "kg05"):
        assert tip_id in tips, f"нет совета {tip_id}"
        source = tips[tip_id]["source"]
        assert ("Мозг долгожителя" in source or
                "Кишечник долгожителя" in source), f"{tip_id}: источник не из книг"
        assert tips[tip_id]["rx"] is False


def test_schedule_references_the_new_book_tips():
    schedule = {s["id"]: s for s in load("schedule.json")}

    brain = schedule["brain_training"]
    assert "mz03" in brain["tips"] and brain["time"] == "17:00"

    gut = schedule["gut_prebiotics"]
    assert "kg02" in gut["tips"] and gut["anchor"] == "allday"

    assert "mz01" in schedule["sleep_start"]["tips"]
    assert "mz06" in schedule["train_walk"]["tips"]
    assert "kg01" in schedule["meal_dinner"]["tips"]

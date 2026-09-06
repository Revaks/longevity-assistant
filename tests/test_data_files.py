import json
from importlib import resources


def load(name: str):
    with resources.files("longevity.data").joinpath(name).open(encoding="utf-8") as f:
        return json.load(f)


def test_tips_file_has_all_seventy_tips():
    tips = load("tips.json")

    assert len(tips) == 70
    assert len({t["id"] for t in tips}) == 70, "id советов должны быть уникальны"


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

import math

import pytest

from longevity.content import Content, Tip, load_content
from longevity.search import Hit, SearchIndex, SYNONYM_WEIGHT
from longevity.text import analyze


@pytest.fixture(scope="module")
def index():
    return SearchIndex(load_content())


def _tip(id_, cat="", title="", text="", tags=""):
    """Минимальный совет для искусственного корпуса: только нужные для BM25F поля."""
    return Tip(
        id=id_, cat=cat, title=title, text=text, sched="", source="test",
        tags=tags, age_min=None, rx=False,
    )


def _content(*tips, synonyms=None):
    """Минимальный Content вокруг заданных советов — прочие поля индексу не нужны."""
    return Content(
        tips=tuple(tips), schedule=(), synonyms=synonyms or {}, mind_good=(),
        mind_limit=(), menu=(), app_title="", app_subtitle="", disclaimer="",
        categories=(), cat_colors={}, quick_questions=(),
    )


def test_finds_obvious_matches(index):
    ids = [hit.tip.id for hit in index.search("зелёный чай")]

    assert "pit18" in ids[:3]


def test_vitamin_d_does_not_return_everything(index):
    """Регресс: прежний фильтр выдавал все 70 советов на этот запрос."""
    hits = index.search("витамин д")

    assert 0 < len(hits) < 20, f"выдача из {len(hits)} записей — это не поиск"
    assert "dob01" in [h.tip.id for h in hits[:5]]


def test_multiword_query_prefers_documents_matching_both_words(index):
    hits = index.search("силовые тренировки")

    assert hits
    assert hits[0].tip.id in {"zh03", "zh01"}


def test_title_outweighs_body(index):
    """Совет с термином в заголовке должен обойти совет, где термин лишь упомянут."""
    hits = index.search("метформин")

    assert hits[0].tip.id == "proc04"


def test_rare_term_beats_common_one(index):
    hits = index.search("рапамицин")

    assert hits[0].tip.id == "proc05"
    assert len(hits) <= 5, "редкий термин не должен тянуть половину базы"


def test_synonyms_widen_search_but_weigh_less(index):
    """«сон» через синонимы достаёт мелатонин, но прямое попадание остаётся выше."""
    hits = index.search("сон")
    ids = [h.tip.id for h in hits]

    assert "zh06" in ids[:3]
    assert any(i in ids for i in ("zh07", "dob14")), "синонимы должны расширять выдачу"


def test_empty_and_stopword_queries_return_nothing(index):
    assert index.search("") == []
    assert index.search("   ") == []
    assert index.search("что как для") == []


def test_unknown_words_return_nothing(index):
    assert index.search("квазистохастический бламбер") == []


def test_scores_are_sorted_descending(index):
    hits = index.search("питание")

    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    assert all(h.score > 0 for h in hits)


def test_limit_is_respected(index):
    assert len(index.search("питание", limit=3)) <= 3


def test_returns_hit_objects(index):
    hit = index.search("зелёный чай")[0]

    assert isinstance(hit, Hit)
    assert hit.tip.title
    assert isinstance(hit.score, float)


def test_index_covers_every_tip(index):
    """Каждый совет должен находиться хотя бы по своему заголовку."""
    content = load_content()
    missing = []
    for tip in content.tips:
        ids = [h.tip.id for h in index.search(tip.title, limit=5)]
        if tip.id not in ids:
            missing.append(tip.id)

    assert not missing, f"советы не находятся по собственному заголовку: {missing}"


# ----------------------------------------------------------------------
# Точечные тесты на составляющие формулы.
#
# Тесты выше проверяют порядок выдачи на реальных данных, где компоненты
# формулы маскируют друг друга (например, короткий заголовок «метформин»
# выигрывает даже при равных весах полей — за счёт длины, а не веса).
# Здесь каждая составляющая проверяется числом, изолированно от прочих.
# ----------------------------------------------------------------------


def test_idf_distinguishes_rare_and_common_terms(index):
    """idf обязан отличать редкое слово корпуса от частого по формуле, а не быть
    константой — иначе скоринг вырождается в чистый tf."""
    rare = analyze("рапамицин")[0]
    common = analyze("питание")[0]
    n = index._n
    df_rare = index._df[rare]
    df_common = index._df[common]

    # Ожидаемые значения посчитаны напрямую по формуле idf, а не через вызов
    # index._idf — иначе тест был бы тавтологией и не поймал бы подмену idf
    # на константу.
    expected_rare = math.log((n - df_rare + 0.5) / (df_rare + 0.5) + 1)
    expected_common = math.log((n - df_common + 0.5) / (df_common + 0.5) + 1)

    assert index._idf(rare) == pytest.approx(expected_rare)
    assert index._idf(common) == pytest.approx(expected_common)
    assert index._idf(rare) > index._idf(common) * 2, (
        "редкое слово должно получать заметно больший idf, чем частое"
    )


def test_field_length_normalization_reduces_long_field_contribution():
    """При одинаковом числе вхождений термина короткое поле должно давать
    больший вклад в score, чем длинное — иначе нормировка на длину не работает.

    Искусственный корпус из двух советов: термин встречается по одному разу
    в обоих текстах, но текст одного совета в 11 раз длиннее другого.
    """
    short_tip = _tip("short", text="целебный")
    long_tip = _tip("long", text="целебный " + " ".join(["лишний"] * 10))
    index = SearchIndex(_content(short_tip, long_tip))

    scores = {h.tip.id: h.score for h in index.search("целебный")}

    assert scores["short"] > scores["long"]

    # Числовая проверка по формуле b=0.75, k1=1.2 — оба константы записаны здесь
    # буквально, а не импортом из search.py, чтобы тест ловил и порчу самой
    # логики нормировки (норму заменили на 1), а не только чтения b/k1.
    b, k1 = 0.75, 1.2
    avg_len_text = (1 + 11) / 2  # длины полей text: 1 токен у short, 11 у long
    norm_short = 1 - b + b * (1 / avg_len_text)
    norm_long = 1 - b + b * (11 / avg_len_text)
    tf_short = 1 / norm_short  # вес поля text = 1.0, count(term) = 1 в обоих
    tf_long = 1 / norm_long
    # idf и вес термина запроса одинаковы для short и long, поэтому в отношении
    # score сокращаются — остаётся только насыщение BM25 от разных tf.
    expected_ratio = (tf_short * (k1 + 1) / (tf_short + k1)) / (
        tf_long * (k1 + 1) / (tf_long + k1)
    )
    assert scores["short"] / scores["long"] == pytest.approx(expected_ratio)


def test_field_weight_prefers_title_hit_over_text_hit_at_equal_length():
    """Попадание в заголовок должно давать больший вклад, чем такое же попадание
    в текст, при равной длине обоих полей — иначе тест не отличит вес поля
    от эффекта длины (как «метформин»/proc04 на реальных данных).

    В обоих советах поле title и поле text состоят ровно из одного слова,
    так что норма на длину для title и text одинакова в обоих документах.
    """
    title_hit = _tip("title_hit", title="уникальтерм", text="нейтральное")
    text_hit = _tip("text_hit", title="нейтральное", text="уникальтерм")
    index = SearchIndex(_content(title_hit, text_hit))

    scores = {h.tip.id: h.score for h in index.search("уникальтерм")}

    assert scores["title_hit"] > scores["text_hit"]
    # При равной длине полей отношение вкладов равно отношению весов полей,
    # прогнанных через насыщение BM25 (K1): (3.0*(K1+1))/(3.0+K1) для title
    # против (1.0*(K1+1))/(1.0+K1) для text.
    assert scores["title_hit"] / scores["text_hit"] == pytest.approx(
        ((3.0 * 2.2) / (3.0 + 1.2)) / ((1.0 * 2.2) / (1.0 + 1.2))
    )


def test_synonym_terms_get_lower_weight_than_direct_terms(index):
    """Слово, попавшее в запрос напрямую, сохраняет вес 1.0, даже если оно же
    входит в раскрытие синонима другого слова того же запроса; слово, пришедшее
    только через синонимы, весит меньше.

    Ожидаемый вес синонима (0.4) записан здесь буквально по формуле из брифа,
    а не через импорт SYNONYM_WEIGHT — иначе тест не поймал бы порчу самой
    константы (её же ошибочное повышение до 1.0).
    """
    expected_synonym_weight = 0.4
    sleep_stem = analyze("сон")[0]
    melatonin_stem = analyze("мелатонин")[0]

    # «спать» раскрывается синонимами в том числе в «сон» и «мелатонин» —
    # ни того, ни другого слова в запросе нет, оба весят как синонимы.
    only_synonyms = index._weighted_terms("спать")
    assert only_synonyms[sleep_stem] == expected_synonym_weight
    assert only_synonyms[melatonin_stem] == expected_synonym_weight

    # «сон» указан в запросе напрямую вместе со «спать» — прямое попадание
    # обязано перебить пониженный вес, который дало бы раскрытие «спать».
    direct_and_synonym = index._weighted_terms("сон спать")
    assert direct_and_synonym[sleep_stem] == 1.0
    assert direct_and_synonym[melatonin_stem] == expected_synonym_weight


def test_formula_constants_match_the_spec():
    """Замок на гиперпараметры формулы: их порча константой (а не логикой)
    не всегда ловится поведенческими тестами выше, если порча совпадает
    с ожиданием теста по случайности — здесь сверка прямая и буквальная."""
    from longevity.search import B, FIELD_WEIGHTS, K1

    assert K1 == 1.2
    assert B == 0.75
    assert SYNONYM_WEIGHT == 0.4
    assert FIELD_WEIGHTS == {"title": 3.0, "tags": 2.0, "text": 1.0, "cat": 0.5}

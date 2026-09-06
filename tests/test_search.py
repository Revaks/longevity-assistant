import pytest

from longevity.content import load_content
from longevity.search import Hit, SearchIndex


@pytest.fixture(scope="module")
def index():
    return SearchIndex(load_content())


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

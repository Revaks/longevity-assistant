from longevity.text import STOPWORDS, analyze, normalize, stem, tokenize


def test_normalize_lowercases_and_unifies_yo():
    assert normalize("Зелёный ЧАЙ") == "зеленый чай"


def test_normalize_drops_punctuation():
    assert normalize("омега-3, витамин D!") == "омега 3 витамин d"


def test_tokenize_splits_on_whitespace():
    assert tokenize("зелёный чай") == ["зеленый", "чай"]
    assert tokenize("   ") == []


def test_stem_is_symmetric():
    """Ключевое свойство: одно слово в разных формах даёт одну основу."""
    assert stem("витамины") == stem("витамин")
    assert stem("тренировка") == stem("тренировки")
    assert stem("бегом") == stem("бега")


def test_stem_keeps_short_words_intact():
    assert stem("сон") == "сон"
    assert stem("чай") == "чай"
    assert stem("d3") == "d3"


def test_stem_does_not_over_truncate():
    """Основа не должна схлопываться до неразличимости."""
    assert len(stem("магния")) >= 4
    assert stem("магний") == stem("магния")
    assert stem("магний") != stem("метионин")


def test_analyze_drops_stopwords():
    result = analyze("какие добавки нужно принимать")

    assert "добавк" in " ".join(result)
    for word in ("какие", "нужно", "принимать"):
        assert stem(word) not in result


def test_analyze_is_the_same_for_query_and_document():
    query = analyze("витамины для сна")
    document = analyze("Витамин D3 улучшает сон")

    assert set(query) & set(document), "запрос и документ должны пересечься по основам"


def test_analyze_returns_empty_for_stopwords_only():
    assert analyze("что как для") == []


def test_stopwords_are_frozen():
    assert isinstance(STOPWORDS, frozenset)

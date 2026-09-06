from longevity.text import STOPWORDS, analyze, normalize, stem, tokenize, _FLEETING_VOWEL_MAP


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

    assert "добавк" in result  # проверка членства в списке, а не подстроки
    for word in ("какие", "нужно", "принимать"):
        assert stem(word) not in result


def test_analyze_is_the_same_for_query_and_document():
    query = analyze("витамины для сна")
    document = analyze("Витамин D3 улучшает сон")

    assert set(query) & set(document), "запрос и документ должны пересечься по основам"


def test_analyze_returns_empty_for_stopwords_only():
    assert analyze("что как для") == []


def test_stem_handles_fleeting_vowels():
    """Слова с беглой гласной сводятся к одной основе через словарь исключений."""
    # сон ~ сна (беглая 'о'): полная семья
    assert stem("сон") == "сон"   # базовая форма
    assert stem("сна") == "сон"   # генитив
    assert stem("сну") == "сон"   # датив
    assert stem("сном") == "сон"  # инструментал
    assert stem("сне") == "сон"   # локатив
    # все формы дают одну основу
    assert stem("сон") == stem("сна") == stem("сну") == stem("сном") == stem("сне")


def test_fleeting_vowel_map_is_consistent():
    """Инвариант: словарь беглой гласной полностью согласован.

    Три условия, проверяемые БЕЗ фильтрации (ни одна запись не должна пропускаться):

    1. Для каждой записи форма→цель: stem(форма) == цель.
       Ловит записи, которые словарь объявляет, но stem() не применяет.

    2. Каждая цель присутствует среди ключей словаря.
       Ловит семью без базовой формы (когда днем→день, но самого день нет).

    3. Для каждой цели: stem(цель) == цель.
       Ловит цель, которую обработка сама же потом отсекает.
    """
    for form, target in _FLEETING_VOWEL_MAP.items():
        # Условие 1: stem(форма) должна давать точно то, что в словаре
        assert stem(form) == target, (
            f"Условие 1: форма '{form}' должна стемиться в '{target}', "
            f"но даёт '{stem(form)}'"
        )

        # Условие 2: каждая цель должна быть в словаре (быть ключом)
        assert target in _FLEETING_VOWEL_MAP, (
            f"Условие 2: цель '{target}' должна быть в словаре как ключ "
            f"(базовая форма), но там её нет"
        )

        # Условие 3: stem(цель) должна быть стабильна (не отсекаться дальше)
        assert stem(target) == target, (
            f"Условие 3: цель '{target}' должна быть стабильной, "
            f"но stem() отсекает её в '{stem(target)}'"
        )


def test_stem_handles_dative_plural():
    """Дательный падеж множественного числа (-ам, -ям) отсекается правильно."""
    assert stem("тренировкам") == stem("тренировке")
    assert stem("орехам") == stem("ореха")
    assert stem("добавкам") == stem("добавка")
    assert stem("овощам") == stem("овоща")


def test_stopwords_are_frozen():
    assert isinstance(STOPWORDS, frozenset)

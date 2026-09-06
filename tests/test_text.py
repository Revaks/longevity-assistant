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
    """Инвариант: словарь беглой гласной не разъединяет совпадения.

    Для каждой записи в словаре её результат должен совпадать с результатом
    для базовой формы того же слова (то значение, которое естественный стемминг
    даёт для начальной формы).
    """
    # Для каждой формы в словаре проверяем, что её результат совпадает
    # с результатом для базовой формы (той, что естественно стемится)
    base_forms = {
        "сон": "сон",  # базовая форма сама себе отображается
    }

    for base, expected_stem in base_forms.items():
        # Все формы этого слова в словаре должны давать одну основу
        for form, mapped_stem in _FLEETING_VOWEL_MAP.items():
            if mapped_stem == expected_stem:
                # Если форма отображена на эту основу, то результат должен совпадать
                assert stem(form) == expected_stem, (
                    f"Форма '{form}' должна давать '{expected_stem}', "
                    f"но даёт '{stem(form)}'"
                )


def test_stem_handles_dative_plural():
    """Дательный падеж множественного числа (-ам, -ям) отсекается правильно."""
    assert stem("тренировкам") == stem("тренировке")
    assert stem("орехам") == stem("ореха")
    assert stem("добавкам") == stem("добавка")
    assert stem("овощам") == stem("овоща")


def test_stopwords_are_frozen():
    assert isinstance(STOPWORDS, frozenset)

"""Логика профилактических обследований: применимость, сроки, «пора ли».

Отметки о прохождении хранятся в профиле под ключами ``user.screen.<id>``;
здесь — только чистые вычисления по возрасту/полу и датам.
"""

import datetime as dt


def is_applicable(screening, profile) -> bool:
    """Относится ли обследование к пользователю.

    Пол неизвестен — показываем (интерфейс добавит подсказку уточнить профиль).
    """
    age = profile.age
    if age is not None and age < screening.age_min:
        return False
    sex = profile.sex
    if screening.sex is not None and sex is not None and screening.sex != sex:
        return False
    return True


def next_due(last_done, screening, today: dt.date) -> dt.date:
    """Следующая дата обследования; без отметки — «пора сейчас» (сегодня)."""
    if last_done is None:
        return today
    return _add_months(last_done, screening.period_months)


def is_due(last_done, screening, today: dt.date) -> bool:
    """Пора ли проходить (не проходили или срок вышел)."""
    if last_done is None:
        return True
    return not (_add_months(last_done, screening.period_months) > today)


def for_profile(content, profile, today: dt.date, last_done):
    """Применимые обследования, сначала те, что пора проходить.

    ``last_done(id)`` возвращает дату последнего прохождения или None.
    Возвращает список троек (обследование, последняя дата, пора ли).
    """
    entries = []
    for screening in content.screenings:
        if not is_applicable(screening, profile):
            continue
        last = last_done(screening.id)
        entries.append((screening, last, is_due(last, screening, today)))
    entries.sort(key=lambda e: (0 if e[2] else 1, next_due(e[1], e[0], today), e[0].id))
    return entries


def _add_months(day: dt.date, months: int) -> dt.date:
    """Прибавить месяцы, ограничивая день числом дней в результирующем месяце."""
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return dt.date(year, month, min(day.day, _days_in_month(year, month)))


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        nxt = dt.date(year + 1, 1, 1)
    else:
        nxt = dt.date(year, month + 1, 1)
    return (nxt - dt.timedelta(days=1)).day

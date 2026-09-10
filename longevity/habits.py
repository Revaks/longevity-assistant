"""Серии, прогресс недели и проблемные пункты — чистые функции.

Считают по отметкам выполнения (date + item_id) без Tkinter; покрываются
обычными тестами. Неплановые дни серию не прерывают.
"""

import datetime as dt


def streaks(item_ids, today: dt.date, scheduled, done,
            max_lookback_days: int = 180) -> dict:
    """Серии по пунктам: сколько подряд плановых дней пункт отмечен.

    ``scheduled(day)`` возвращает id пунктов, запланированных на день;
    ``done(day)`` — id отмеченных. Неплановые дни пропускаются. Если
    сегодняшний плановый день ещё не отмечен, серия не обрывается — считаем
    с предыдущего дня (успеть можно до вечера).
    """
    result = {item_id: 0 for item_id in item_ids}
    if not item_ids:
        return result
    active = set(item_ids)
    day = today
    first_day = True
    steps = 0
    while active and steps <= max_lookback_days:
        planned_today = scheduled(day)
        done_today = done(day)
        broken = []
        for item_id in active:
            if item_id not in planned_today:
                continue
            if item_id in done_today:
                result[item_id] += 1
            elif not first_day:
                broken.append(item_id)
        for item_id in broken:
            active.discard(item_id)
        first_day = False
        day -= dt.timedelta(days=1)
        steps += 1
    return result


def week_progress(monday: dt.date, today: dt.date, item_ids_for, done) -> tuple[int, int]:
    """Прогресс недели по плановым пунктам: пара (сделано, всего).

    Будущие дни недели не учитываются.
    """
    total = 0
    completed = 0
    for i in range(7):
        day = monday + dt.timedelta(days=i)
        if day > today:
            break
        planned = item_ids_for(day)
        total += len(planned)
        done_today = done(day)
        completed += sum(1 for item_id in planned if item_id in done_today)
    return completed, total


def daily_ratios(monday: dt.date, today: dt.date, item_ids_for, done) -> list[float]:
    """Прогресс по каждому дню недели: доля выполнения 0..1 (для полосок)."""
    ratios = []
    for i in range(7):
        day = monday + dt.timedelta(days=i)
        if day > today:
            ratios.append(0.0)
            continue
        planned = item_ids_for(day)
        if not planned:
            ratios.append(0.0)
            continue
        done_today = done(day)
        ratios.append(sum(1 for item_id in planned if item_id in done_today) / len(planned))
    return ratios


def weak_spots(planned: dict, done: dict, limit: int = 3,
               min_planned: int = 3) -> list[tuple[str, float]]:
    """Самые проблемные пункты: наименьшая доля выполнения (0..1).

    Учитываются только пункты с не менее чем ``min_planned`` плановыми днями.
    Возвращает пары (id, доля), отсортированные по возрастанию доли.
    """
    entries = [
        (item_id, done.get(item_id, 0) / planned_count)
        for item_id, planned_count in planned.items()
        if planned_count >= min_planned
    ]
    entries.sort(key=lambda pair: (pair[1], pair[0]))
    return entries[:limit]

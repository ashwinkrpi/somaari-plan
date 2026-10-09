"""Assign due dates. Pure functions, no I/O, no AI (AI_PROMPTS.md section 4)."""
from datetime import date, timedelta


def _week_fill(priorities, start, per_day):
    """Dates for tasks in order: fill start..start+6 with per_day each, High no later than the
    third day when there is room, overflow continues into the following 7-day blocks."""
    per_day = max(1, int(per_day))
    n = len(priorities)
    used = {}
    out = [None] * n
    for i, p in enumerate(priorities):
        if p == "High":
            for d in range(3):
                if used.get(d, 0) < per_day:
                    out[i] = d
                    used[d] = used.get(d, 0) + 1
                    break
    d = 0
    for i in range(n):
        if out[i] is not None:
            continue
        while used.get(d, 0) >= per_day:
            d += 1
        out[i] = d
        used[d] = used.get(d, 0) + 1
    return [start + timedelta(days=o) for o in out]


def schedule(tasks, mode, anchor, per_day=4, today=None):
    """tasks: list of {priority, date: date|None}. Returns a list of dates, one per task.
    mode: week | day | in_text. anchor is a date (week start / the day). in_text: dated tasks keep their date;
    an undated task takes the date of the nearest dated task before it (carry forward, D-10); undated tasks
    before the first dated one follow the week rule from today."""
    if mode == "day":
        return [anchor] * len(tasks)
    if mode == "week":
        return _week_fill([t["priority"] for t in tasks], anchor, per_day)
    start = today or date.today()
    out, last = [], None
    for t in tasks:
        last = t.get("date") or last
        out.append(t.get("date") or last)
    undated = [i for i, d in enumerate(out) if d is None]
    filled = _week_fill([tasks[i]["priority"] for i in undated], start, per_day)
    for i, d in zip(undated, filled):
        out[i] = d
    return out

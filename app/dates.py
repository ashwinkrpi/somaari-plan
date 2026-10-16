"""Resolve Jev date parts into a calendar date. Pure code (AI_PROMPTS.md section 3)."""
from datetime import date, timedelta

from .ai.questions import MONTHS, WEEKDAYS

TIME_OF_DAY = {"morning": "10:00", "afternoon": "15:00", "evening": "18:00"}
PARTS = ("mode", "month", "day", "year", "anchor", "weekday", "week_offset", "time_of_day")


def _monday(d):
    return d - timedelta(days=d.weekday())


def _safe(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return None


def resolve(parts, today):
    """parts: {name: (value, confidence)}. today: date.
    Returns (date|None, 'HH:MM'|None, lowest confidence of the parts used)."""
    v = {k: parts.get(k, ("none", 1.0))[0] for k in PARTS}
    used = ["mode"]
    found = None
    if v["mode"] == "absolute" and v["month"] in MONTHS and v["day"].isdigit():
        used += ["month", "day", "year"]
        month, day = MONTHS.index(v["month"]) + 1, int(v["day"])
        if v["year"] == "next year":
            found = _safe(today.year + 1, month, day)
        elif v["year"] == "this year":
            found = _safe(today.year, month, day)
        else:
            found = _safe(today.year, month, day)
            if found and (today - found).days > 31:
                found = _safe(today.year + 1, month, day)
    elif v["mode"] == "relative":
        a = v["anchor"]
        used.append("anchor")
        if a == "today":
            found = today
        elif a == "tomorrow":
            found = today + timedelta(days=1)
        elif a == "day_after":
            found = today + timedelta(days=2)
        elif a == "next_week":
            found = _monday(today) + timedelta(days=7)
        elif a == "next_month_day" and v["day"].isdigit():
            used.append("day")
            y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
            found = _safe(y, m, int(v["day"]))
        elif a == "weekday" and v["weekday"] in WEEKDAYS:
            used += ["weekday", "week_offset"]
            wd = WEEKDAYS.index(v["weekday"])
            if v["week_offset"] == "current":
                found = _monday(today) + timedelta(days=wd)
            elif v["week_offset"] == "next":
                found = _monday(today) + timedelta(days=7 + wd)
            else:
                found = today + timedelta(days=(wd - today.weekday()) % 7)
    if found is None:
        return None, None, min(parts.get("mode", ("none", 1.0))[1], 1.0)
    clock = TIME_OF_DAY.get(v["time_of_day"])
    if clock:
        used.append("time_of_day")
    conf = min(parts.get(k, ("none", 1.0))[1] for k in used)
    return found, clock, conf

"""Rule-based quick-add parser. No AI. Finds a date and/or time, removes the matched span from the title."""
import re
from datetime import date, timedelta

from . import dates
from .ai.questions import MONTHS, WEEKDAYS

_MON = "|".join(m[:3] + "(?:" + m[3:] + ")?" if len(m) > 3 else m for m in MONTHS)
_MON = _MON.replace("sep(?:tember)?", "sep(?:t(?:ember)?)?")
_WD = "|".join(w[:3] + "(?:" + w[3:] + ")?" for w in WEEKDAYS)
_PRE = r"(?:\b(?:on|at|by|in the|this)\s+)?"
_ORD = r"(\d{1,2})(?:st|nd|rd|th)?"

DATE_RULES = [   # (name, regex), tried in order; first match wins
    ("nextmonth_day", re.compile(_PRE + r"\b" + _ORD + r"\s+(?:of\s+)?next\s+month\b", re.I)),
    ("day_month", re.compile(_PRE + r"\b" + _ORD + r"\s+(?:of\s+)?(" + _MON + r")\b", re.I)),
    ("month_day", re.compile(_PRE + r"\b(" + _MON + r")\.?\s+" + _ORD + r"\b", re.I)),
    ("day_after", re.compile(r"\bday after tomorrow\b", re.I)),
    ("tomorrow", re.compile(r"\btomorrow\b", re.I)),
    ("tonight", re.compile(r"\btonight\b", re.I)),
    ("today", re.compile(r"\btoday\b", re.I)),
    ("next_week", re.compile(r"\bnext week\b", re.I)),
    ("weekday", re.compile(_PRE + r"\b(next\s+)?(" + _WD + r")\b", re.I)),
]
TIME12 = re.compile(r"(?:\bat\s+)?\b(\d{1,2})(?::([0-5]\d))?\s*(am|pm)\b", re.I)
TIME24 = re.compile(r"(?:\bat\s+)?\b([01]?\d|2[0-3]):([0-5]\d)\b")
TOD = re.compile(r"\b(?:in the\s+)?(morning|afternoon|evening)\b", re.I)
MEETING = re.compile(r"\b(meeting|meet|sync|stand-?up|appointment|interview|catch-?up)\b", re.I)


def _cut(text, m):
    return text[:m.start()] + " " + text[m.end():]


def _tidy(t):
    t = re.sub(r"\s+", " ", t).strip(" ,;:-")
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r"\b(on|at|by|for)$", "", t, flags=re.I).strip(" ,;:-")
    return t


def is_meeting(text):
    return bool(MEETING.search(text))


def _clock(text):
    for rx in (TIME12, TIME24):
        m = rx.search(text)
        if not m:
            continue
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if rx is TIME12:
            if not 1 <= h <= 12:
                continue
            h = h % 12 + (12 if m.group(3).lower() == "pm" else 0)
        return f"{h:02d}:{mi:02d}", m
    return None, None


def find(text, today):
    """Rule-based date/time in text. Returns (date|None, 'HH:MM'|None, week: bool, rest_of_text).
    A time with no date gives date None (callers decide the default)."""
    rest = text.strip()
    found, week, tod_default = None, False, None
    for name, rx in DATE_RULES:
        m = rx.search(rest)
        if not m:
            continue
        if name == "nextmonth_day":
            p = {"mode": "relative", "anchor": "next_month_day", "day": m.group(1)}
        elif name in ("day_month", "month_day"):
            mon, day = (m.group(2), m.group(1)) if name == "day_month" else (m.group(1), m.group(2))
            full = next(x for x in MONTHS if x.startswith(mon.lower()[:3]))
            p = {"mode": "absolute", "month": full, "day": str(int(day)), "year": "none"}
        elif name == "weekday":
            wd = next(x for x in WEEKDAYS if x.startswith(m.group(2).lower()[:3]))
            p = {"mode": "relative", "anchor": "weekday", "weekday": wd,
                 "week_offset": "next" if m.group(1) else "none"}
        else:
            anchor = {"today": "today", "tonight": "today", "tomorrow": "tomorrow", "day_after": "day_after",
                      "next_week": "next_week"}[name]
            p = {"mode": "relative", "anchor": anchor}
            week = name == "next_week"
            tod_default = "20:00" if name == "tonight" else None
        d, _, _ = dates.resolve({k: (v, 1.0) for k, v in p.items()}, today)
        if d is None:
            continue
        found, rest = d, _cut(rest, m)
        break
    clock, m = _clock(rest)
    if m:
        rest = _cut(rest, m)
    else:
        m = TOD.search(rest)
        if m:
            clock = dates.TIME_OF_DAY[m.group(1).lower()]
            rest = _cut(rest, m)
    return found, clock or tod_default, week, rest


def parse(text, today):
    """Returns {title, date: date|None, time: 'HH:MM'|None, week: bool, type, matched: bool}."""
    found, clock, week, rest = find(text, today)
    if found is None and clock:
        found = today
    return {"title": _tidy(rest) or text.strip(), "date": found, "time": clock, "week": week,
            "type": "meeting" if is_meeting(text) else "task", "matched": found is not None}

"""Jev question sets. Bump VERSION on any wording change (it is part of the cache key)."""
VERSION = "1"

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
ANCHORS = ["today", "tomorrow", "day_after", "weekday", "next_week", "next_month_day"]
TIMES = ["morning", "afternoon", "evening"]


def _noul(text):
    return {"type": "noul", "instructions": text}


def _choice(text, options):
    return {"type": "choice", "instructions": text, "criteria": {o: o for o in options}}


def meeting_question(i):
    return _noul(f"Line {i} is a meeting, call or appointment with other people.")


def line_questions(lines):
    """Four questions per line: t_ (is a task), p_ (priority), m_ (meeting), d_ (names a date)."""
    qs = {}
    for ln in lines:
        i = ln["id"]
        qs["t_" + i] = _noul(f"Line {i} is an action the user must do, not a heading, note, example or explanation.")
        qs["p_" + i] = {"type": "choice", "instructions": f"Priority of line {i} in this plan.",
                        "criteria": {"High": "blocks later steps or is time-critical",
                                     "Medium": "normal work",
                                     "Low": "optional, nice-to-have or marked later"}}
        qs["m_" + i] = meeting_question(i)
        qs["d_" + i] = _noul(f"Line {i} names a specific date or day.")
    return qs


def line_state(lines, today):
    return {"today": today, "lines": [{"id": l["id"], "step": l["step"], "text": l["text"]} for l in lines]}


def date_questions(lines):
    qs = {}
    for ln in lines:
        i = ln["id"]
        qs["mode_" + i] = _choice(f"How does line {i} state its date?", ["absolute", "relative", "none"])
        qs["month_" + i] = _choice(f"Month named in line {i}.", MONTHS + ["none"])
        qs["day_" + i] = _choice(f"Day of the month named in line {i}.", [str(n) for n in range(1, 32)] + ["none"])
        qs["year_" + i] = _choice(f"Year named in line {i}.", ["this year", "next year", "none"])
        qs["anchor_" + i] = _choice(f"Relative date used in line {i}.", ANCHORS + ["none"])
        qs["weekday_" + i] = _choice(f"Weekday named in line {i}.", WEEKDAYS + ["none"])
        qs["week_offset_" + i] = _choice(f"Which week does line {i} mean?", ["current", "next", "none"])
        qs["time_of_day_" + i] = _choice(f"Time of day in line {i}.", TIMES + ["none"])
    return qs

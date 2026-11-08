"""Build the daily Telegram message (pure: no I/O). Plain text, so titles need no escaping."""
from datetime import date

LIMIT = 4096          # Telegram's maximum message length
PRIORITIES = ("High", "Medium", "Low")


def _day(d):
    d = d if isinstance(d, date) else date.fromisoformat(d)
    return f"{d:%a} {d.day} {d:%b}"


def _line(t, with_date=False):
    parts = [_day(t["due_date"])] if with_date else []
    if t.get("due_time"):
        parts.append(t["due_time"])
    parts.append(f"SP-{t['id']}")
    parts.append(t["title"])
    line = "• " + "  ".join(parts)
    return line + (f"  ({t['step']})" if t.get("step") else "")


def _sort_key(t):
    return (t.get("due_time") is None, t.get("due_time") or "", t["id"])


def build(today, tasks, overdue=()):
    """today: date; tasks: open tasks due today; overdue: open tasks due before today.
    Returns the message text, or None when there is nothing to send."""
    if not tasks and not overdue:
        return None
    n = len(tasks)
    lines = [f"Today · {_day(today)} · {n} open" if n else f"Today · {_day(today)} · nothing due"]
    for p in PRIORITIES:
        group = sorted((t for t in tasks if t.get("priority", "Medium") == p), key=_sort_key)
        if group:
            lines += ["", p] + [_line(t) for t in group]
    if overdue:
        lines += ["", f"Overdue ({len(overdue)})"]
        lines += [_line(t, with_date=True) for t in sorted(overdue, key=lambda t: (t["due_date"], t["id"]))]
    return _fit(lines)


def empty(today):
    return f"Today · {_day(today)} · nothing due. Enjoy the day."


def _fit(lines):
    text = "\n".join(lines)
    if len(text) <= LIMIT:
        return text
    kept = []
    for i, line in enumerate(lines):
        more = f"\n…and {len(lines) - i} more lines"
        if len("\n".join(kept + [line])) + len(more) > LIMIT:
            return "\n".join(kept) + more
        kept.append(line)
    return "\n".join(kept)

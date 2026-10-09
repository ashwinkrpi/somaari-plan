"""Seed 13 neutral demo tasks (a book swap plan, week of 5 Oct 2026). Run: python -m app.seed"""
import sys
from datetime import date, timedelta

from .db import connect, init_db, DEFAULT_DB

WEEK = date(2026, 10, 5)
GEN = "2026-10-05T06:58:00+05:30"
# (day offset, priority, created_at, step, title, closed_at)
DEMO = [
    (0, "Low", GEN, "Hall", "Check the hall calendar for free Saturdays", "2026-10-05T20:41:00+05:30"),
    (1, "Low", GEN, "Hall", "Ask whether the hall lends folding tables", "2026-10-06T07:38:00+05:30"),
    (1, "Low", GEN, "Hall", "Ask about the cleaning fee", "2026-10-06T07:52:00+05:30"),
    (1, "Medium", GEN, "Hall", "Compare room prices: small room, main hall, garden room", None),
    (1, "High", GEN, "Hall", "Book the hall and pay the deposit", None),
    (2, "Medium", "2026-09-29T21:05:00+05:30", "Flyer", "Write the flyer text and fill in the placeholders", None),
    (2, "High", GEN, "Flyer", "Fit the flyer on one A5 page", None),
    (3, "Medium", GEN, "Flyer", "Print a test copy and read it from across the room", None),
    (4, "Low", GEN, "Sign-up", "Set up the volunteer sign-up form", None),
    (4, "High", GEN, "Sign-up", "Ask a second volunteer to test the form", None),
    (4, "Medium", GEN, "Sign-up", "Post the flyer and pin the form link in the group", None),
    (5, "High", GEN, "Publicity", "Hand out flyers near the hall", None),
    (6, "High", GEN, "Day", "Set up tables and signs for each type of book", None),
]


def seed(path=None):
    """Insert demo tasks; skip if the tasks table already has rows. Returns count inserted."""
    init_db(path)
    conn = connect(path)
    try:
        if conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]:
            return 0
        for i, (day, pri, created, step, title, closed) in enumerate(DEMO):
            conn.execute(
                "INSERT INTO tasks (title, step, priority, due_date, sort_order, created_at, closed_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (title, step, pri, (WEEK + timedelta(days=day)).isoformat(), i, created, closed),
            )
        conn.commit()
        return len(DEMO)
    finally:
        conn.close()


if __name__ == "__main__":
    n = seed(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB)
    print(f"Seeded {n} tasks." if n else "Tasks already present; nothing seeded.")

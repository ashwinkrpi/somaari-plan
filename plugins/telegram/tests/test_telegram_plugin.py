"""Telegram plugin tests. Run with the plugin installed: `uv sync --extra telegram`, then
`uv run pytest -q plugins/telegram/tests`. Skipped when the plugin isn't installed. No network."""
import io
import json
import urllib.error
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

tg = pytest.importorskip("somaari_plan_telegram")
from somaari_plan_telegram import message, schedule, telegram  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
DAY = date(2026, 11, 24)


def task(i, title, prio="Medium", tm=None, step=None, d="2026-11-24"):
    return {"id": i, "title": title, "priority": prio, "due_time": tm, "step": step, "due_date": d}


# ---- message (pure) ----
def test_message_groups_by_priority_and_time():
    text = message.build(DAY, [task(3, "Low one", "Low"), task(1, "Post on X", "High", "21:00", "social"),
                               task(2, "Early", "High", "09:00"), task(4, "Mid")],
                         [task(9, "Late", d="2026-11-20")])
    assert text.splitlines() == [
        "Today · Tue 24 Nov · 4 open", "",
        "High", "• 09:00  SP-2  Early", "• 21:00  SP-1  Post on X  (social)", "",
        "Medium", "• SP-4  Mid", "",
        "Low", "• SP-3  Low one", "",
        "Overdue (1)", "• Fri 20 Nov  SP-9  Late"]


def test_message_none_when_nothing_and_overdue_only():
    assert message.build(DAY, []) is None
    assert message.build(DAY, [], [task(9, "x", d="2026-11-01")]).startswith("Today · Tue 24 Nov · nothing due")


def test_message_capped_at_telegram_limit():
    text = message.build(DAY, [task(i, "t" * 90) for i in range(200)])
    assert len(text) <= message.LIMIT and text.rsplit("\n", 1)[1].startswith("…and ")


# ---- schedule (pure) ----
def at(h, m):
    return datetime(2026, 11, 24, h, m, tzinfo=IST)


@pytest.mark.parametrize("now, last, expect", [
    (at(7, 29), None, False),          # before send time
    (at(7, 30), None, True),           # at send time
    (at(9, 0), None, True),            # app was down: catch up
    (at(10, 31), None, False),         # past the 3 h grace: skip today
    (at(7, 31), "2026-11-24", False),  # already sent today
    (at(7, 31), "2026-11-23", True),
])
def test_due(now, last, expect):
    assert schedule.due(now, "07:30", last) is expect


class Ctx:
    def __init__(self, tmp_path, settings, tasks=(), overdue=()):
        self.data_dir, self._s, self._t, self._o, self.logs = tmp_path, settings, list(tasks), list(overdue), []
        self.name = "telegram"

    def settings(self):
        return {**tg.plugin.defaults, **self._s}

    def now(self):
        return at(7, 45)

    def today(self):
        return DAY

    def tasks(self, f=None, t=None, open_only=True):
        return self._t if f else self._o

    def log(self, m):
        self.logs.append(m)


def test_tick_sends_once_per_day(tmp_path):
    sent = []
    ctx = Ctx(tmp_path, {"enabled": True})
    assert schedule.tick(ctx, sent.append) is True
    assert schedule.tick(ctx, sent.append) is False       # state.json says sent today
    assert len(sent) == 1 and schedule.State(tmp_path).last_sent() == "2026-11-24"


def test_tick_off_when_disabled(tmp_path):
    assert schedule.tick(Ctx(tmp_path, {"enabled": False}), lambda c: 1 / 0) is False


# ---- plugin ----
def test_validate():
    p = tg.plugin
    assert p.validate({"send_time": "7:05"})["send_time"] == "07:05"
    for bad in ({"send_time": "25:00"}, {"send_time": ""}, {"enabled": "yes"}):
        with pytest.raises(ValueError):
            p.validate(bad)


def test_text_respects_overdue_and_empty_settings(tmp_path):
    p = tg.plugin
    od = [task(9, "old", d="2026-11-20")]
    assert "Overdue" in p.text_for_today(Ctx(tmp_path, {}, overdue=od))
    assert p.text_for_today(Ctx(tmp_path, {"include_overdue": False}, overdue=od)) is None
    assert "nothing due" in p.text_for_today(Ctx(tmp_path, {"include_overdue": False, "send_when_empty": True}))


def test_status_never_shows_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:SECRET")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    lines = " ".join(tg.plugin.status(Ctx(tmp_path, {})))
    assert "SECRET" not in lines and "Bot token: set" in lines and "Chat id: missing" in lines


# ---- telegram (no network: fake opener) ----
def test_send_posts_json(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:SECRET")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    seen = {}

    def opener(req, timeout):
        seen["url"], seen["body"] = req.full_url, json.loads(req.data)
        return io.BytesIO(b'{"ok": true}')

    telegram.send("hi", opener=opener)
    assert seen["url"].endswith("/bot123:SECRET/sendMessage") and seen["body"]["chat_id"] == "42"


def test_send_errors_hide_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:SECRET")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")

    def unauthorized(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"description":"Unauthorized"}'))

    def offline(req, timeout):
        raise urllib.error.URLError(OSError("no route to " + req.full_url))

    for opener in (unauthorized, offline):
        with pytest.raises(telegram.SendError) as e:
            telegram.send("hi", opener=opener)
        assert "SECRET" not in str(e.value)


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    with pytest.raises(telegram.SendError, match="TELEGRAM_BOT_TOKEN not set"):
        telegram.send("hi")

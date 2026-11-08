"""When to send (pure `due`) and the background service that does it."""
import json
import threading
from datetime import datetime, time, timedelta

CHECK_EVERY_S = 30
GRACE = timedelta(hours=3)     # app down at send time: catch up for this long, then skip the day


def parse_time(s):
    h, m = s.split(":")
    return time(int(h), int(m))


def due(now, send_time, last_sent, grace=GRACE):
    """True when today's message should go now. now: aware datetime; send_time: 'HH:MM';
    last_sent: ISO date of the last daily send or None."""
    target = datetime.combine(now.date(), parse_time(send_time), tzinfo=now.tzinfo)
    return last_sent != now.date().isoformat() and target <= now < target + grace


class State:
    """data/plugins/telegram/state.json: {"last_sent": "YYYY-MM-DD"}, so a restart never sends twice."""

    def __init__(self, folder):
        self.path = folder / "state.json"

    def last_sent(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("last_sent")
        except (OSError, ValueError):
            return None

    def mark(self, day):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"last_sent": day}), encoding="utf-8")
        tmp.replace(self.path)


def tick(ctx, send_today):
    """One check. Settings are re-read every time, so changes in Settings apply without a restart."""
    s = ctx.settings()
    if not s.get("enabled"):
        return False
    state, now = State(ctx.data_dir), ctx.now()
    if not due(now, s["send_time"], state.last_sent()):
        return False
    state.mark(now.date().isoformat())   # mark first: a failing send is logged once, not retried all day
    send_today(ctx)
    return True


def start(ctx, send_today):
    stop = threading.Event()

    def loop():
        while not stop.wait(CHECK_EVERY_S):
            try:
                tick(ctx, send_today)
            except Exception as e:  # noqa: BLE001 - keep the service alive; never log the token
                ctx.log(f"daily send failed: {e}")

    threading.Thread(target=loop, name="telegram-daily", daemon=True).start()
    return stop

"""somaari-plan Telegram plugin: today's tasks, sent once a day at the time set in Settings.

Plugin API v1 (somaari-plan docs/PLUGINS_PLAN.md). Secrets come from .env:
TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID. Nothing here is imported by the core by name.
"""
import os
from datetime import timedelta

from . import message, schedule, telegram

__version__ = "0.1.0"


def _plugin_error():
    try:
        from app.plugins import PluginError   # the host app; present whenever this plugin is loaded by it
        return PluginError
    except ImportError:  # pragma: no cover - only when used outside somaari-plan
        return RuntimeError


class TelegramPlugin:
    api_version = 1
    name = "telegram"
    title = "Telegram"
    description = ("Sends today's open tasks to your Telegram chat once a day. The bot token and "
                   "chat id live in .env (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).")
    defaults = {"enabled": False, "send_time": "07:30", "include_overdue": True, "send_when_empty": False}
    fields = [
        {"key": "enabled", "label": "Send today's tasks every day", "type": "bool"},
        {"key": "send_time", "label": "Send at (IST)", "type": "time",
         "hint": "If the app is off at this time, it sends when it starts, up to 3 hours late."},
        {"key": "include_overdue", "label": "Include overdue open tasks", "type": "bool"},
        {"key": "send_when_empty", "label": "Send a message on days with nothing due", "type": "bool"},
    ]
    actions = [{"id": "test", "label": "Send test message"}, {"id": "today", "label": "Send today's tasks now"}]

    def validate(self, values):
        out = dict(self.defaults)
        for k in ("enabled", "include_overdue", "send_when_empty"):
            if not isinstance(values.get(k, out[k]), bool):
                raise ValueError(f"{k} must be true or false.")
            out[k] = values.get(k, out[k])
        t = values.get("send_time", out["send_time"])
        try:
            parsed = schedule.parse_time(t)
        except (ValueError, AttributeError):
            raise ValueError("Send at must be a time such as 07:30.") from None
        out["send_time"] = f"{parsed:%H:%M}"
        return out

    def status(self, ctx):
        token = bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip())
        chat = bool(os.environ.get("TELEGRAM_CHAT_ID", "").strip())
        last = schedule.State(ctx.data_dir).last_sent()
        return [f"Bot token: {'set' if token else 'missing'} · Chat id: {'set' if chat else 'missing'}",
                f"Last daily message: {last or 'never'}"]

    def text_for_today(self, ctx):
        s, today = ctx.settings(), ctx.today()
        tasks = ctx.tasks(today, today)
        overdue = ctx.tasks(None, today - timedelta(days=1)) if s["include_overdue"] else []
        text = message.build(today, tasks, overdue)
        if text is None and s["send_when_empty"]:
            text = message.empty(today)
        return text

    def send_today(self, ctx):
        text = self.text_for_today(ctx)
        if text is None:
            ctx.log("nothing due today; no message sent")
            return False
        telegram.send(text)
        ctx.log("daily message sent")
        return True

    def run_action(self, ctx, action):
        try:
            if action == "test":
                telegram.send("somaari-plan: test message. Telegram is set up.")
                return "Test message sent. Check Telegram."
            text = self.text_for_today(ctx) or message.empty(ctx.today())
            telegram.send(text)
            return "Today's tasks sent. This doesn't count as the daily message."
        except telegram.SendError as e:
            raise _plugin_error()(str(e)) from None

    def start(self, ctx):
        schedule.start(ctx, self.send_today)


plugin = TelegramPlugin()

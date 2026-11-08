"""Telegram Bot API over stdlib urllib. The token is part of the URL, so errors never include it."""
import json
import os
import urllib.error
import urllib.request

API = "https://api.telegram.org"
TIMEOUT_S = 15


class SendError(Exception):
    pass


def credentials():
    """(token, chat_id) from the environment (.env), or raise SendError naming what is missing."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    missing = [k for k, v in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat)) if not v]
    if missing:
        raise SendError(f"{' and '.join(missing)} not set in .env (restart the app after editing it).")
    return token, chat


def send(text, opener=urllib.request.urlopen):
    token, chat = credentials()
    body = json.dumps({"chat_id": chat, "text": text, "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(f"{API}/bot{token}/sendMessage", body, {"Content-Type": "application/json"})
    try:
        with opener(req, timeout=TIMEOUT_S) as r:
            reply = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            desc = json.load(e).get("description", "")
        except Exception:  # noqa: BLE001
            desc = ""
        hint = {401: "the bot token is wrong", 400: "check TELEGRAM_CHAT_ID, and send /start to the bot once",
                403: "the bot can't message this chat: send /start to the bot first"}.get(e.code, "")
        raise SendError(f"Telegram said {e.code}{': ' + desc if desc else ''}{' (' + hint + ')' if hint else ''}.") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise SendError(f"Could not reach Telegram ({type(reason).__name__}). Is the Pi online?") from None
    if not reply.get("ok"):
        raise SendError("Telegram did not accept the message.")

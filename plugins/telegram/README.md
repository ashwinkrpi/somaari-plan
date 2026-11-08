# somaari-plan-telegram

Optional somaari-plan plugin that sends **today's open tasks** to your Telegram chat once a day, at the time you set in **Settings → Telegram**.

It isn't part of the main install. somaari-plan runs the same without it.

- **No extra libraries:** it uses only the Python standard library.
- **No changes to your tasks:** it only reads them.

## Setup

1. **Create a bot.** In Telegram, message **@BotFather**, send `/newbot`, and follow the prompts. Copy the **bot token** (it looks like `123456789:AA…`).

2. **Get your chat id.**
   1. Open a chat with your new bot and press **Start** (or send any message).
   2. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser.
   3. Find `"chat":{"id":123456789` and copy the number. A group chat id starts with `-`.

3. **Add both to `.env`** in the somaari-plan folder, and keep the file `chmod 600`:
   ```sh
   TELEGRAM_BOT_TOKEN=123456789:AA...
   TELEGRAM_CHAT_ID=123456789
   ```

4. **Install the plugin and restart the app:**
   ```sh
   cd ~/somaari-plan
   uv sync --extra telegram
   systemctl --user restart somaari-plan
   journalctl --user -u somaari-plan -n 5    # shows "plugin telegram loaded"
   ```

5. **Turn it on.** Open **Settings → Telegram**:
   1. Press **Send test message**. A message should arrive.
   2. Tick **Send today's tasks every day**, pick a time, and press **Save Telegram**.

## Settings

| Setting | Default | What it does |
|---|---|---|
| Send today's tasks every day | off | Turns the daily message on |
| Send at (IST) | 07:30 | When to send. If the app is off at that time, it sends when it starts, up to 3 hours late. After that, it skips the day. |
| Include overdue open tasks | on | Adds an "Overdue (N)" list |
| Send a message on days with nothing due | off | Otherwise, nothing is sent on an empty day |

Settings are saved in `config.toml` under `[plugins.telegram]`. The token and chat id are only read from `.env`. They're never saved anywhere else, shown, or logged. `data/plugins/telegram/state.json` stores the date of the last daily message, so a restart never sends a second one.

## Example message

```
Today · Tue 24 Nov · 3 open

High
• 21:00  SP-142  Post on X #1: Launch + pin it  (somaari-disk social)

Medium
• SP-150  Review the backup job

Overdue (1)
• Mon 23 Nov  SP-141  Add GitHub link to Instagram bio  (somaari-disk social)
```

## Updating and removing
- **Updating:** run `uv sync --extra telegram`, not plain `uv sync`.
- **Removing:** plain `uv sync` removes the plugin. The app keeps working, and the `[plugins.telegram]` section in `config.toml` is ignored. To clean up completely, delete that section and `data/plugins/telegram/`.

## Tests
```sh
uv sync --extra telegram
uv run pytest -q plugins/telegram/tests
```

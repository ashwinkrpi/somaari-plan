# Stage 11 · Plugins and Telegram reminders (D-21)

Goal: optional features install separately and never add weight to the main app. The first plugin
sends today's tasks to Telegram every day at a time set in Settings.
Status: built, tested by the owner and merged to `main` (2026-11-08).

## The requirement
- **No Telegram unless you ask for it.** `uv sync` installs the same files as before, and the app runs the same without the plugin.
- **Opt in with two settings:** turn it on in Settings, and put the keys in `.env`.
- **Self-contained:** the plugin's code, setup and docs live together and install with one command.

## Options considered (2026)

| Option | How it works | Verdict |
|---|---|---|
| A. Feature flag in the core | Telegram code ships in `app/`, behind `[telegram] enabled` | No: every install carries the code, which is the bloat to avoid. |
| B. Extra with optional deps (`somaari-plan[telegram]`) | The code still lives in `app/`; the extra only adds deps | No: Telegram needs no third-party deps, so the extra would add nothing, and the code is still in the core. |
| **C. Separate package + entry points** | The plugin is its own distribution and advertises itself in the `somaari_plan.plugins` entry-point group. The core finds whatever is installed. | **Chosen.** It's the standard Python pattern (pytest, Datasette, MkDocs, Flask CLI): zero cost when absent, and it can be installed and removed on its own. |
| D. External script + systemd timer | A separate script calls `/api/tasks` and sends to Telegram | No: the send time couldn't be set in Settings, and it needs a second unit to manage. Still a good fit for features that need no UI. |

How C is installed with uv: the root `pyproject.toml` lists the plugin as an **optional extra** whose
source is the local folder `plugins/telegram`:

```toml
[project.optional-dependencies]
telegram = ["somaari-plan-telegram"]
[tool.uv.sources]
somaari-plan-telegram = { path = "plugins/telegram", editable = true }
```

- `uv sync` installs the core only, exactly as before.
- `uv sync --extra telegram` adds the plugin.
- The plugin's code is in the repo but **not** in the core wheel (`packages.find` includes `app*` only).
- It can move to its own repo later without changing the core.

## Plugin API v1 (`app/plugins.py`)
A plugin is any object loaded from the `somaari_plan.plugins` entry point. It has these parts:

| Attribute | Purpose |
|---|---|
| `name`, `title`, `description` | Id (`telegram`), and the label and text shown in Settings |
| `api_version = 1` | The core skips plugins built for a different API version |
| `fields` | Settings form: `{key, label, type: bool\|time\|text\|number, hint}`. The core draws it generically. |
| `defaults`, `validate(values)` | Settings stored in `config.toml` under `[plugins.<name>]`. `validate` raises `ValueError` with a user-facing message. |
| `actions` | Buttons: `{id, label}`. `run_action(ctx, id)` returns a message or raises `PluginError`. |
| `status(ctx)` | Read-only lines for Settings, such as "Bot token: set". Never the secret itself. |
| `start(ctx)` (optional) | Starts a background service (daemon thread). Called only by the real server, never in tests or by the `--dev` reloader parent. |

`Context` (what a plugin may use):
- `settings()` and `save_settings()`
- `tasks(from_date, to_date, open_only)`
- `today()` and `now()` (IST)
- `data_dir` (`data/plugins/<name>/`, for state files)
- `log()` (to stderr, which ends up in the journal)

Plugins don't touch the DB or `config.toml` directly, so the core can change its internals.

Core endpoints:
- `GET /api/plugins`: installed plugins, with their fields, values, actions and status.
- `PUT /api/plugins/<name>`: save settings.
- `POST /api/plugins/<name>/actions/<id>`: run a button.

With no plugin installed, Settings shows one line: "No plugins installed", with a pointer to GUIDE → Plugins.

Principle change: "No background workers" becomes "No background workers in the core. A plugin
may run one daemon thread, started only by the server process."

## Telegram plugin (`plugins/telegram`, package `somaari_plan_telegram`)
- **Secrets in `.env`:** `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. They're never stored in `config.toml`, never shown, and never logged.
- **Settings `[plugins.telegram]`:**

  | Setting | Default |
  |---|---|
  | `enabled` | false |
  | `send_time` (HH:MM, IST) | 07:30 |
  | `include_overdue` | true |
  | `send_when_empty` | false |

- **Message:** plain text, no Telegram formatting, so task titles need no escaping.
  - Header: "Today · Tue 24 Nov · 3 open".
  - Tasks are grouped High / Medium / Low, with time first, then SP-key, title and step.
  - Then an "Overdue (N)" section.
  - It's capped at Telegram's 4096 characters, ending "…and N more".
- **Schedule:**
  - A daemon thread checks every 30 s, re-reading the settings each time, so changes apply without a restart.
  - It sends once a day when now ≥ `send_time`.
  - If the app was down at send time, it catches up for up to 3 hours.
  - `data/plugins/telegram/state.json` keeps `last_sent`, so a restart doesn't send twice.
- **Buttons:**
  - **Send test message** checks the token and chat id.
  - **Send today's tasks now** sends right away, and doesn't count as the daily send.
- **HTTP:** stdlib `urllib` POST to `api.telegram.org/bot<token>/sendMessage` with a 15 s timeout. Errors are shown as plain text, never with the URL, because the URL holds the token.

## Work items

| # | Item | Est. |
|---|---|---|
| 11.1 | `app/plugins.py` (discover, Context, API v1), `routes/plugins.py`, `config.load_plugin`/`save_plugin`, start services in `__main__` | 0.5 d |
| 11.2 | Settings: generic Plugins section (fields, Save, actions, status), "No plugins installed" line, time-input CSS | 0.5 d |
| 11.3 | `plugins/telegram`: pyproject + entry point, `message.py` (pure), `schedule.py` (pure `due()` + service), `telegram.py` (urllib), README | 0.5 d |
| 11.4 | Tests: core (`tests/test_plugins.py`, fake plugin, no plugin installed); plugin (`plugins/telegram/tests`, skipped unless installed) | 0.5 d |
| 11.5 | Docs: GUIDE → Plugins and Telegram setup, ARCHITECTURE (tree, API, principle), README feature line, CHANGELOG, STATUS | 0.25 d |

## Manual checks (to do)
- [ ] `uv sync` (no extra) → Settings shows "No plugins installed", and the app works as before.
- [ ] `uv sync --extra telegram`, then fill in `.env` and restart → the Telegram section appears, and **Send test message** arrives.
- [ ] Set the send time 2 minutes ahead → exactly one message arrives. Restart → no second message.
- [ ] Settings at 380 px, in all themes, keyboard only.
- [ ] `uv sync` again (without the extra) removes the plugin → the app still starts, and `[plugins.telegram]` in `config.toml` is ignored.

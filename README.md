# somaari-plan

A small planner web app for a Raspberry Pi. Upload a Markdown plan, paste loose text, or type a quick line, and it turns them into dated tasks you can see by day, week and priority.

It is built for one person on a home network: Flask + Waitress + SQLite, plain HTML/CSS/JS, no build step, idle under 80 MB of RAM on a Pi 5.

| Light | Dark |
|---|---|
| ![Light theme](docs/screenshots/light.png) | ![Dark theme](docs/screenshots/dark.png) |

## What it does

- **New plan:** upload a `.md` plan or paste text. You get an editable preview (titles, dates, priority, step) and a list of skipped lines before anything is saved.
- **Quick add:** type a line like `call the plumber friday` and get a task card to check and add.
- **Today, Calendar, Dashboard, Done:** today's list, day/week/month views, a 7-day board by priority (drag or tap to move), and a searchable list of finished tasks you can reopen.
- **Backup:** JSON export and add-only import from Settings.
- Light and dark themes, keyboard friendly, works at phone width.

Code does the parsing, titles, dates and scheduling. AI is optional and only answers small typed questions (see [AI setup](#ai-setup)).

## Install on a Raspberry Pi

Needs Python 3.11+ (Raspberry Pi OS Bookworm ships it) and git.

```sh
git clone https://github.com/ashwinkrpi/somaari-plan.git
cd somaari-plan
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.example.toml config.toml
cp .env.example .env && chmod 600 .env
.venv/bin/python -m app
```

Open `http://<pi-address>:8710` from any device on your network. Host and port come from `[server]` in `config.toml` (or `SOMAARI_HOST` / `SOMAARI_PORT` in `.env`, or `--host` / `--port`). Use `host = "127.0.0.1"` to keep it on the Pi only.

Optional demo data: `.venv/bin/python -m app.seed`.

### Run as a service

`~/.config/systemd/user/somaari-plan.service`:

```ini
[Unit]
Description=somaari-plan

[Service]
WorkingDirectory=%h/somaari-plan
EnvironmentFile=%h/somaari-plan/.env
ExecStart=%h/somaari-plan/.venv/bin/python -m app
Restart=on-failure

[Install]
WantedBy=default.target
```

```sh
systemctl --user daemon-reload
systemctl --user enable --now somaari-plan
loginctl enable-linger "$USER"   # keep it running after logout
```

Adjust the paths if you cloned somewhere else. More notes (backups, logs, changing the port) are in [docs/DEPLOY_PI.md](docs/DEPLOY_PI.md).

Your data lives in `data/somaari.db` (SQLite). It is not committed to git.

## AI setup

Put keys in `.env` only; they are never shown in the UI or written to logs. Pick a mode in `config.toml` under `[ai]` or on the Settings page:

| `mode` | Needs | What happens |
|---|---|---|
| `jev` (default) | `TYPESAFE_API_KEY` | [TypeSafe](https://typesafe.ai) Jev answers typed questions (is this line a task, which date parts). An LLM from `generate_chain` only rewrites loose prose into titles, if `rewrite_prose = true`. |
| `llm` | a key for a provider in `generate_chain` | For users without a TypeSafe key. The LLM does the full extraction. |
| `off` | nothing | Code parsing only; every line becomes a draft task for you to review. |

`generate_chain` providers:

| Provider | Key | Notes |
|---|---|---|
| `openrouter_free` | `OPENROUTER_API_KEY` | free, rate-limited; upstream may log prompts, so only the prose sentences are sent |
| `gemini_api` | `GEMINI_API_KEY` | free tier available |
| `gemini_cli` | none (CLI login) | needs the `gemini` CLI installed and logged in for the same user |

Set `generate_chain = []` to never call an LLM.

**Subscription vs API:** a chat subscription (Gemini app, ChatGPT, Claude) does not include API access. A Gemini subscription works here only through `gemini_cli`; everything else needs an API key.

If Jev fails, the app falls back to `llm` (if a chain is set) or `off`, and the page tells you. Answers are cached, so uploading the same plan again makes no AI calls.

Check a provider from the Pi: `.venv/bin/python -m app.ai.smoke jev` or `... smoke openrouter_free`.

## Development

```sh
.venv/bin/python -m app --dev      # Flask debug server
.venv/bin/python -m pytest -q      # tests use mocks; no real AI calls
```

Design and build docs are in [docs/](docs/).

## Licence

MIT, see [LICENSE](LICENSE). The bundled Bricolage Grotesque font is under the SIL Open Font License ([web/fonts/OFL.txt](web/fonts/OFL.txt)).

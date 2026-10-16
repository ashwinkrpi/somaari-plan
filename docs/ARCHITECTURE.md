# Architecture

## Tree
```
app/
  __init__.py        create_app(), blueprint registration
  __main__.py        entry point: resolves host/port, starts Waitress (or Flask with --dev)
  config.py          loads config.toml + .env
  db.py              sqlite connect, migrate
  schema.sql
  seed.py            13 hand-written neutral demo tasks (Stage 1)
  routes/            tasks.py · ingest.py · quick.py · ai.py · settings.py · export.py · about.py (GET /api/about)
  stamp.py           writes git-ignored _build_info.py (commit, UTC date) for About
  scheduler.py       assigns due dates (pure functions, no I/O)
  ingest/mdparse.py  markdown → steps + candidate lines (no AI)
  ingest/pipeline.py candidates → Jev scores / LLM fallback → draft tasks (ai_cache)
  dates.py           resolves Jev date parts → date (pure)
  quickparse.py      rule-based date/time parser (no AI)
  ai/
    router.py        decide() / generate(), cache, fallback, logging
    questions.py     Jev question sets (VERSION constant)
    jev.py           TypeSafe HTTP client (urllib)
    smoke.py         manual real-provider smoke test (`python -m app.ai.smoke`)
    providers/       mock.py (mock_jev, mock_llm) · remote.py (openrouter_free, gemini_api, gemini_cli)
  prompts/           rewrite.txt · extract.txt (LLM fallback only)
web/
  index.html
  css/app.css
  js/  app.js (router) · store.js (shared task state) · dom.js · dates.js · today.js · calendar.js
       dashboard.js · done.js · editor.js (inline task editor) · datefmt.js (date format + date field) · plan.js · quick.js · steps.js (step suggestions) · settings.js
  fonts/             BricolageGrotesque-var.woff2 + OFL.txt (self-hosted, no Google Fonts call)
tests/
  fixtures/          example-plan.md · .expected.json · jev/<set>_<sha8>.json
design/              canvas exports (reference only, not served)
data/                somaari.db (gitignored)
```

## Server config
Settings, defaults and precedence (CLI → env → `config.toml` → defaults): [GUIDE.md → Server](GUIDE.md#server). `app/config.py` implements them.
- Validate: port 1024–65535. If the port is busy, exit with a clear message naming the port and how to change it; never pick another port silently.
- Log the final URL at start-up, e.g. `somaari-plan on http://0.0.0.0:8710`.
- The UI uses relative URLs only (`/api/...`), so a port change needs no frontend edit.
- Settings page shows host/port read-only, with a note that changes need a restart.

## API (JSON)
| Method | Path | Notes |
|---|---|---|
| GET | /api/tasks?from=YYYY-MM-DD&to=YYYY-MM-DD | due_date in range |
| POST | /api/tasks | single task |
| PATCH | /api/tasks/:id | title, step, due_date, due_time, priority, closed (bool); reopening moves a past due date to today; a due_date change is logged in task_moves |
| DELETE | /api/tasks/:id | |
| GET | /api/done?q=&limit= | done tasks, newest closed first; q matches title or step (Done page) |
| GET | /api/moved?from=&to= | `{moved: N}`: tasks once due in the range that now sit outside it (Dashboard "Last week … moved", D-07) |
| GET | /api/steps | distinct steps in use, most recent first (step suggestions) |
| POST | /api/ingest/preview | multipart files and/or text + schedule options → draft tasks |
| POST | /api/ingest/commit | draft tasks → saved, dates assigned |
| GET | /api/quick | pending cards (not yet added), oldest first; `?all=1` includes added ones |
| DELETE | /api/quick/:id · /api/quick | discard one pending card · all pending cards (added ones stay; 409 for an added card) |
| POST | /api/quick | text → parsed card (local first, AI fallback) |
| POST | /api/quick/:id/add | commit the card as a task (optional step) |
| GET | /api/ai/status | chain + availability, no secrets |
| POST | /api/ai/test | one tiny call to `jev` or a named generate provider |
| GET/PUT | /api/settings | `[ai]` mode, model, chain, thresholds; `[ui]` date_format (writes config.toml; never keys); `[server]` read-only |
| GET | /api/export · POST /api/import | JSON backup; import is add-only (D-08) |

Not built: `GET /api/summary` (the Dashboard computes its summary in `dashboard.js` from `/api/tasks`) and `GET/DELETE /api/sources`.

## Principles
- Server renders nothing but `index.html`; the UI fetches JSON.
- All dates are local (Asia/Kolkata); store ISO strings.
- AI is optional at runtime: tasks, calendar and board work with AI off.
- No background workers. AI calls are synchronous with a 60 s timeout; the UI shows a spinner.

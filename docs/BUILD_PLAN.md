# Build plan

Work one stage per session. At the start, read only the docs listed for that stage.
A stage is done when its "Done when" checks pass, docs/STATUS.md is updated, and no open entry in docs/DECISIONS.md blocks it.

## Stage 0 — Repo and skeleton
Read: ARCHITECTURE.md
- Repo at `~/code/ai-projects/somaari-plan`. Creating the private GitHub repo and pushing is Ashwin Koppam Raghavendra's (manual check).
- Create the folder tree from ARCHITECTURE.md, `requirements.txt` (flask, waitress, pytest), `.gitignore` (`.venv/ data/ .env config.toml __pycache__/ *.zip .claude/settings.local.json`), `.env.example`, `config.example.toml`.
- `create_app()` serves `web/index.html` and `GET /api/health`.
- `python -m app` reads host/port per ARCHITECTURE.md → Server config (CLI > env > config.toml > default).
Done when: `/api/health` returns `{"ok": true}` on the Pi; the app starts on a port set via config, env and `--port`; a busy port gives a clear error; pytest passes.

## Stage 1 — Data layer and task API
Read: DATA_MODEL.md, ARCHITECTURE.md (API section)
- `app/db.py`: connection helper, migrations from `app/schema.sql`, WAL mode.
- Task CRUD routes. Closing a task sets `closed_at`; reopening clears it.
- Seed script (`app/seed.py`): 13 neutral demo tasks (book swap, week of 5 Oct 2026), same shape as the canvas mockup. Hand-written data; the example plan file is `tests/fixtures/example-plan.md`.
Done when: CRUD tests pass; created/closed timestamps verified.

## Stage 2 — UI shell and themes
Read: UI_SPEC.md (Tokens, Shell)
- `web/index.html`, `web/css/app.css` (light + dark tokens), `web/js/app.js` hash router.
- Left panel: Today, Calendar, Dashboard, New plan ↗. One page at a time.
- Theme: follows system; a manual toggle stored in localStorage.
Done when: all four routes render empty states in both themes; works at 380 px wide.

## Stage 3 — Today and Calendar
Read: UI_SPEC.md (Today, Calendar)
- Today: list sorted by priority, Mark done toggle, created/closed shown.
- Calendar: Day / Week / Month views from `GET /api/tasks?from=&to=`.
Done when: ticking a task updates Today, Calendar and the left-panel count without reload.

## Stage 4 — Dashboard board
Read: UI_SPEC.md (Dashboard)
- Summary band: this week planned/done, progress by step, last week done.
- Board: day columns × priority lanes. Native HTML5 drag and drop + tap "Move / Move here" fallback.
- Drop → `PATCH /api/tasks/:id {due_date, priority}`.
- Week navigation (prev/next week).
Done when: drag and tap-move both persist after reload; summary numbers are correct.

## Stage 5 — AI layer: Jev first
Read: AI_PROVIDERS.md, TESTING.md
- The TypeSafe Claude Code skill is already installed; load it for Jev API details.
- `router.py`: `decide()` → `jev.py` (urllib, batching, 429 retry, cache); `generate()` → chain.
- Providers: `jev`, `mock_jev`, `openrouter_free`, `mock_llm`; then `gemini_cli`, `gemini_api` (`ollama` off). No Claude providers.
- `config.toml` + `.env`; modes `jev | llm | off`; thresholds; `GET /api/ai/status` (never keys).
- Settings page (not in canvas): mode, Jev model, generate chain order, thresholds, test buttons; `GET/PUT /api/settings`.
Done when: mock tests pass; one real Jev call and one `openrouter_free` call work on the Pi; Jev down → falls back as configured.

## Stage 6 — Ingest: files and pasted text
Read: AI_PROMPTS.md (§1–4, §6), DATA_MODEL.md (sources)
- Upload many .md files; each has its own schedule: week starting <date> or "dates inside the file".
- Pasted text: dates in text / week starting / single day; tasks per day.
- `mdparse.py` (code) → Jev line decisions → Jev date parts for dated lines → prose rewrite only if needed.
- Flow: upload → `POST /api/ingest/preview` → editable preview (flagged rows highlighted, skipped lines collapsed) → `POST /api/ingest/commit` → `scheduler.py` assigns dates.
- Tune thresholds on 3–4 of your real plan files; propose values in D-03 (Ashwin Koppam Raghavendra decides), then pin the Jev version.
Done when: `tests/fixtures/example-plan.md` gives the 21 expected candidates, Jev keeps the real tasks (Ashwin Koppam Raghavendra reviews the list), no LLM call is made, and re-upload makes zero AI calls.

## Stage 7 — Quick add
Read: AI_PROMPTS.md (Quick add)
- Local rule parser first (`app/quickparse.py`): today, tomorrow, tonight, next week, "3rd of next month", "14 Nov", morning/afternoon/evening, 4pm.
- On a miss → Jev date-parts questions. No LLM in quick add.
- Chat log stored (`GET /api/quick` returns it); "Add to plan" commits a task (type task or meeting, optional time).
Done when: the parser test table passes with zero AI calls; the Jev path is covered by a `mock_jev` test.

## Stage 8 — Polish
Read: UI_SPEC.md (Accessibility)
- Keyboard: every action reachable; visible focus; ARIA from UI_SPEC.
- Empty, loading and error states (AI down → clear message, nothing lost).
- Export/backup: `GET /api/export` (JSON); import.
Done when: keyboard-only walk-through works; AI-down path tested.

## Stage 9 — Run on the Pi
Read: DEPLOY_PI.md
- systemd service, Waitress, nightly SQLite backup, log rotation.
Done when: survives reboot; idle RAM under 80 MB; Today page loads in under 1 s on LAN.

## Stage 10 — Go public (later)
Read: RELEASE_CHECKLIST.md

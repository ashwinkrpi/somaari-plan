# somaari-plan

Planner web app. Turns .md plans, pasted text and quick-add chat into dated tasks.
Runs on Raspberry Pi 5 (8 GB, Twister OS). Single user, LAN only.

## Stack — keep it light
- Python 3.11 · Flask · Waitress · SQLite (stdlib `sqlite3`) · config via stdlib `tomllib`
- Outbound HTTP: stdlib `urllib.request` only (no requests/httpx/SDKs)
- Frontend: plain HTML + CSS + ES modules. No framework, no npm, no bundler, no CDN
- Ask before adding any dependency. Allowed list: `requirements.txt`

## Commands
- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Dev: `.venv/bin/python -m app --dev` (Flask debug server)
- Test: `.venv/bin/python -m pytest -q tests/<module>` (only what you changed; full suite at stage end)
- Prod: `.venv/bin/python -m app` (Waitress)
- Host/port come from config; never hard-code them (docs/ARCHITECTURE.md → Server config)

## Hard rules
1. AI calls only via `app/ai/router.py` (`decide` = Jev, `generate` = LLM fallback).
2. Tests use `mock_jev` / `mock_llm`. Never spend real tokens in tests.
3. Jev decides; `openrouter_free` only rewrites loose prose (or does full extraction when `mode = "llm"`). The app never calls Claude models. Details: docs/AI_PROVIDERS.md.
4. Code parses markdown, writes titles, resolves dates and schedules. Jev only answers typed questions; it never generates text.
5. Tasks store `created_at` / `closed_at` (ISO 8601, Asia/Kolkata). No duration tracking.
6. Secrets live in `.env` (gitignored). Never print or log keys.
7. UI must match docs/UI_SPEC.md, light and dark.
8. Need a decision only Ashwin can make (cost, accounts, legal, UX taste, data loss, new dependency)? Log it in docs/DECISIONS.md, ask in chat, and carry on with other work. Never decide it yourself.

## Docs — read only what the current task needs
| File | Read when |
|---|---|
| docs/STATUS.md | Always first. Update at session end (≤5 lines) |
| docs/DECISIONS.md | Before asking Ashwin anything; when a decision is answered |
| docs/BUILD_PLAN.md | Starting a stage — read that stage's section only |
| docs/ARCHITECTURE.md | Adding files, routes, modules |
| docs/DATA_MODEL.md | Touching the DB |
| docs/AI_PROVIDERS.md | AI config, providers, fallback |
| docs/AI_PROMPTS.md | Parsing, Jev questions, quick add, fallback prompts |
| docs/UI_SPEC.md | Any frontend work |
| docs/TESTING.md | Writing tests |
| docs/GUIDE.md | User docs: install, service, config, AI setup, using the app. Update when behaviour users see changes |
| docs/DEPLOY_PI.md | Pi performance targets, dev notes |
| docs/RELEASE_CHECKLIST.md | Before making the repo public |

About section: follow somaari-common/docs/ABOUT_SPEC.md.

## TypeSafe skill
Installed as a Claude Code plugin. Use it for Jev API details instead of fetching the TypeSafe docs.

## Token discipline
- One stage per session; `/clear` between stages.
- `design/*.dc.html` are big: `grep -n` for the id you need, then read those lines only.
- Make targeted edits; don't rewrite or echo whole files.
- Don't re-read a doc already read this session.

# Changelog

## v0.1.0 — unreleased

First public release.

- Pages: Today, Calendar (day / week / month), Dashboard (7-day board by priority, drag or tap to move), Done (search, reopen), New plan, Settings.
- New plan: upload a `.md` plan or paste text, review an editable preview, then commit dated tasks. Dates are read by rules first; undated lines take the date above them.
- Quick add: one line in chat becomes a task card (rules first, Jev only for a date the rules miss).
- Steps (tags) on tasks, inline edit and delete, created/closed timestamps (Asia/Kolkata).
- AI: TypeSafe Jev for typed decisions; optional LLM (OpenRouter, Gemini or any OpenAI-compatible server; model is configurable) only to rewrite loose prose, or for full extraction with `mode = "llm"`. `mode = "off"` works with no AI at all. Answers are cached, so re-uploading a plan makes no AI calls.
- About page: version, build, developer info and **Copy debug info** (shared somaari About spec).
- Backup: JSON export and add-only import from Settings.
- Themes shared with somaari.in: Warm Tactile, Liquid Glass, Dasara – Jamboo Savari, Kannada Rajyotsava; Auto picks one by the date in India. Keyboard and 380 px phone width supported; date format setting.
- Runs on a Raspberry Pi 5 with Flask, Waitress and SQLite; no frontend build step.

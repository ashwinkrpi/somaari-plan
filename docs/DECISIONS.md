# Manual decisions

Decisions only Ashwin Koppam Raghavendra can make. Claude Code adds entries; Ashwin Koppam Raghavendra fills in `Decision`.
Keep each entry ≤6 lines. Open items at the top, decided items move to the bottom.

## How Claude Code uses this file
- Hit a choice that needs Ashwin Koppam Raghavendra (cost, account, legal, UX taste, data loss, new dependency, anything not settled in docs/) → add an entry here, ask in chat, and work on something else until it's answered.
- Before adding, check this file; don't duplicate. Reopen an entry rather than writing a new one.
- Once decided: set Status, fill Decision and the date, move it under Decided, and update the affected doc if the decision changes it.
- Never decide an open item yourself, even if one option looks obvious. Recommend one instead.

## Template
```
### D-NN · <short title> · Stage N · Open
Question: <one line>
Options: A) … B) … — Recommend: <A|B> because <one line>
Decision: _ (date)
```

## Open

## Decided

### D-18 · Themes move to somaari-common · After release · Decided
Question: theme.js, the schedule, picker radios, fonts and many token values were copied between this app and somaari-site. Move them to one place?
Options: A) somaari-common theme/, served at /theme/ from the somaari_theme package; app.css keeps only app-only tokens B) keep two copies — Recommend: A
Fonts: self-hosted (somaari.in drops Google Fonts too); Onest gains its arrow/✓/↻ subsets, so those glyphs change in Liquid Glass only.
Decision: A (2026-10-19)

### D-17 · Site themes in the app · After release · Decided
Question: Bring somaari-site's themes (warm-tactile, liquid-glass, dasara-jamboo, rajyotsava; Auto = same IST seasonal schedule, default warm-tactile) into the app. What happens to the current Kinetic Swiss light/dark?
Options: A) Replace them; site themes only B) Keep Kinetic light/dark as extra choices; Auto = seasonal site theme — Recommend: B because the app's look stays available and nothing is lost
Fonts: self-hosted woff2 + OFL in web/fonts (no CDN rule), not Google Fonts links.
Decision: A, replace Kinetic light/dark; site themes only, Auto = seasonal (2026-10-19)

### D-16 · Configurable AI models · After release · Decided
Question: Users may have other AI accounts (ChatGPT, Claude, …). Make the LLM models configurable?
Decision: Yes, all of them. `[ai.models]` per provider (Settings page too) and a new `openai_compat` provider (`openai_base_url`, `OPENAI_API_KEY`, no key for LAN servers). Defaults stay free and non-Claude; users may pick any model, Claude included (amends D-02) (2026-10-18)

### D-15 · Drop the gemini_cli provider? · After release · Decided
Question: `gemini_cli` is unused (chain is `openrouter_free`) and needs PATH/login setup for the service. Remove it?
Decision: Yes. Remove `gemini_cli`, keep `gemini_api` as a free backup (2026-10-17)

### D-08 · Import: merge or replace? · Stage 8 · Decided
Question: Should `POST /api/import` only add missing tasks, or replace everything in the database with the backup?
Options: A) add-only (skip a task with the same title, due date and created_at; never edits or deletes) B) replace all (wipes current tasks first) — Recommend: A
Stage 8 note: only A is built, so no data can be lost. Restoring onto a fresh database works; replace needs your call.
Decision: A, add-only (already built; no replace-all) (2026-10-16)

### D-03 · Jev thresholds and version pin · After Stage 6 · Decided
Question: Final `task_accept` / `task_review` / `confidence_review` values and the Jev version to pin, after testing on real plan files.
Options: values proposed by Claude Code from the test runs — Recommend: decide after Stage 6 tuning
Stage 6 note: no real Jev run yet (needs key on the Pi), so no tuning data. Keep defaults 0.70 / 0.40 / 0.60 for now; run the preview on 3-4 real plans, check the skipped/flagged lists, then pin a Jev version (currently `jev-latest`).
Decision: keep Claude Code's recommended defaults 0.70 / 0.40 / 0.60; model stays `jev-latest` (2026-10-16)

### D-07 · "Moved items" in Dashboard summary · After Stage 4 · Decided
Question: UI_SPEC summary band wants "Last week … + moved items", but no move history is stored. Stage 4 shows a "not done" count instead.
Options: A) add a reschedule counter/log to tasks (schema change) B) redefine as "not done last week" and update UI_SPEC — Recommend: B (no schema change, same signal)
Decision: A, move log table `task_moves` + GET /api/moved; Dashboard shows moved and not done (2026-10-16)

### D-14 · Adopt uv for setup and running? · After release · Decided
Question: Replace `python3 -m venv` + `pip install -r requirements.txt` with uv (`uv sync`, `uv run somaari-plan`, `uv.lock`)?
Options: A) keep venv + pip (no new tool; `somaari-plan` command already added) B) uv (faster installs, pinned lockfile, one command; but a new tool on the Pi and an extra GUIDE install step) — Recommend: A for now, revisit if dependency pinning starts to matter
Decision: B, use uv. pyproject.toml + uv.lock replace requirements.txt (2026-10-16)

### D-13 · About in the menu · About section · Decided
Question: The brief says About goes after New plan, but the menu also has Done and Settings. Built as the last item, small like Settings. OK?
Decision: A. Last in the menu, small like Settings (2026-10-16)

### D-12 · Personal plan in git history · Stage 10 · Decided
Question: The old fixture and seed (personal website plan: name, city, GitHub account, domain plans) are gone from main but still in history. Clean it before going public?
Options: A) publish a fresh repo with one squashed commit B) rewrite history (git filter-repo) and force-push C) leave it — Recommend: A (simplest, nothing to force-push)
Note: design/*.dc.html mockups still show the old personal tasks and file name.
Decision: A, a fresh repo with one squashed commit; clean design/*.dc.html first (2026-10-09)

### D-05 · Licence for public release · Stage 10 · Decided
Question: Which licence when the repo goes public?
Decision: MIT (2026-10-09)

### D-11 · Quick add log after adding · After Stage 8 · Decided
Question: Should added Quick add cards keep showing on New plan?
Decision: No. Show pending cards only; added cards drop off when you leave the page; Discard / Clear for pending ones; added history kept in the DB. 01/02 inputs stay until used or reload (2026-10-08)

### D-10 · Undated lines in "Dates inside the file" · After Stage 8 · Decided
Question: Which date should a plan line with no date of its own get?
Decision: Carry forward: the date of the nearest dated line above it; lines before the first dated line spread from today (2026-10-08)

### D-09 · Editing and archiving tasks · After Stage 8 · Decided
Question: How to edit saved tasks (typos etc.) and archive completed ones?
Decision: A + 1. Edit button on Today rows and Dashboard cards (title, step, priority, date, time; Delete with confirm). No archive flag: done tasks stay in place; a Done page lists them newest first by week, with search and Reopen (2026-10-08)

### D-01 · Jev access route · Stage 5 · Decided
Question: Call Jev with a direct TypeSafe key, or through another provider if the key is waitlisted?
Decision: A. Direct TypeSafe API key (2026-10-07)

### D-04 · Settings page design · Stage 5 · Decided
Question: The Settings page isn't on the canvas. Design it on the canvas first, or build it straight from UI_SPEC tokens?
Decision: B. Build directly from UI_SPEC tokens (2026-10-07)

### D-02 · LLM fallback provider · Stage 5 · Decided
Question: Use Claude (via `claude -p` with the Pro login) for the prose fallback?
Decision: No. The app uses no Claude models; `openrouter_free` is the fallback for now (2026-10-06). Amended by D-16: defaults still never use Claude, but users may choose any model

### D-06 · Do plan paragraphs become candidates? · Stage 6 · Decided
Question: AI_PROMPTS §1 makes paragraph sentences `prose` candidates, but the golden fixture (21 candidates) has none, and its Step 2/3 heading fallback only fires if prose is ignored.
Options: A) .md files: lists/checkboxes only, prose only for pasted text with no lists B) keep prose rule, regenerate fixture — Recommend: A (matches fixture; "Done when:" lines aren't tasks)
Decision: A. Lists/checkboxes only in .md files; prose only for pasted text with no lists (2026-10-07)

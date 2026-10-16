# UI spec — Kinetic Swiss Editorial

Source of truth: `design/light.dc.html`, `design/dark.dc.html` (canvas exports). This file summarises them; open a design file only to check one section (`grep -n 'id="p-dash"'` etc.).

## Tokens (CSS custom properties on :root; dark via `[data-theme=dark]` and `prefers-color-scheme`)
| Token | Light | Dark |
|---|---|---|
| --bg | #ffffff | #0b0b0b |
| --fg | #0a0a0a | #f2f2f2 |
| --panel (left menu) | #111111 | #171717 |
| --panel-fg | #fafafa | #fafafa |
| --field | #f6f6f6 | #151515 |
| --line | #d0d0d0 | #353535 |
| --track | #e4e4e4 | #2a2a2a |
| --muted-fg (done text) | #6a6a6a | #9c9c9c |
| --accent | #ff4f00 | #ff4f00 |
| --on-accent (text on accent) | #0b0b0c | #0b0b0c |
| --accent-text (accent as text) | #c23b00 | #ff7a3d |
| --drop-hover | #ffe3d6 | #3a1a0c |
| --today-cell | #fff4ee | #1f130d |
| --weekend (Sat/Sun in Calendar; Dashboard day headers) | #f1f1f1 | #161616 |
| --weekend-cell (Sat/Sun Dashboard board cells) | #ebebeb | #1e1e1e |

Font: `web/fonts/BricolageGrotesque-var.woff2` (90 KB variable font: wght 200–800, opsz 12–96; Latin subset; OFL.txt beside it). One `@font-face` with `font-weight: 200 800; font-display: swap`. Fallback `system-ui, sans-serif`.
✓ ↗ ↵ aren't in the font and render from the fallback; that's expected.
Type: page titles 72px/800, tracking −0.05em; big numerals 84–120px/800; body 16–20px.
Rules: 2px fg rule under page titles; 1px `--line` between rows. No radius, no shadows.

## Dates
- Dates are shown and typed in the format chosen in Settings → Display (dd/mm/yyyy default; mm/dd/yyyy; yyyy-mm-dd). Stored and sent as ISO `YYYY-MM-DD`.
- Every date input is a text box in that format plus a 📅 button (44px) that opens the browser's calendar. Native `<input type=date>` isn't shown, because it uses the browser's locale format. Typed dates accept / - . or spaces and 2-digit years; an invalid date or one before `min` shows "Use dd/mm/yyyy" / "Pick … or later".
- Short labels ("Thu 17 Oct", "17 Oct 06:00") stay as they are; ISO dates printed in status lines use the chosen format.

## Shell
- Left panel (flex 1 1 240px, `--panel`): logo "somaari—plan", big date "06" + weekday/month, nav, footer "Week NN / YYYY".
- Nav buttons (min-height 52px): Today (shows "N open"), Calendar, Dashboard (shows done/planned), Done, New plan ↗, plus Settings and About (small, at the bottom; About last).
- Active item: `--accent` background, `--on-accent` text, `aria-current="page"`.
- Main: flex 999 1 640px, padding 28px 36px. Content uses the full width (no max-width; changed 2026-10-08 for large monitors). Forms stay narrow: Settings ≤640px, About ≤760px, Done search ≤480px. Below 900px the panel stacks on top.
- Exactly one page visible at a time.

## Today
Title "Today (N open)". Ordered list sorted by priority. Row: 2-digit index, title (24px/600), meta line: priority badge · step · "Created …" · "Closed …" or orange "Open" tag. Right: "Edit" (1px `--line` border) then "Mark done" / "Done ✓" button (2px border, ≥48px tall). Done = strikethrough + muted text.

## Editing a task (D-09)
"Edit" on Today rows, Calendar Day rows and Dashboard cards swaps that row/card for an inline form (2px accent border): Title · Step (tag, suggestions) · Priority · Date · Time, then Save (accent) · Cancel · "Delete…".
- Done tasks: "Edit" is visible but disabled (like "Move"), with a "Reopen the task to edit it" tooltip. Reopen (Today's "Done ✓" toggle or the Done page) enables Edit and Move again.
- One task edited at a time. Opening focuses Title; Esc or Cancel closes and returns focus to its Edit button; Save does the same.
- "Delete…" asks first: "Delete this task? This can't be undone." with Delete (accent border) · Keep (focused). Delete is for mistakes; finished work is marked done, not deleted.
- Errors show inline (`role=alert`); typed values are kept.

## Calendar
Title = range label. Segmented Day / Week / Month (active = 800 weight + 2px underline, `aria-pressed`).
- Week: 7 columns, big day numerals, items with a 3px left rule (accent = High, fg = others, muted = done).
- Month: Mon-first grid, out-of-month muted, today cell filled accent, "N tasks" label.
- Weekend: Sat/Sun columns (week) and Sat/Sun headers + cells (month) use `--weekend`; today's highlight wins.
- Day: numbered rows with created/closed.
Wide content scrolls horizontally inside its own container.

## Dashboard
1. Summary band (3 cells, 1px dividers): This week done/planned · progress by step (4px bars) · Last week done/planned + moved items.
2. Board: header row of days; lanes High / Medium / Low; cells `--field`, today column `--today-cell`.
   Weekend: Sat/Sun headers `--weekend`, Sat/Sun cells `--weekend-cell`; today and drop-hover win.
   Cards: `--bg`, 1.5px fg border, title 13px/600, step, small "Move" and "Edit" buttons (inline editor as above, fields stacked).
   Open cards due today or earlier also get a small "Done" button (marks done; Today, Calendar and nav counts refresh).
   Done cards: struck-through title, "Move" visible but disabled, not draggable.
   Drag: `draggable`, dragover highlights the cell with `--drop-hover` + dashed accent outline.
   Tap fallback: "Move" selects (3px accent outline) → every cell shows "Move here" → banner with Cancel.
   Live status line (`role=status`) confirms each move.

## Done
Title "Done (N)". Search box (title or step, 250 ms debounce). Finished tasks newest first, grouped by the week they were closed (2px rule + "5 Oct – 11 Oct · N done"). Row: title, meta (priority badge · step · "Due …" · "Closed …"), "Reopen" (2px) and "Reopen on…" (1px) buttons. Reopen keeps a future due date, else moves it to today. "Reopen on…" swaps in a date picker (min today, default tomorrow or the future due date) · Reopen · Cancel; Esc cancels. Status line says where it went ("Reopened for today: …"). Archive = done; there is no separate archive (D-09). Shows the latest 500; search finds older ones.

## New plan ↗
Title "Plan in. Tasks out." Two columns:
- Left: 01 Upload plans (multi-file; per file: Schedule [Week starting | Dates inside the file] + Date, Remove) · 02 Paste text (Schedule [Use dates in the text | Week starting | A single day] + Date + Tasks per day) · "Generate plan →" accent button → preview list before commit.
- Steps (tags): one-line muted hints (13px, `code` for headings) close 01 and 02. 01: "Tags: each `## heading` tags the tasks under it. `## Step 1: Domain (this week)` → Domain". 02: "Tags: same rule as files. Lines with no `## heading` get the Step above, or no tag." 02 has a "Step (tag)" field applied to pasted tasks without a heading step. The preview row has an editable Step box. All step inputs suggest steps already in use (`<datalist>`), max 30 chars.
- Right: 03 Quick add, a chat log (`role=log`). User bubble right (fg bg), result card left: TASK/MEETING badge, parsed date/time, title, optional "Step (tag)" field, "Add to plan" / "Added ✓", "Discard". The log shows pending cards only: an added card shows "Added ✓" until you leave New plan, then drops off (its task is on Today/Calendar). "Clear N" by the heading (when 2+ pending) discards all pending cards. Added entries stay in the DB as history (D-11). Input + "Add ↵" (Enter submits).

## About
- Follows somaari-common/docs/ABOUT_SPEC.md. App name (48px/800) + "vX · build <commit> · <date>" (muted), then Developer and Debug info sections: 20px/800 heading on a 2px fg rule, label/value rows (label 14px `--muted-fg`, 1px `--line` between rows; stacked below 480px). Links in `--accent-text`.
- **Copy debug info** (primary button) copies the spec's text block; `role=status` says copied/failed (falls back to `execCommand` on plain-http LAN). "Show copied text" disclosure shows the exact block.

## Accessibility
Buttons for all actions (no clickable divs). Visible focus ring (2px accent, 2px offset). Every input has a label. Contrast: text on accent always `--on-accent`.

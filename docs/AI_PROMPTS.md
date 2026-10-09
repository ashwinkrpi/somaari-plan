# AI requests

Question sets live in `app/ai/questions.py` with a `VERSION` constant. Bump it on any wording change; it is part of the cache key.

## 1. Parse in code first (`app/ingest/mdparse.py`, no AI)
- Drop: code blocks, HTML comments, tables, link-only lines, blank lines, front matter.
- `##` headings (`##Ideas` without a space also counts; a lone `#tag` doesn't) → current step: heading text minus `Step N:` / `Later:` and parentheses, max 30 chars at a word boundary. `#` is the title; `###`/`####` don't change the step.
- Candidates: top-level list items, numbered items, `- [ ]` checkboxes. `- [x]` → skip (already done).
- Nested (indented) items are details of their parent: append to its notes, never separate candidates.
- A `##` section with no candidates outside code blocks (e.g. "here's a prompt to run") → one candidate from the heading text.
- Paragraphs in .md files are never candidates (intros, notes, "Done when:" lines). Pasted text with no list items: each sentence → a candidate marked `prose` (D-06).
- Title = cleaned line: strip markers, bold/italics, trailing colons, backticks; max 120 chars.
- Each candidate gets an id `L1…Ln`, its step, and its text.

## 2. Jev: line decisions (one request per ≤40 lines)
State (JSON): `{"today": "2026-10-06", "lines": [{"id": "L1", "step": "Domain", "text": "..."}]}`

Per line `Ln`, four questions (ids `t_Ln`, `p_Ln`, `m_Ln`, `d_Ln`):
| id | type | instructions | criteria |
|---|---|---|---|
| t_Ln | noul | Line Ln is an action the user must do, not a heading, note, example or explanation. | – |
| p_Ln | choice | Priority of line Ln in this plan. | High: blocks later steps or is time-critical · Medium: normal work · Low: optional, nice-to-have or marked later |
| m_Ln | noul | Line Ln is a meeting, call or appointment with other people. | – |
| d_Ln | noul | Line Ln names a specific date or day. | – |

Code applies thresholds (AI_PROVIDERS.md):
- `t ≥ task_accept` → task · `task_review ≤ t < task_accept` → task, flagged · below → "skipped lines" (collapsed in preview, one click to restore)
- `p` confidence < `confidence_review` → flagged; priority still set
- `m ≥ 0.5` → type meeting

## 3. Dates in plan lines: rules first, then Jev date parts
Code reads each line with the Quick add rules (`quickparse.find`: "14 Oct", "Thu 15 Oct", weekdays, today/tomorrow, 6:00am, 5pm …), ignoring text in (brackets). A rule-read date wins; an exact clock time beats Jev's morning/afternoon. A time with no date keeps the time and the scheduler picks the day.
Jev date parts are asked only for lines with `d ≥ 0.5` that the rules couldn't date (batched). Added 2026-10-08 after Jev returned `mode: absolute` with no month for "by Thu 15 Oct".

Follows TypeSafe's date-extraction pattern: Jev reads the parts and code does the calendar maths. Per line, Choice questions:
- `mode`: absolute | relative | none
- `month` (12 + none) · `day` (1–31 + none) · `year` (this year, next year, none)
- `anchor`: today | tomorrow | day_after | weekday | next_week | next_month_day | none
- `weekday` (7 + none) · `week_offset`: current | next | none
- `time_of_day`: morning | afternoon | evening | none
Code resolves against TODAY: no year → this year, or next year if more than 31 days past. "3rd of next month" = `next_month_day` + `day`. Morning/afternoon/evening = 10:00/15:00/18:00. Lowest part confidence < `confidence_review` → flagged.

## 4. Scheduling (code, never AI)
- `week`: keep order; fill Mon→Sun from the anchor, `per_day` per day; High tasks no later than Wednesday when there's room; overflow → next Monday.
- `day`: all on the anchor date.
- `in_text`: use resolved dates. An undated task takes the date of the nearest dated task above it in the file (carry forward, D-10); undated tasks before the first dated one follow the `week` rule from today.

## 5. Quick add
1. `app/quickparse.py` rules (no AI): today, tomorrow, tonight, next week, "3rd of next month", "14 Nov", weekday names, morning/afternoon/evening, 4pm, 10:30am. The title is the text with the matched date span removed.
2. On a miss → Jev date-parts set (section 3) + `m` noul on the single line. The title is the full text (the user can edit it on the card).
3. Never uses an LLM.

## 6. LLM prompts (fallback only)
### Prose rewrite (`mode=jev`, `rewrite_prose=true`)
Sent only for blocks where more than half the candidates are `prose`, or a prose sentence has more than 20 words.
```
# v1
Rewrite each numbered sentence as one task title: imperative, max 12 words, keep product names.
If a sentence is not a task, return null for it. JSON only: {"r": ["title" | null, ...]}
```
The rewritten titles then go through section 2 like any other line.

### Full extraction (`mode=llm`)
```
# v1
Extract actionable tasks. JSON only:
{"t":[{"s":step,"n":title,"p":"H"|"M"|"L","d":"YYYY-MM-DD"|null,"m":true|false}]}
n: imperative, max 12 words. d only if the text states a date. Max 40 tasks.
```
User message: `TODAY=YYYY-MM-DD` followed by the trimmed text.

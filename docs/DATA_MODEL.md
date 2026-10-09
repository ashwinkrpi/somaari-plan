# Data model (SQLite, `app/schema.sql`)

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE sources (
  id          INTEGER PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('file','text','quick')),
  name        TEXT,                 -- file name, or NULL for pasted text
  content_sha TEXT NOT NULL,        -- sha256 of normalised content (AI cache key)
  schedule    TEXT CHECK (schedule IN ('week','day','in_text')), -- NULL for kind 'quick'
  anchor_date TEXT,                 -- week start or single day, YYYY-MM-DD
  per_day     INTEGER DEFAULT 4,
  created_at  TEXT NOT NULL
);

CREATE TABLE tasks (
  id          INTEGER PRIMARY KEY,
  source_id   INTEGER REFERENCES sources(id) ON DELETE SET NULL,
  title       TEXT NOT NULL,
  step        TEXT,                 -- heading/phase from the plan, or typed by the user; ≤30 chars, NULL = no tag
  type        TEXT NOT NULL DEFAULT 'task' CHECK (type IN ('task','meeting')),
  priority    TEXT NOT NULL DEFAULT 'Medium' CHECK (priority IN ('High','Medium','Low')),
  due_date    TEXT NOT NULL,        -- YYYY-MM-DD
  due_time    TEXT,                 -- HH:MM, meetings or explicit times only
  sort_order  INTEGER DEFAULT 0,    -- within day+priority cell
  ai_conf     REAL,                 -- lowest Jev confidence used for this task; NULL if manual
  reviewed    INTEGER DEFAULT 1,    -- 0 = flagged in preview and not yet confirmed
  created_at  TEXT NOT NULL,        -- ISO 8601 with +05:30
  closed_at   TEXT                  -- NULL = open
);
CREATE INDEX tasks_due ON tasks(due_date);

CREATE TABLE ai_cache (
  key         TEXT PRIMARY KEY,     -- sha256(provider + model + prompt/question-set version + state)
  provider    TEXT, model TEXT,     -- e.g. jev / jev-1.13.0
  response    TEXT NOT NULL,        -- validated JSON
  created_at  TEXT NOT NULL
);

CREATE TABLE chat (
  id INTEGER PRIMARY KEY, text TEXT NOT NULL, parsed TEXT NOT NULL, -- JSON card
  task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL, created_at TEXT NOT NULL
);
```

## Rules
- "Done" means `closed_at IS NOT NULL`. There is no separate status column.
- Week = Monday–Sunday.
- Rescheduling changes `due_date`; it never touches `created_at`.
- User-entered steps (preview, paste, quick add, PATCH) are whitespace-collapsed and cut to 30 chars; blank → NULL.
- Reopening (closed → open) never leaves a task in the past: a past `due_date` becomes today; an explicit past date is refused (400). Future due dates are kept.
- Archive = done: there is no archive flag. Done tasks stay where they are; the Done page lists them by `closed_at` (D-09).
- Deleting a source keeps its tasks (source_id → NULL) unless the user chooses "remove tasks too".

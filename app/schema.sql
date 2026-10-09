PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
  id          INTEGER PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('file','text','quick')),
  name        TEXT,
  content_sha TEXT NOT NULL,
  schedule    TEXT CHECK (schedule IN ('week','day','in_text')),
  anchor_date TEXT,
  per_day     INTEGER DEFAULT 4,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
  id          INTEGER PRIMARY KEY,
  source_id   INTEGER REFERENCES sources(id) ON DELETE SET NULL,
  title       TEXT NOT NULL,
  step        TEXT,
  type        TEXT NOT NULL DEFAULT 'task' CHECK (type IN ('task','meeting')),
  priority    TEXT NOT NULL DEFAULT 'Medium' CHECK (priority IN ('High','Medium','Low')),
  due_date    TEXT NOT NULL,
  due_time    TEXT,
  sort_order  INTEGER DEFAULT 0,
  ai_conf     REAL,
  reviewed    INTEGER DEFAULT 1,
  created_at  TEXT NOT NULL,
  closed_at   TEXT
);
CREATE INDEX IF NOT EXISTS tasks_due ON tasks(due_date);

CREATE TABLE IF NOT EXISTS ai_cache (
  key         TEXT PRIMARY KEY,
  provider    TEXT, model TEXT,
  response    TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat (
  id INTEGER PRIMARY KEY, text TEXT NOT NULL, parsed TEXT NOT NULL,
  task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL, created_at TEXT NOT NULL
);

"""JSON backup: GET /api/export, POST /api/import (add-only, never overwrites)."""
from flask import Blueprint, Response, jsonify, request
import json

from ..db import now_iso
from .tasks import PRIORITIES, TYPES, err, open_db, valid_date, valid_time

bp = Blueprint("export", __name__)

VERSION = 1
SRC_COLS = ["id", "kind", "name", "content_sha", "schedule", "anchor_date", "per_day", "created_at"]
TASK_COLS = ["id", "source_id", "title", "step", "type", "priority", "due_date", "due_time", "sort_order",
             "ai_conf", "reviewed", "created_at", "closed_at"]
MOVE_COLS = ["task_id", "from_date", "to_date", "moved_at"]
KINDS = ("file", "text", "quick")
SCHEDULES = (None, "week", "day", "in_text")


@bp.get("/api/export")
def export():
    conn = open_db()
    try:
        data = {
            "app": "somaari-plan", "version": VERSION, "exported_at": now_iso(),
            "sources": [dict(r) for r in conn.execute(f"SELECT {', '.join(SRC_COLS)} FROM sources ORDER BY id")],
            "tasks": [dict(r) for r in conn.execute(f"SELECT {', '.join(TASK_COLS)} FROM tasks ORDER BY id")],
            "moves": [dict(r) for r in conn.execute(f"SELECT {', '.join(MOVE_COLS)} FROM task_moves ORDER BY id")],
        }
    finally:
        conn.close()
    name = "somaari-plan-" + data["exported_at"][:10] + ".json"
    return Response(json.dumps(data, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _clean_task(t):
    if not isinstance(t, dict):
        return None
    title = t.get("title")
    if not isinstance(title, str) or not title.strip() or not valid_date(t.get("due_date")):
        return None
    if t.get("priority", "Medium") not in PRIORITIES or t.get("type", "task") not in TYPES:
        return None
    if not valid_time(t.get("due_time")):
        return None
    if not isinstance(t.get("created_at"), str) or not (t.get("closed_at") is None or isinstance(t["closed_at"], str)):
        return None
    step = t.get("step")
    so = t.get("sort_order", 0)
    if (step is not None and not isinstance(step, str)) or not isinstance(so, int) or isinstance(so, bool):
        return None
    conf = t.get("ai_conf")
    if conf is not None and (isinstance(conf, bool) or not isinstance(conf, (int, float))):
        return None
    return {"title": title.strip(), "step": step, "type": t.get("type", "task"), "priority": t.get("priority", "Medium"),
            "due_date": t["due_date"], "due_time": t.get("due_time"), "sort_order": so, "ai_conf": conf,
            "reviewed": 0 if t.get("reviewed") in (0, False) else 1,
            "created_at": t["created_at"], "closed_at": t.get("closed_at")}


def _clean_source(s):
    if not isinstance(s, dict) or s.get("kind") not in KINDS or not isinstance(s.get("content_sha"), str):
        return None
    if s.get("schedule") not in SCHEDULES or not isinstance(s.get("created_at"), str):
        return None
    ad, pd = s.get("anchor_date"), s.get("per_day", 4)
    if (ad is not None and not valid_date(ad)) or not isinstance(pd, int) or isinstance(pd, bool):
        return None
    name = s.get("name")
    if name is not None and not isinstance(name, str):
        return None
    return {"kind": s["kind"], "name": name, "content_sha": s["content_sha"], "schedule": s.get("schedule"),
            "anchor_date": ad, "per_day": pd, "created_at": s["created_at"]}


@bp.post("/api/import")
def import_():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get("app") != "somaari-plan":
        return err("This is not a somaari-plan backup")
    if body.get("version") != VERSION:
        return err("Unsupported backup version")
    srcs, tasks, moves = body.get("sources", []), body.get("tasks", []), body.get("moves", [])
    if not isinstance(srcs, list) or not isinstance(tasks, list) or not isinstance(moves, list):
        return err("sources, tasks and moves must be lists")
    for m in moves:
        if (not isinstance(m, dict) or not isinstance(m.get("task_id"), int) or not valid_date(m.get("from_date"))
                or not valid_date(m.get("to_date")) or not isinstance(m.get("moved_at"), str)):
            return err("A move in the backup is invalid")
    clean_src = {}
    for s in srcs:
        c = _clean_source(s)
        if c is None or not isinstance(s.get("id"), int):
            return err("A source in the backup is invalid")
        clean_src[s["id"]] = c
    clean = []
    for t in tasks:
        c = _clean_task(t)
        if c is None:
            return err("A task in the backup is invalid")
        sid = t.get("source_id")
        if sid is not None and sid not in clean_src:
            return err("A task points to a missing source")
        clean.append((c, sid, t.get("id")))
    conn = open_db()
    try:
        idmap = {}
        for old, c in clean_src.items():
            row = conn.execute("SELECT id FROM sources WHERE kind=? AND content_sha=? AND created_at=?",
                               (c["kind"], c["content_sha"], c["created_at"])).fetchone()
            if row:
                idmap[old] = row["id"]
            else:
                cur = conn.execute(f"INSERT INTO sources ({', '.join(c)}) VALUES ({', '.join('?' * len(c))})", list(c.values()))
                idmap[old] = cur.lastrowid
        added = skipped = 0
        task_ids = {}   # backup task id -> new id, for added tasks only
        for c, sid, old in clean:
            dup = conn.execute("SELECT 1 FROM tasks WHERE title=? AND due_date=? AND created_at=?",
                               (c["title"], c["due_date"], c["created_at"])).fetchone()
            if dup:
                skipped += 1
                continue
            c = {**c, "source_id": idmap.get(sid)}
            cur = conn.execute(f"INSERT INTO tasks ({', '.join(c)}) VALUES ({', '.join('?' * len(c))})", list(c.values()))
            if isinstance(old, int):
                task_ids[old] = cur.lastrowid
            added += 1
        for m in moves:   # move history follows only the tasks this import added
            if m["task_id"] in task_ids:
                conn.execute("INSERT INTO task_moves (task_id, from_date, to_date, moved_at) VALUES (?, ?, ?, ?)",
                             (task_ids[m["task_id"]], m["from_date"], m["to_date"], m["moved_at"]))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"added": added, "skipped": skipped})

"""JSON backup: GET /api/export, POST /api/import (add-only, never overwrites)."""
from flask import Blueprint, Response, current_app, jsonify, request
import json

from ..db import connect, now_iso
from .tasks import PRIORITIES, TYPES, _valid_date, _valid_time

bp = Blueprint("export", __name__)

VERSION = 1
SRC_COLS = ["id", "kind", "name", "content_sha", "schedule", "anchor_date", "per_day", "created_at"]
TASK_COLS = ["id", "source_id", "title", "step", "type", "priority", "due_date", "due_time", "sort_order",
             "ai_conf", "reviewed", "created_at", "closed_at"]
KINDS = ("file", "text", "quick")
SCHEDULES = (None, "week", "day", "in_text")


def _err(msg, code=400):
    return jsonify({"error": msg}), code


@bp.get("/api/export")
def export():
    conn = connect(current_app.config["DB_PATH"])
    try:
        data = {
            "app": "somaari-plan", "version": VERSION, "exported_at": now_iso(),
            "sources": [dict(r) for r in conn.execute(f"SELECT {', '.join(SRC_COLS)} FROM sources ORDER BY id")],
            "tasks": [dict(r) for r in conn.execute(f"SELECT {', '.join(TASK_COLS)} FROM tasks ORDER BY id")],
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
    if not isinstance(title, str) or not title.strip() or not _valid_date(t.get("due_date")):
        return None
    if t.get("priority", "Medium") not in PRIORITIES or t.get("type", "task") not in TYPES:
        return None
    if not _valid_time(t.get("due_time")):
        return None
    for k in ("created_at", "closed_at"):
        v = t.get(k)
        if v is not None and not isinstance(v, str):
            return None
    if not isinstance(t.get("created_at"), str):
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
    if (ad is not None and not _valid_date(ad)) or not isinstance(pd, int) or isinstance(pd, bool):
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
        return _err("This is not a somaari-plan backup")
    if body.get("version") != VERSION:
        return _err("Unsupported backup version")
    srcs, tasks = body.get("sources", []), body.get("tasks", [])
    if not isinstance(srcs, list) or not isinstance(tasks, list):
        return _err("sources and tasks must be lists")
    clean_src = {}
    for s in srcs:
        c = _clean_source(s)
        if c is None or not isinstance(s.get("id"), int):
            return _err("A source in the backup is invalid")
        clean_src[s["id"]] = c
    clean = []
    for t in tasks:
        c = _clean_task(t)
        if c is None:
            return _err("A task in the backup is invalid")
        sid = t.get("source_id")
        if sid is not None and sid not in clean_src:
            return _err("A task points to a missing source")
        clean.append((c, sid))
    conn = connect(current_app.config["DB_PATH"])
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
        for c, sid in clean:
            dup = conn.execute("SELECT 1 FROM tasks WHERE title=? AND due_date=? AND created_at=?",
                               (c["title"], c["due_date"], c["created_at"])).fetchone()
            if dup:
                skipped += 1
                continue
            c = {**c, "source_id": idmap.get(sid)}
            conn.execute(f"INSERT INTO tasks ({', '.join(c)}) VALUES ({', '.join('?' * len(c))})", list(c.values()))
            added += 1
        conn.commit()
    finally:
        conn.close()
    return jsonify({"added": added, "skipped": skipped})

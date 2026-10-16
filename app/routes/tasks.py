"""Task CRUD routes."""
import re
from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, request

from ..db import IST, connect, now_iso

bp = Blueprint("tasks", __name__)

PRIORITIES = ("High", "Medium", "Low")
TYPES = ("task", "meeting")
COLS = "id, source_id, title, step, type, priority, due_date, due_time, sort_order, ai_conf, reviewed, created_at, closed_at"


def err(msg, code=400):
    return jsonify({"error": msg}), code


def valid_date(v):
    try:
        return isinstance(v, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)) and date.fromisoformat(v) is not None
    except ValueError:
        return False


def norm_step(v):
    """User-entered step: None/blank -> None, else trimmed text max 30 chars. Raises ValueError if not text."""
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError("step must be text")
    v = " ".join(v.split())[:30].strip()
    return v or None


def valid_time(v):
    return v is None or (isinstance(v, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v) is not None)


def _row(r):
    d = dict(r)
    d["closed"] = d["closed_at"] is not None
    d["reviewed"] = bool(d["reviewed"])
    return d


def _check(body, partial):
    """Return (clean_fields, error)."""
    out = {}
    if "title" in body or not partial:
        t = body.get("title")
        if not isinstance(t, str) or not t.strip():
            return None, "title is required"
        out["title"] = t.strip()
    if "due_date" in body or not partial:
        if not valid_date(body.get("due_date")):
            return None, "due_date must be YYYY-MM-DD"
        out["due_date"] = body["due_date"]
    if "due_time" in body:
        if not valid_time(body["due_time"]):
            return None, "due_time must be HH:MM"
        out["due_time"] = body["due_time"]
    if "priority" in body:
        if body["priority"] not in PRIORITIES:
            return None, "priority must be High, Medium or Low"
        out["priority"] = body["priority"]
    if "type" in body:
        if body["type"] not in TYPES:
            return None, "type must be task or meeting"
        out["type"] = body["type"]
    if "step" in body:
        try:
            out["step"] = norm_step(body["step"])
        except ValueError as e:
            return None, str(e)
    if "sort_order" in body:
        if not isinstance(body["sort_order"], int) or isinstance(body["sort_order"], bool):
            return None, "sort_order must be an integer"
        out["sort_order"] = body["sort_order"]
    return out, None


def open_db():
    return connect(current_app.config["DB_PATH"])


@bp.get("/api/tasks")
def list_tasks():
    frm, to = request.args.get("from"), request.args.get("to")
    for v in (frm, to):
        if v is not None and not valid_date(v):
            return err("from/to must be YYYY-MM-DD")
    sql, args = f"SELECT {COLS} FROM tasks WHERE 1=1", []
    if frm:
        sql += " AND due_date >= ?"
        args.append(frm)
    if to:
        sql += " AND due_date <= ?"
        args.append(to)
    sql += " ORDER BY due_date, due_time IS NULL, due_time, sort_order, id"
    conn = open_db()
    try:
        return jsonify([_row(r) for r in conn.execute(sql, args)])
    finally:
        conn.close()


@bp.post("/api/tasks")
def create_task():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return err("JSON body required")
    f, e = _check(body, partial=False)
    if e:
        return err(e)
    f.setdefault("priority", "Medium")
    f.setdefault("type", "task")
    f["created_at"] = now_iso()
    cols = ", ".join(f)
    conn = open_db()
    try:
        cur = conn.execute(f"INSERT INTO tasks ({cols}) VALUES ({', '.join('?' * len(f))})", list(f.values()))
        conn.commit()
        r = conn.execute(f"SELECT {COLS} FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(_row(r)), 201
    finally:
        conn.close()


@bp.patch("/api/tasks/<int:tid>")
def patch_task(tid):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return err("JSON body required")
    f, e = _check(body, partial=True)
    if e:
        return err(e)
    if "closed" in body:
        if not isinstance(body["closed"], bool):
            return err("closed must be true or false")
    conn = open_db()
    try:
        cur = conn.execute("SELECT closed_at, due_date FROM tasks WHERE id=?", (tid,)).fetchone()
        if cur is None:
            return err("not found", 404)
        if "closed" in body:
            if body["closed"] and cur["closed_at"] is None:
                f["closed_at"] = now_iso()
            elif not body["closed"]:
                f["closed_at"] = None
                if cur["closed_at"] is not None:    # reopening: never leave the task in the past
                    today = datetime.now(IST).date().isoformat()
                    if "due_date" in f and f["due_date"] < today:
                        return err("a reopened task can't be due in the past")
                    if f.get("due_date", cur["due_date"]) < today:
                        f["due_date"] = today
        if f:
            sets = ", ".join(f"{k}=?" for k in f)
            conn.execute(f"UPDATE tasks SET {sets} WHERE id=?", [*f.values(), tid])
            if f.get("due_date", cur["due_date"]) != cur["due_date"]:   # D-07: log every reschedule
                conn.execute("INSERT INTO task_moves (task_id, from_date, to_date, moved_at) VALUES (?, ?, ?, ?)",
                             (tid, cur["due_date"], f["due_date"], now_iso()))
            conn.commit()
        return jsonify(_row(conn.execute(f"SELECT {COLS} FROM tasks WHERE id=?", (tid,)).fetchone()))
    finally:
        conn.close()


@bp.get("/api/done")
def list_done():
    """Done tasks, newest closed first. ?q= filters title/step (case-insensitive); ?limit= caps rows (default 500)."""
    q = (request.args.get("q") or "").strip()
    try:
        limit = max(1, min(int(request.args.get("limit", 500)), 2000))
    except ValueError:
        return err("limit must be a number")
    sql, args = f"SELECT {COLS} FROM tasks WHERE closed_at IS NOT NULL", []
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sql += " AND (title LIKE ? ESCAPE '\\' OR step LIKE ? ESCAPE '\\')"
        args += [like, like]
    sql += " ORDER BY closed_at DESC, id DESC LIMIT ?"
    conn = open_db()
    try:
        return jsonify([_row(r) for r in conn.execute(sql, [*args, limit])])
    finally:
        conn.close()


@bp.get("/api/moved")
def moved_count():
    """Tasks once due in from..to that now sit outside it (Dashboard "moved", D-07)."""
    frm, to = request.args.get("from"), request.args.get("to")
    if not (valid_date(frm) and valid_date(to)):
        return err("from and to must be YYYY-MM-DD")
    conn = open_db()
    try:
        n = conn.execute("SELECT COUNT(DISTINCT m.task_id) FROM task_moves m JOIN tasks t ON t.id = m.task_id"
                         " WHERE m.from_date BETWEEN ? AND ? AND t.due_date NOT BETWEEN ? AND ?",
                         (frm, to, frm, to)).fetchone()[0]
        return jsonify({"moved": n})
    finally:
        conn.close()


@bp.get("/api/steps")
def list_steps():
    """Distinct steps in use, most recently used first (for step suggestions)."""
    conn = open_db()
    try:
        rows = conn.execute("SELECT step FROM tasks WHERE step IS NOT NULL AND step <> ''"
                            " GROUP BY step ORDER BY MAX(created_at) DESC, step LIMIT 50")
        return jsonify([r["step"] for r in rows])
    finally:
        conn.close()


@bp.delete("/api/tasks/<int:tid>")
def delete_task(tid):
    conn = open_db()
    try:
        cur = conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
        conn.commit()
        if cur.rowcount == 0:
            return err("not found", 404)
        return "", 204
    finally:
        conn.close()

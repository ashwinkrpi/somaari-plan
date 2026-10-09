"""Quick add: one line -> parsed card (rules first, Jev date parts on a miss, never an LLM)."""
import hashlib
import json
import re
from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, request

from .. import config, dates, quickparse
from ..ai import questions as Q
from ..ai import router
from ..db import IST, connect, now_iso
from .tasks import norm_step

bp = Blueprint("quick", __name__)
MAX_TEXT = 300


def _err(msg, code=400):
    return jsonify({"error": msg}), code


def _today(v):
    if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        try:
            return date.fromisoformat(v)
        except ValueError:
            pass
    return datetime.now(IST).date()


def _jev_card(text, today, cfg):
    """Date-parts questions plus a meeting question on the single line."""
    line = [{"id": "L1", "step": "", "text": text}]
    qs = Q.date_questions(line)
    qs["m_L1"] = {"type": "noul", "instructions": "Line L1 is a meeting, call or appointment with other people."}
    r = router.decide(Q.line_state(line, today.isoformat()), qs, "quick", Q.VERSION, cfg)
    if not r["ok"]:
        return None
    a = r["answers"]
    val = lambda q, k: (a.get(q) or {}).get(k)
    parts = {p: (val(f"{p}_L1", "choice") or "none", val(f"{p}_L1", "confidence") or 1.0) for p in dates.PARTS}
    d, clock, conf = dates.resolve(parts, today)
    meeting = float(val("m_L1", "noul") or 0.0) >= 0.5
    return {"date": d, "time": clock, "conf": conf, "meeting": meeting}


def make_card(text, today, cfg):
    p = quickparse.parse(text, today)
    card = {"title": p["title"], "type": p["type"], "date": p["date"].isoformat() if p["date"] else None,
            "time": p["time"], "week": p["week"], "source": "rules", "note": ""}
    if p["matched"]:
        return card
    card["title"] = text
    j = _jev_card(text, today, cfg) if cfg["mode"] != "off" else None
    if j is None:
        card.update(source="none", date=today.isoformat(),
                    note="No date found; set to today. Change it before adding.")
        return card
    card["source"] = "jev"
    if j["meeting"]:
        card["type"] = "meeting"
    if j["date"]:
        card.update(date=j["date"].isoformat(), time=j["time"])
        if j["conf"] < cfg["thresholds"]["confidence_review"]:
            card["note"] = "Unsure about the date. Check it before adding."
    else:
        card.update(date=today.isoformat(), note="No date found; set to today. Change it before adding.")
    return card


def _row(r):
    return {"id": r["id"], "text": r["text"], "parsed": json.loads(r["parsed"]), "task_id": r["task_id"],
            "created_at": r["created_at"]}


@bp.get("/api/quick")
def log():
    """Pending cards (not yet added), oldest first. ?all=1 includes added ones (last 100)."""
    where = "" if request.args.get("all") == "1" else "WHERE task_id IS NULL"
    conn = connect(current_app.config["DB_PATH"])
    try:
        rows = conn.execute(f"SELECT * FROM (SELECT * FROM chat {where} ORDER BY id DESC LIMIT 100) ORDER BY id").fetchall()
        return jsonify([_row(r) for r in rows])
    finally:
        conn.close()


@bp.delete("/api/quick/<int:cid>")
def discard(cid):
    """Discard one pending card. Added cards are history and stay (409)."""
    conn = connect(current_app.config["DB_PATH"])
    try:
        row = conn.execute("SELECT task_id FROM chat WHERE id=?", (cid,)).fetchone()
        if not row:
            return _err("Not found", 404)
        if row["task_id"]:
            return _err("Already added; it's a task now.", 409)
        conn.execute("DELETE FROM chat WHERE id=?", (cid,))
        conn.commit()
        return "", 204
    finally:
        conn.close()


@bp.delete("/api/quick")
def clear():
    """Discard every pending card. Added cards and their tasks are untouched."""
    conn = connect(current_app.config["DB_PATH"])
    try:
        n = conn.execute("DELETE FROM chat WHERE task_id IS NULL").rowcount
        conn.commit()
        return jsonify({"discarded": n})
    finally:
        conn.close()


@bp.post("/api/quick")
def create():
    body = request.get_json(silent=True)
    text = body.get("text") if isinstance(body, dict) else None
    if not isinstance(text, str) or not text.strip():
        return _err("Type something to add.")
    text = text.strip()
    if len(text) > MAX_TEXT:
        return _err(f"Keep it under {MAX_TEXT} characters.")
    card = make_card(text, _today(body.get("today")), config.load_ai())
    conn = connect(current_app.config["DB_PATH"])
    try:
        cur = conn.execute("INSERT INTO chat (text, parsed, created_at) VALUES (?,?,?)",
                           (text, json.dumps(card), now_iso()))
        conn.commit()
        row = conn.execute("SELECT * FROM chat WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(_row(row)), 201
    finally:
        conn.close()


@bp.post("/api/quick/<int:cid>/add")
def add(cid):
    body = request.get_json(silent=True)
    body = body if isinstance(body, dict) else {}
    conn = connect(current_app.config["DB_PATH"])
    try:
        row = conn.execute("SELECT * FROM chat WHERE id=?", (cid,)).fetchone()
        if not row:
            return _err("Not found", 404)
        if row["task_id"]:
            return _err("Already added.", 409)
        card = json.loads(row["parsed"])
        title = body.get("title", card["title"])
        ty = body.get("type", card["type"])
        due = body.get("due_date", card["date"])
        clock = body.get("due_time", card["time"])
        try:
            step = norm_step(body.get("step", card.get("step")))
        except ValueError as e:
            return _err(str(e))
        if not isinstance(title, str) or not title.strip():
            return _err("Title is required.")
        if ty not in ("task", "meeting"):
            return _err("type must be task or meeting")
        if not (isinstance(due, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", due)):
            return _err("due_date must be YYYY-MM-DD")
        try:
            date.fromisoformat(due)
        except ValueError:
            return _err("due_date must be YYYY-MM-DD")
        if clock is not None and not (isinstance(clock, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", clock)):
            return _err("due_time must be HH:MM")
        created = now_iso()
        sha = hashlib.sha256(row["text"].encode()).hexdigest()
        sid = conn.execute("INSERT INTO sources (kind, name, content_sha, created_at) VALUES ('quick',NULL,?,?)",
                           (sha, created)).lastrowid
        tid = conn.execute(
            "INSERT INTO tasks (source_id, title, step, type, priority, due_date, due_time, reviewed, created_at)"
            " VALUES (?,?,?,?,?,?,?,1,?)", (sid, title.strip()[:200], step, ty, "Medium", due, clock, created)).lastrowid
        card.update(title=title.strip()[:200], step=step, type=ty, date=due, time=clock)
        conn.execute("UPDATE chat SET task_id=?, parsed=? WHERE id=?", (tid, json.dumps(card), cid))
        conn.commit()
        return jsonify({"task_id": tid, "chat": _row(conn.execute("SELECT * FROM chat WHERE id=?", (cid,)).fetchone())}), 201
    finally:
        conn.close()

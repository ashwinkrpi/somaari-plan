"""Ingest: upload files / paste text -> editable preview -> commit."""
import hashlib
import json
from datetime import date, datetime

from flask import Blueprint, jsonify, request

from .. import config, scheduler
from ..db import IST, now_iso
from .tasks import PRIORITIES, TYPES, err, norm_step, open_db, valid_date, valid_time
from ..ingest import mdparse, pipeline

bp = Blueprint("ingest", __name__)

SCHEDULES = ("week", "day", "in_text")
MAX_FILES, MAX_FILE_BYTES, MAX_TEXT = 20, 1_000_000, 100_000


class BadRequest(Exception):
    pass


def _date(v, what):
    if valid_date(v):
        return date.fromisoformat(v)
    raise BadRequest(f"{what} must be a date (YYYY-MM-DD)")


def _options(o, label):
    o = o if isinstance(o, dict) else {}
    sched = o.get("schedule", "week")
    if sched not in SCHEDULES:
        raise BadRequest(f"{label}: schedule must be week, day or in_text")
    anchor = None
    if sched != "in_text":
        anchor = _date(o.get("anchor_date"), f"{label}: date")
    per_day = o.get("per_day", 4)
    if not isinstance(per_day, int) or isinstance(per_day, bool) or not 1 <= per_day <= 20:
        raise BadRequest(f"{label}: tasks per day must be 1 to 20")
    return {"schedule": sched, "anchor": anchor, "per_day": per_day}


def normalise(text):
    return "\n".join(l.rstrip() for l in text.replace("\r\n", "\n").replace("\r", "\n").strip().split("\n"))


def _sha(text):
    return hashlib.sha256(normalise(text).encode()).hexdigest()


def _place(tasks, opt, today):
    """Fill due_date for tasks that have none (week/day: all of them)."""
    items = [{"priority": t["priority"], "date": date.fromisoformat(t["due_date"]) if t.get("due_date") else None}
             for t in tasks]
    for t, d in zip(tasks, scheduler.schedule(items, opt["schedule"], opt["anchor"], opt["per_day"], today)):
        t["due_date"] = d.isoformat()


@bp.post("/api/ingest/preview")
def preview():
    try:
        meta = json.loads(request.form.get("meta") or "{}")
    except ValueError:
        return err("meta must be JSON")
    if not isinstance(meta, dict):
        return err("meta must be JSON")
    files = [f for f in request.files.getlist("files") if f and f.filename]
    text = request.form.get("text") or ""
    if not files and not text.strip():
        return err("Add a .md file or paste some text.")
    if len(files) > MAX_FILES:
        return err(f"At most {MAX_FILES} files at a time.")
    if len(text) > MAX_TEXT:
        return err("Pasted text is too long.")
    try:
        today = _date(meta["today"], "today") if meta.get("today") else datetime.now(IST).date()
        fmeta = meta.get("files") if isinstance(meta.get("files"), list) else []
        inputs = []
        for i, f in enumerate(files):
            name = f.filename.replace("\\", "/").rsplit("/", 1)[-1]
            if not name.lower().endswith((".md", ".markdown", ".txt")):
                raise BadRequest(f"{name}: only .md files can be uploaded")
            data = f.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise BadRequest(f"{name}: file is larger than 1 MB")
            try:
                body = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise BadRequest(f"{name}: file is not UTF-8 text")
            inputs.append(("file", name, body, _options(fmeta[i] if i < len(fmeta) else {}, name)))
        if text.strip():
            inputs.append(("text", None, text, _options(meta.get("text"), "Pasted text")))
    except BadRequest as e:
        return err(str(e))

    cfg = config.load_ai()
    conn = open_db()
    sources, tasks, skipped = [], [], []
    info = {"mode": cfg["mode"], "notes": [], "cached": True, "provider": None, "fallback": None}
    try:
        for idx, (kind, name, body, opt) in enumerate(inputs):
            parsed = mdparse.parse(body, "md" if kind == "file" else "text")
            sha = _sha(body)
            need_dates = opt["schedule"] == "in_text"
            raw, ai = pipeline.analyse(parsed["candidates"], normalise(body), kind, sha, today.isoformat(), cfg,
                                       need_dates, conn)
            t, sk = pipeline.finalise(raw, cfg, today)
            if not need_dates:
                for x in t:
                    x["due_date"] = x["due_time"] = None
            _place(t, opt, today)
            for x in t:
                x["source"] = idx
            for x in sk:
                x["source"] = idx
            tasks += t
            skipped += sk
            sources.append({"index": idx, "kind": kind, "name": name, "content_sha": sha, "schedule": opt["schedule"],
                            "anchor_date": opt["anchor"].isoformat() if opt["anchor"] else None,
                            "per_day": opt["per_day"], "title": parsed["title"], "count": len(t), "skipped": len(sk)})
            info["cached"] = info["cached"] and ai["cached"]
            info["provider"] = ai["provider"] or info["provider"]
            info["fallback"] = ai["fallback"] or info["fallback"]
            info["notes"] += [n for n in ai["notes"] if n not in info["notes"]]
    finally:
        conn.close()
    return jsonify({"sources": sources, "tasks": tasks, "skipped": skipped, "ai": info, "today": today.isoformat()})


@bp.post("/api/ingest/commit")
def commit():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("sources"), list) or not isinstance(body.get("tasks"), list):
        return err("sources and tasks are required")
    try:
        today = datetime.now(IST).date()
        opts = []
        for s in body["sources"]:
            if not isinstance(s, dict) or s.get("kind") not in ("file", "text"):
                raise BadRequest("each source needs a kind (file or text)")
            if not isinstance(s.get("content_sha"), str) or not s["content_sha"]:
                raise BadRequest("each source needs content_sha")
            opts.append(_options(s, s.get("name") or "Pasted text"))
        rows = []
        for t in body["tasks"]:
            if not isinstance(t, dict) or not isinstance(t.get("title"), str) or not t["title"].strip():
                raise BadRequest("every task needs a title")
            src = t.get("source")
            if not isinstance(src, int) or isinstance(src, bool) or not 0 <= src < len(opts):
                raise BadRequest("task source is invalid")
            pr, ty = t.get("priority", "Medium"), t.get("type", "task")
            if pr not in PRIORITIES or ty not in TYPES:
                raise BadRequest("priority or type is invalid")
            if t.get("due_date"):
                _date(t["due_date"], "due_date")
            clock = t.get("due_time")
            if not valid_time(clock):
                raise BadRequest("due_time must be HH:MM")
            conf = t.get("ai_conf")
            try:
                step = norm_step(t.get("step"))
            except ValueError as e:
                raise BadRequest(str(e))
            rows.append({"title": t["title"].strip()[:200], "step": step, "type": ty, "priority": pr,
                         "due_date": t.get("due_date") or None, "due_time": clock, "source": src,
                         "ai_conf": conf if isinstance(conf, (int, float)) and not isinstance(conf, bool) else None,
                         "reviewed": 0 if t.get("reviewed") is False else 1})
    except BadRequest as e:
        return err(str(e))
    for i in range(len(opts)):      # the scheduler fills any task still without a date
        todo = [r for r in rows if r["source"] == i and not r["due_date"]]
        if todo:
            _place(todo, opts[i], today)
    conn = open_db()
    try:
        ids, created = [], now_iso()
        sids = []
        for s, o in zip(body["sources"], opts):
            cur = conn.execute(
                "INSERT INTO sources (kind, name, content_sha, schedule, anchor_date, per_day, created_at) VALUES (?,?,?,?,?,?,?)",
                (s["kind"], s.get("name"), s["content_sha"], o["schedule"],
                 o["anchor"].isoformat() if o["anchor"] else None, o["per_day"], created))
            sids.append(cur.lastrowid)
        order = {}
        for r in rows:
            order[(r["source"], r["due_date"], r["priority"])] = order.get((r["source"], r["due_date"], r["priority"]), 0) + 1
            cur = conn.execute(
                "INSERT INTO tasks (source_id, title, step, type, priority, due_date, due_time, sort_order, ai_conf, reviewed, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (sids[r["source"]], r["title"], r["step"], r["type"], r["priority"], r["due_date"], r["due_time"],
                 order[(r["source"], r["due_date"], r["priority"])], r["ai_conf"], r["reviewed"], created))
            ids.append(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"created": len(ids), "ids": ids}), 201

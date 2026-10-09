"""Candidates -> decisions. Code parses, Jev answers typed questions, code applies thresholds
and resolves dates. The LLM chain is used only for prose rewrite and mode=llm extraction."""
import hashlib
import json
import re
from datetime import date

from .. import dates, quickparse
from ..ai import questions as Q
from ..ai import router
from ..db import now_iso
from ..config import ROOT

PROMPTS = ROOT / "app" / "prompts"
PRI = {"H": "High", "M": "Medium", "L": "Low"}


def _prompt(name):
    return "\n".join(l for l in (PROMPTS / name).read_text().splitlines() if not l.startswith("# v"))


def _val(ans, qid, key):
    a = (ans or {}).get(qid) or {}
    return a.get(key)


def _prose_blocks(lines):
    """Groups (by step) of prose candidates worth rewriting."""
    by = {}
    for l in lines:
        by.setdefault(l["step"], []).append(l)
    out = []
    for block in by.values():
        prose = [l for l in block if l["from"] == "prose"]
        if prose and (len(prose) * 2 > len(block) or any(len(l["text"].split()) > 20 for l in prose)):
            out.append(prose)
    return out


def _rewrite(lines, cfg, notes):
    for block in _prose_blocks(lines):
        numbered = "\n".join(f"{i}. {l['text']}" for i, l in enumerate(block, 1))
        r = router.generate(_prompt("rewrite.txt") + "\n" + numbered, expect_json=True, version="rewrite-v1", cfg=cfg)
        res = (r.get("data") or {}).get("r") if r["ok"] and isinstance(r.get("data"), dict) else None
        if not isinstance(res, list) or len(res) != len(block):
            notes.append("Prose rewrite was unavailable; sentences are used as written.")
            continue
        for l, t in zip(block, res):
            if t is None:
                l["not_task"] = True
            elif isinstance(t, str) and t.strip():
                l["text"] = t.strip()[:120]


def _extract(text, today, cfg, notes):
    """mode=llm: full extraction in one LLM call. Returns lines or None."""
    r = router.generate(_prompt("extract.txt") + f"\n\nTODAY={today}\n" + text[:12000], expect_json=True,
                        version="extract-v1", cfg=cfg)
    items = (r.get("data") or {}).get("t") if r["ok"] and isinstance(r.get("data"), dict) else None
    if not isinstance(items, list):
        notes.append("The LLM could not extract tasks.")
        return None
    out = []
    for i, it in enumerate(items[:40], 1):
        if not isinstance(it, dict) or not str(it.get("n", "")).strip():
            continue
        d = it.get("d")
        out.append({"id": f"L{i}", "step": str(it.get("s") or "")[:30], "text": str(it["n"]).strip()[:120],
                    "notes": "", "from": "llm", "t": None, "p": PRI.get(it.get("p"), "Medium"), "pc": None,
                    "m": 1.0 if it.get("m") else 0.0, "d": None,
                    "date": d if isinstance(d, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) else None})
    return out


def _code_date(text, today):
    """Rule-based date/time for a plan line. Text in (brackets) is a side note, e.g. "(open till 11pm)", so it is ignored."""
    day, clock, _, _ = quickparse.find(re.sub(r"\([^)]*\)", " ", text), today)
    return day, clock


def _jev_lines(lines, today, cfg, need_dates, notes):
    """Returns (lines, ok, fallback). Mutates a copy with t/p/pc/m/d/parts."""
    out = [dict(l, t=0.0, p="Medium", pc=None, m=0.0, d=0.0) if l.get("not_task") else dict(l) for l in lines]
    ask = [l for l in out if "t" not in l]
    for batch in router.chunk(ask, 40):
        r = router.decide(Q.line_state(batch, today), Q.line_questions(batch), "lines", Q.VERSION, cfg)
        if not r["ok"]:
            return lines, False, r.get("fallback") or "off"
        for l in batch:
            i, a = l["id"], r["answers"]
            l["t"] = float(_val(a, "t_" + i, "noul") or 0.0)
            l["p"] = _val(a, "p_" + i, "choice") or "Medium"
            l["pc"] = _val(a, "p_" + i, "confidence")
            l["m"] = float(_val(a, "m_" + i, "noul") or 0.0)
            l["d"] = float(_val(a, "d_" + i, "noul") or 0.0)
    if need_dates:   # code reads dates first (finalise); Jev date parts only for lines the rules can't read
        dated = [l for l in out if l.get("d", 0) >= 0.5 and l["t"] >= cfg["thresholds"]["task_review"]
                 and _code_date(l["text"], date.fromisoformat(today))[0] is None]
        for batch in router.chunk(dated, 40):
            r = router.decide(Q.line_state(batch, today), Q.date_questions(batch), "dates", Q.VERSION, cfg)
            if not r["ok"]:
                notes.append("Dates could not be read; those tasks are scheduled by the plan rule.")
                break
            for l in batch:
                l["parts"] = {p: [_val(r["answers"], f"{p}_{l['id']}", "choice") or "none",
                                  _val(r["answers"], f"{p}_{l['id']}", "confidence") or 1.0] for p in dates.PARTS}
    return out, True, None


def _cache_key(content_sha, kind, need_dates, cfg):
    prov = "mock_jev" if router.mocking() else "jev"
    return hashlib.sha256(json.dumps([prov, cfg["jev_model"], Q.VERSION, content_sha, kind, need_dates,
                                      cfg["rewrite_prose"]]).encode()).hexdigest()


def analyse(candidates, text, kind, content_sha, today, cfg, need_dates, conn):
    """Returns (raw_lines, ai_info). raw_lines are JSON-safe and independent of thresholds."""
    notes = []
    info = {"mode": cfg["mode"], "provider": None, "fallback": None, "cached": False, "notes": notes}
    lines = [dict(c) for c in candidates]
    if not lines and cfg["mode"] != "llm":
        return [], info
    if cfg["mode"] == "jev":
        key = _cache_key(content_sha, kind, need_dates, cfg)
        row = conn.execute("SELECT response FROM ai_cache WHERE key=?", (key,)).fetchone()
        if row:
            info.update(provider="mock_jev" if router.mocking() else "jev", cached=True)
            return json.loads(row["response"]), info
        if cfg["rewrite_prose"]:
            _rewrite(lines, cfg, notes)
        out, ok, fb = _jev_lines(lines, today, cfg, need_dates, notes)
        if ok:
            info["provider"] = "mock_jev" if router.mocking() else "jev"
            conn.execute("INSERT OR REPLACE INTO ai_cache (key, provider, model, response, created_at) VALUES (?,?,?,?,?)",
                         (key, info["provider"], cfg["jev_model"], json.dumps(out), now_iso()))
            conn.commit()
            return out, info
        info["fallback"] = fb
        notes.append("Jev is unavailable; " + ("falling back to the LLM." if fb == "llm" else "tasks are listed without AI."))
        mode = fb
    else:
        mode = cfg["mode"]
    if mode == "llm" and cfg["generate_chain"]:
        ex = _extract(text, today, cfg, notes)
        if ex is not None:
            info["provider"] = "llm"
            return ex, info
    return lines, info    # off: code-only, no scores


def finalise(raw, cfg, today):
    """Apply thresholds and resolve dates. Returns (tasks, skipped)."""
    th = cfg["thresholds"]
    tasks, skipped = [], []
    for l in raw:
        t, flags = l.get("t"), []
        if t is not None and t < th["task_review"]:
            skipped.append({"id": l["id"], "step": l["step"], "text": l["text"], "notes": l.get("notes", ""), "t": t})
            continue
        if t is not None and t < th["task_accept"]:
            flags.append("Unsure this is a task")
        conf = [t] if t is not None else []
        pc = l.get("pc")
        if pc is not None:
            conf.append(pc)
            if pc < th["confidence_review"]:
                flags.append("Unsure about priority")
        due, clock = l.get("date"), None
        code_day, code_clock = _code_date(l["text"], today)   # rules first (AI_PROMPTS §3)
        if code_day:
            due, clock = code_day.isoformat(), code_clock
        elif l.get("parts"):
            d, clock, dc = dates.resolve({k: (v[0], v[1]) for k, v in l["parts"].items()}, today)
            if d:
                due = d.isoformat()
                conf.append(dc)
                if dc < th["confidence_review"]:
                    flags.append("Unsure about the date")
        if code_clock:
            clock = code_clock   # exact clock beats Jev's morning/afternoon; a time alone keeps the time, the scheduler picks the day
        meeting = (l.get("m") or 0) >= 0.5
        tasks.append({"id": l["id"], "step": l["step"], "title": l["text"], "notes": l.get("notes", ""),
                      "priority": l.get("p") if l.get("p") in ("High", "Medium", "Low") else "Medium",
                      "type": "meeting" if meeting else "task", "due_date": due, "due_time": clock,
                      "ai_conf": round(min(conf), 3) if conf else None, "flags": flags})
    return tasks, skipped

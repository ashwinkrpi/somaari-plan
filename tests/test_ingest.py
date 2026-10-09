import io
import json
from datetime import date
from pathlib import Path

from app import scheduler
from app.ai import jev
from app.ai.providers import mock
from app.dates import resolve
from app.ingest.mdparse import clean_step, parse

FIX = Path(__file__).parent / "fixtures"
PLAN = (FIX / "example-plan.md").read_text()
TODAY = date(2026, 10, 6)


def test_mdparse_golden():
    exp = json.loads((FIX / "example-plan.expected.json").read_text())
    got = parse(PLAN)["candidates"]
    assert len(got) == 21 == exp["count"]
    assert [{k: c[k] for k in ("step", "text", "from")} for c in got] == exp["candidates"]
    assert len({c["step"] for c in got}) == 6
    assert "Payments" in got[0]["text"] and "**" not in got[0]["text"] and "`" not in got[1]["text"]


def test_mdparse_rules():
    md = ("---\ntitle: x\n---\n# Plan\nIntro paragraph.\n<!-- hidden\n- no -->\n## Step 1: Do it (soon)\n"
          "- [ ] Real task:\n  - detail one\n- [x] Already done\n  - child of done\n| a | b |\n[only link](http://x.y)\n"
          "1. Numbered\n## Later: tidy up the very long heading names here\nJust text.\n")
    r = parse(md)
    assert r["title"] == "Plan"
    assert [(c["step"], c["text"], c["from"]) for c in r["candidates"]] == [
        ("Do it", "Real task", "list"), ("Do it", "Numbered", "list"),
        ("Tidy up the very long heading", "Tidy up the very long heading names here", "heading")]
    assert r["candidates"][0]["notes"] == "detail one"
    assert clean_step("Step 3: Launch (public)") == "Launch"


def test_mdparse_prose_only_for_pasted_text_without_lists():
    t = "Buy milk. Call Sam about the venue!\n\nSend the invoice."
    assert parse(t)["candidates"] == []                       # .md: paragraphs never count (D-06)
    assert [c["text"] for c in parse(t, "text")["candidates"]] == ["Buy milk.", "Call Sam about the venue!", "Send the invoice."]
    assert all(c["from"] == "prose" for c in parse(t, "text")["candidates"])
    assert parse("- one\n\nsome prose.", "text")["candidates"][0]["from"] == "list"
    assert len(parse("- one\n\nsome prose.", "text")["candidates"]) == 1


def _r(**p):
    return {k: (v, 0.9) for k, v in p.items()}


def test_dates_resolve():
    assert resolve(_r(mode="absolute", month="november", day="14", year="none"), TODAY)[0] == date(2026, 11, 14)
    assert resolve(_r(mode="absolute", month="january", day="5", year="none"), TODAY)[0] == date(2027, 1, 5)   # >31 days past
    assert resolve(_r(mode="absolute", month="october", day="1", year="none"), TODAY)[0] == date(2026, 10, 1)
    assert resolve(_r(mode="absolute", month="february", day="30", year="none"), TODAY)[0] is None
    assert resolve(_r(mode="relative", anchor="tomorrow", time_of_day="afternoon"), TODAY)[:2] == (date(2026, 10, 7), "15:00")
    assert resolve(_r(mode="relative", anchor="next_month_day", day="3"), TODAY)[0] == date(2026, 11, 3)
    assert resolve(_r(mode="relative", anchor="next_week"), TODAY)[0] == date(2026, 10, 12)
    assert resolve(_r(mode="relative", anchor="weekday", weekday="friday", week_offset="next"), TODAY)[0] == date(2026, 10, 16)
    assert resolve(_r(mode="relative", anchor="weekday", weekday="monday", week_offset="none"), TODAY)[0] == date(2026, 10, 12)
    assert resolve(_r(mode="none"), TODAY)[0] is None
    d, _, conf = resolve({"mode": ("relative", 0.9), "anchor": ("today", 0.3)}, TODAY)
    assert d == TODAY and conf == 0.3


def test_scheduler():
    mon = date(2026, 10, 12)
    ts = [{"priority": "Medium"} for _ in range(9)]
    ds = scheduler.schedule(ts, "week", mon, 4)
    assert ds[:4] == [mon] * 4 and ds[4] == date(2026, 10, 13) and ds[8] == date(2026, 10, 14)
    ts = [{"priority": "Low"}] * 12 + [{"priority": "High"}]
    assert scheduler.schedule(ts, "week", mon, 4)[-1] <= date(2026, 10, 14)      # High by Wednesday
    assert scheduler.schedule([{"priority": "Low"}] * 29, "week", mon, 1)[28] == date(2026, 11, 9)   # overflow
    assert scheduler.schedule([{"priority": "Low"}] * 3, "day", date(2026, 10, 20)) == [date(2026, 10, 20)] * 3
    mixed = [{"priority": "Low", "date": date(2026, 11, 1)}, {"priority": "Low"}]
    assert scheduler.schedule(mixed, "in_text", None, 4, today=TODAY) == [date(2026, 11, 1), date(2026, 11, 1)]   # carry forward
    lead = [{"priority": "Low", "date": None}, {"priority": "Low", "date": date(2026, 11, 1)},
            {"priority": "Low", "date": None}, {"priority": "Low", "date": date(2026, 11, 3)}, {"priority": "Low", "date": None}]
    assert scheduler.schedule(lead, "in_text", None, 4, today=TODAY) == [   # before the first date: week rule from today
        TODAY, date(2026, 11, 1), date(2026, 11, 1), date(2026, 11, 3), date(2026, 11, 3)]


# ---- routes ----
def _jev(t=0.9, p="Medium", conf=0.9, by_text=None, d=0.1):
    def responder(state, questions):
        if "lines" in state:
            ans = mock.fake_answers(questions, t=t, p=p, conf=conf, d=d)
            for ln in state["lines"]:
                if by_text and ln["text"] in by_text:
                    ans["t_" + ln["id"]]["noul"] = by_text[ln["text"]]
            return ans
        raise AssertionError("unexpected question set")
    return responder


def post(client, files=None, text="", meta=None):
    data = {"meta": json.dumps(meta or {"files": [{"schedule": "week", "anchor_date": "2026-10-12"}], "today": "2026-10-06"})}
    if files:
        data["files"] = [(io.BytesIO(b.encode()), n) for n, b in files]
    if text:
        data["text"] = text
    return client.post("/api/ingest/preview", data=data, content_type="multipart/form-data")


def test_preview_website_plan_no_llm_and_reupload_zero_calls(client):
    mock.RESPONDER = _jev()
    r = post(client, [("example-plan.md", PLAN)])
    j = r.get_json()
    assert r.status_code == 200 and len(j["tasks"]) == 21 and j["skipped"] == []
    assert all(t["due_date"] for t in j["tasks"]) and j["tasks"][0]["due_date"] == "2026-10-12"
    assert j["sources"][0]["schedule"] == "week" and j["ai"]["provider"] == "mock_jev"
    kinds = [c[0] for c in mock.CALLS]
    assert kinds and set(kinds) == {"jev"}                      # no LLM call, one Jev request (21 lines <= 40)
    n = len(mock.CALLS)
    from app.ai import router
    router._cache.clear()                                       # prove the persistent cache, not memory
    j2 = post(client, [("again.md", PLAN)]).get_json()
    assert len(mock.CALLS) == n and j2["ai"]["cached"] is True and len(j2["tasks"]) == 21


def test_thresholds_flag_and_skip(client):
    mock.RESPONDER = _jev(by_text={"Check whether the hall lends folding tables and shelves.": 0.2,
                                   "Check the hall calendar for free first Saturdays before calling.": 0.55}, conf=0.5)
    j = post(client, [("p.md", PLAN)]).get_json()
    assert [s["text"] for s in j["skipped"]] == ["Check whether the hall lends folding tables and shelves."]
    flagged = [t for t in j["tasks"] if "Unsure this is a task" in t["flags"]]
    assert len(flagged) == 1 and len(j["tasks"]) == 20
    assert all("Unsure about priority" in t["flags"] for t in j["tasks"])     # conf 0.5 < 0.6


def test_in_text_dates_and_meeting(client):
    def responder(state, questions):
        if "lines" in state and not any(k.startswith("mode_") for k in questions):
            ans = mock.fake_answers(questions, t=0.9, d=0.9)
            for ln in state["lines"]:
                ans["m_" + ln["id"]]["noul"] = 0.9 if "Call" in ln["text"] else 0.1
                ans["d_" + ln["id"]]["noul"] = 0.9 if "Nov" in ln["text"] else 0.1
            return ans
        ans = {}
        for qid in questions:
            part, lid = qid.rsplit("_", 1) if qid.startswith(("mode_", "month_", "day_", "year_", "anchor_", "weekday_")) else (None, None)
            val = {"mode": "absolute", "month": "november", "day": "14", "year": "none"}.get(part, "none")
            ans[qid] = {"type": "choice", "choice": val, "confidence": 0.95, "probabilities": {}}
        return ans
    mock.RESPONDER = responder
    meta = {"text": {"schedule": "in_text"}, "today": "2026-10-06"}
    j = post(client, text="- Call the bank on 14 Nov\n- Write notes", meta=meta).get_json()
    a, b = j["tasks"]
    assert a["due_date"] == "2026-11-14" and a["type"] == "meeting"
    assert b["due_date"] == "2026-11-14"          # undated carries the date of the dated line above (D-10)


def test_jev_down_falls_back_to_llm_extraction(client):
    def boom(s, q):
        raise jev.JevError("Jev is unreachable")
    mock.RESPONDER = boom
    mock.LLM_RESPONDER = lambda p: json.dumps({"t": [{"s": "Setup", "n": "Buy domain", "p": "H", "d": None, "m": False}]})
    j = post(client, [("p.md", "- anything\n")]).get_json()
    assert [t["title"] for t in j["tasks"]] == ["Buy domain"] and j["ai"]["fallback"] == "llm"
    assert j["tasks"][0]["priority"] == "High"


def test_prose_rewrite_only_for_prose(client):
    mock.RESPONDER = _jev()
    mock.LLM_RESPONDER = lambda p: json.dumps({"r": ["Buy milk", None]})
    j = post(client, text="I should buy milk tomorrow. It was sunny.", meta={"text": {"schedule": "day", "anchor_date": "2026-10-07"}}).get_json()
    assert [t["title"] for t in j["tasks"]] == ["Buy milk"] and len(j["skipped"]) == 1
    assert [c[0] for c in mock.CALLS].count("llm") == 1
    mock.CALLS.clear()
    post(client, [("l.md", "- a\n- b\n")])                       # lists never go to the LLM
    assert "llm" not in [c[0] for c in mock.CALLS]


def test_preview_validation(client):
    assert post(client).status_code == 400
    assert post(client, [("x.exe", "hi")]).status_code == 400
    assert post(client, [("x.md", "- a")], meta={"files": [{"schedule": "week"}]}).status_code == 400
    assert post(client, [("x.md", "- a")], meta={"files": [{"schedule": "nope"}]}).status_code == 400


def test_commit_saves_and_schedules(client):
    body = {"sources": [{"kind": "file", "name": "p.md", "content_sha": "abc", "schedule": "week", "anchor_date": "2026-10-12", "per_day": 2}],
            "tasks": [{"source": 0, "title": " One ", "priority": "High", "step": "S", "due_date": "2026-10-15", "reviewed": False},
                      {"source": 0, "title": "Two"}, {"source": 0, "title": "Three"}, {"source": 0, "title": "Four"}]}
    r = client.post("/api/ingest/commit", json=body)
    assert r.status_code == 201 and r.get_json()["created"] == 4
    rows = client.get("/api/tasks?from=2026-10-01&to=2026-12-01").get_json()
    by = {t["title"]: t for t in rows}
    assert by["One"]["due_date"] == "2026-10-15" and by["One"]["reviewed"] is False and by["One"]["source_id"]
    assert [by[k]["due_date"] for k in ("Two", "Three", "Four")] == ["2026-10-12", "2026-10-12", "2026-10-13"]
    bad = dict(body, tasks=[{"source": 3, "title": "x"}])
    assert client.post("/api/ingest/commit", json=bad).status_code == 400


def test_commit_step_trimmed_and_validated(client):
    src = [{"kind": "text", "content_sha": "abc", "schedule": "day", "anchor_date": "2026-10-12", "per_day": 4}]
    long = "x" * 40
    r = client.post("/api/ingest/commit", json={"sources": src, "tasks": [{"source": 0, "title": "A", "step": f" {long} "},
                                                                           {"source": 0, "title": "B", "step": ""}]})
    assert r.status_code == 201
    steps = {t["title"]: t["step"] for t in client.get("/api/tasks?from=2026-10-01&to=2026-10-31").get_json()}
    assert steps == {"A": "x" * 30, "B": None}
    bad = {"sources": src, "tasks": [{"source": 0, "title": "C", "step": ["x"]}]}
    assert client.post("/api/ingest/commit", json=bad).status_code == 400


def test_mdparse_heading_without_space():
    c = parse("##ideas\ncapture new ideas in the ideas md file", "text")["candidates"]
    assert [(x["step"], x["text"]) for x in c] == [("Ideas", "capture new ideas in the ideas md file")]
    p = parse("#tag line\n- a task", "text")   # "#x" is not a heading
    assert p["title"] == "" and [(x["step"], x["text"]) for x in p["candidates"]] == [("", "a task")]


def test_in_text_code_reads_dates_before_jev(client):
    """Jev flags dates but gives contradictory parts (as seen with a real trip plan); code rules win,
    Jev date parts are only asked for lines the rules can't read."""
    asked = []

    def responder(state, questions):
        if not any(k.startswith("mode_") for k in questions):
            ans = mock.fake_answers(questions, t=0.9, d=0.9)
            return ans
        asked.extend(ln["text"] for ln in state["lines"])
        return {qid: {"type": "choice", "choice": "absolute" if qid.startswith("mode_") else "none",
                      "confidence": 0.95, "probabilities": {}} for qid in questions}   # absolute, but no month
    mock.RESPONDER = responder
    meta = {"text": {"schedule": "in_text"}, "today": "2026-10-08"}
    text = ("- Withdraw cash by Thu 15 Oct\n- Leave Bangalore at 6:00am on Sat 17 Oct\n"
            "- Walk the cocoon market before 9am\n- Tea at Kamat Lokaruchi (open till 11pm)\n- Meet the reeler sometime soon")
    tasks = {t["title"]: t for t in post(client, text=text, meta=meta).get_json()["tasks"]}
    assert tasks["Withdraw cash by Thu 15 Oct"]["due_date"] == "2026-10-15"
    leave = tasks["Leave Bangalore at 6:00am on Sat 17 Oct"]
    assert (leave["due_date"], leave["due_time"]) == ("2026-10-17", "06:00")
    walk = tasks["Walk the cocoon market before 9am"]
    assert walk["due_time"] == "09:00" and walk["due_date"] == "2026-10-17"   # time only: day carried from the line above
    assert tasks["Tea at Kamat Lokaruchi (open till 11pm)"]["due_time"] is None   # bracketed note ignored
    assert asked == ["Walk the cocoon market before 9am", "Tea at Kamat Lokaruchi (open till 11pm)",
                     "Meet the reeler sometime soon"]   # Jev date parts only where the rules found no date

import re

from app.seed import seed
from app.db import connect

TS = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+05:30$")


def mk(client, **kw):
    body = {"title": "Write", "due_date": "2026-10-06", **kw}
    return client.post("/api/tasks", json=body)


def test_create_defaults_and_created_at(client):
    r = mk(client)
    assert r.status_code == 201
    t = r.get_json()
    assert t["priority"] == "Medium" and t["type"] == "task"
    assert TS.match(t["created_at"]) and t["closed_at"] is None and t["closed"] is False


def test_create_validation(client):
    assert client.post("/api/tasks", json={"due_date": "2026-10-06"}).status_code == 400
    assert mk(client, due_date="06-10-2026").status_code == 400
    assert mk(client, due_date="2026-02-30").status_code == 400
    assert mk(client, priority="Urgent").status_code == 400
    assert mk(client, due_time="25:00").status_code == 400
    assert mk(client, type="event").status_code == 400
    assert client.post("/api/tasks", data="x").status_code == 400


def test_list_range_and_order(client):
    mk(client, title="b", due_date="2026-10-07")
    mk(client, title="a", due_date="2026-10-05")
    mk(client, title="c", due_date="2026-10-20")
    r = client.get("/api/tasks?from=2026-10-05&to=2026-10-07").get_json()
    assert [t["title"] for t in r] == ["a", "b"]
    assert len(client.get("/api/tasks").get_json()) == 3
    assert client.get("/api/tasks?from=bad").status_code == 400


def test_close_and_reopen(client):
    tid = mk(client).get_json()["id"]
    t = client.patch(f"/api/tasks/{tid}", json={"closed": True}).get_json()
    assert TS.match(t["closed_at"]) and t["closed"] is True
    first = t["closed_at"]
    again = client.patch(f"/api/tasks/{tid}", json={"closed": True}).get_json()
    assert again["closed_at"] == first
    t = client.patch(f"/api/tasks/{tid}", json={"closed": False}).get_json()
    assert t["closed_at"] is None and t["closed"] is False


def test_reschedule_keeps_created_at(client):
    t = mk(client).get_json()
    n = client.patch(f"/api/tasks/{t['id']}", json={"due_date": "2026-10-09", "priority": "High", "title": " New "}).get_json()
    assert n["due_date"] == "2026-10-09" and n["priority"] == "High" and n["title"] == "New"
    assert n["created_at"] == t["created_at"]


def test_patch_errors(client):
    assert client.patch("/api/tasks/99", json={"title": "x"}).status_code == 404
    tid = mk(client).get_json()["id"]
    assert client.patch(f"/api/tasks/{tid}", json={"title": ""}).status_code == 400
    assert client.patch(f"/api/tasks/{tid}", json={"closed": "yes"}).status_code == 400
    assert client.patch(f"/api/tasks/{tid}", json={"due_time": "09:30"}).get_json()["due_time"] == "09:30"


def test_delete(client):
    tid = mk(client).get_json()["id"]
    assert client.delete(f"/api/tasks/{tid}").status_code == 204
    assert client.delete(f"/api/tasks/{tid}").status_code == 404
    assert client.get("/api/tasks").get_json() == []


def test_wal_and_seed(tmp_path):
    from app import create_app
    p = tmp_path / "s.db"
    app = create_app(db_path=p)
    conn = connect(p)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()
    assert seed(p) == 13
    assert seed(p) == 0
    c = app.test_client()
    tasks = c.get("/api/tasks?from=2026-10-05&to=2026-10-11").get_json()
    assert len(tasks) == 13
    assert sum(t["closed"] for t in tasks) == 3
    assert sum(t["due_date"] == "2026-10-06" for t in tasks) == 4


def test_board_move_persists(client):
    tid = mk(client, priority="Low").get_json()["id"]
    r = client.patch(f"/api/tasks/{tid}", json={"due_date": "2026-10-08", "priority": "High"})
    assert r.status_code == 200
    got = client.get("/api/tasks?from=2026-10-08&to=2026-10-08").get_json()
    assert [(t["id"], t["priority"]) for t in got] == [(tid, "High")]


def test_export_import_roundtrip_add_only(client, tmp_path):
    from app import create_app
    seed(tmp_path / "test.db")
    data = client.get("/api/export")
    assert data.status_code == 200 and "attachment" in data.headers["Content-Disposition"]
    j = data.get_json()
    assert j["app"] == "somaari-plan" and len(j["tasks"]) == 13
    # same db: add-only means nothing new, nothing lost
    r = client.post("/api/import", json=j).get_json()
    assert r == {"added": 0, "skipped": 13}
    assert len(client.get("/api/tasks").get_json()) == 13
    # fresh db: everything restored, including closed_at
    client.patch("/api/tasks/1", json={"closed": True})
    j = client.get("/api/export").get_json()
    c2 = create_app(db_path=tmp_path / "other.db").test_client()
    assert c2.post("/api/import", json=j).get_json() == {"added": 13, "skipped": 0}
    got = c2.get("/api/tasks").get_json()
    assert len(got) == 13 and sum(t["closed"] for t in got) == sum(bool(t["closed_at"]) for t in j["tasks"])


def test_import_rejects_bad_files(client):
    assert client.post("/api/import", json={"hello": 1}).status_code == 400
    assert client.post("/api/import", data="x").status_code == 400
    bad = {"app": "somaari-plan", "version": 1, "sources": [], "tasks": [{"title": "x", "due_date": "nope", "created_at": "t"}]}
    assert client.post("/api/import", json=bad).status_code == 400
    assert client.post("/api/import", json={**bad, "version": 9}).status_code == 400
    assert client.get("/api/tasks").get_json() == []


def test_done_list_search_and_reopen(client):
    def mk(title, step=None):
        return client.post("/api/tasks", json={"title": title, "due_date": "2026-10-06", "step": step}).get_json()["id"]
    a, b, c = mk("Buy domain", "Domain"), mk("Fix 100%_off typo"), mk("Still open")
    for tid in (a, b):
        assert client.patch(f"/api/tasks/{tid}", json={"closed": True}).status_code == 200
    done = client.get("/api/done").get_json()
    assert {t["id"] for t in done} == {a, b} and all(t["closed"] for t in done)
    assert [t["id"] for t in client.get("/api/done?q=domain").get_json()] == [a]      # title or step, any case
    assert [t["id"] for t in client.get("/api/done?q=0%_").get_json()] == [b]         # % and _ are literal
    assert client.get("/api/done?q=zzz").get_json() == []
    assert client.get("/api/done?limit=x").status_code == 400
    client.patch(f"/api/tasks/{a}", json={"closed": False})
    assert [t["id"] for t in client.get("/api/done").get_json()] == [b]


def test_edit_fields_and_delete(client):
    tid = client.post("/api/tasks", json={"title": "Byu milk", "due_date": "2026-10-06"}).get_json()["id"]
    r = client.patch(f"/api/tasks/{tid}", json={"title": " Buy milk ", "step": "Home", "priority": "High",
                                                "due_date": "2026-10-09", "due_time": "18:30"}).get_json()
    assert (r["title"], r["step"], r["priority"], r["due_date"], r["due_time"]) == ("Buy milk", "Home", "High", "2026-10-09", "18:30")
    r = client.patch(f"/api/tasks/{tid}", json={"step": "", "due_time": None}).get_json()
    assert r["step"] is None and r["due_time"] is None
    assert client.patch(f"/api/tasks/{tid}", json={"title": "  "}).status_code == 400
    assert client.delete(f"/api/tasks/{tid}").status_code == 204
    assert client.delete(f"/api/tasks/{tid}").status_code == 404


def test_reopen_never_in_the_past(client):
    from datetime import datetime, timedelta
    from app.db import IST
    today = datetime.now(IST).date()
    iso = lambda n: (today + timedelta(days=n)).isoformat()

    def done_task(due):
        tid = client.post("/api/tasks", json={"title": "t", "due_date": due}).get_json()["id"]
        client.patch(f"/api/tasks/{tid}", json={"closed": True})
        return tid
    a = done_task(iso(-5))                                   # past → today
    assert client.patch(f"/api/tasks/{a}", json={"closed": False}).get_json()["due_date"] == iso(0)
    b = done_task(iso(-5))                                   # past → chosen future day
    r = client.patch(f"/api/tasks/{b}", json={"closed": False, "due_date": iso(3)}).get_json()
    assert (r["closed"], r["due_date"]) == (False, iso(3))
    c = done_task(iso(-5))                                   # chosen day in the past → refused, still done
    assert client.patch(f"/api/tasks/{c}", json={"closed": False, "due_date": iso(-1)}).status_code == 400
    assert client.get(f"/api/done").get_json()[0]["id"] in (a, b, c) and any(t["id"] == c for t in client.get("/api/done").get_json())
    d = done_task(iso(4))                                    # future due date is kept
    assert client.patch(f"/api/tasks/{d}", json={"closed": False}).get_json()["due_date"] == iso(4)
    e = client.post("/api/tasks", json={"title": "open", "due_date": iso(-2)}).get_json()["id"]
    assert client.patch(f"/api/tasks/{e}", json={"closed": False}).get_json()["due_date"] == iso(-2)   # already open: untouched


def test_moves_logged_and_counted(client):
    # D-07: every due_date change is logged; /api/moved counts tasks moved out of a range
    a = mk(client, due_date="2026-10-06").get_json()["id"]
    b = mk(client, due_date="2026-10-07").get_json()["id"]
    mk(client, due_date="2026-10-08")
    client.patch(f"/api/tasks/{a}", json={"due_date": "2026-10-14"})                # out of the week
    client.patch(f"/api/tasks/{b}", json={"due_date": "2026-10-09"})                # moved within the week
    client.patch(f"/api/tasks/{b}", json={"priority": "High", "due_date": "2026-10-09"})  # same date: not a move
    rng = "from=2026-10-05&to=2026-10-11"
    assert client.get(f"/api/moved?{rng}").get_json() == {"moved": 1}
    client.patch(f"/api/tasks/{a}", json={"due_date": "2026-10-10"})                # moved back in
    assert client.get(f"/api/moved?{rng}").get_json() == {"moved": 0}
    client.patch(f"/api/tasks/{b}", json={"due_date": "2026-10-20"})
    assert client.get(f"/api/moved?{rng}").get_json() == {"moved": 1}
    conn = connect(client.application.config["DB_PATH"])
    assert conn.execute("SELECT COUNT(*) FROM task_moves").fetchone()[0] == 4
    client.delete(f"/api/tasks/{b}")                                                 # log goes with the task
    assert conn.execute("SELECT COUNT(*) FROM task_moves").fetchone()[0] == 2
    conn.close()
    assert client.get("/api/moved?from=bad&to=2026-10-11").status_code == 400


def test_export_import_carries_moves(client, tmp_path):
    from app import create_app
    tid = mk(client, due_date="2026-10-06").get_json()["id"]
    client.patch(f"/api/tasks/{tid}", json={"due_date": "2026-10-13"})
    j = client.get("/api/export").get_json()
    assert [(m["from_date"], m["to_date"]) for m in j["moves"]] == [("2026-10-06", "2026-10-13")]
    c2 = create_app(db_path=tmp_path / "other.db").test_client()
    mk(c2, title="Already here")                                   # shifts ids, so the move must be remapped
    assert c2.post("/api/import", json=j).get_json() == {"added": 1, "skipped": 0}
    assert c2.get("/api/moved?from=2026-10-05&to=2026-10-11").get_json() == {"moved": 1}
    assert c2.post("/api/import", json=j).get_json() == {"added": 0, "skipped": 1}  # no duplicate log rows
    conn = connect(tmp_path / "other.db")
    assert conn.execute("SELECT COUNT(*) FROM task_moves").fetchone()[0] == 1
    conn.close()
    old = {k: v for k, v in j.items() if k != "moves"}                # older backups have no moves key
    c3 = create_app(db_path=tmp_path / "third.db").test_client()
    assert c3.post("/api/import", json=old).get_json() == {"added": 1, "skipped": 0}
    bad = {**j, "moves": [{"task_id": "x"}]}
    assert c3.post("/api/import", json=bad).status_code == 400

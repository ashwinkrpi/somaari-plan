from datetime import date

import pytest

from app.ai import jev
from app.ai.providers import mock, remote
from app.quickparse import parse

TODAY = date(2026, 10, 6)

TABLE = [
    ("Meeting tomorrow afternoon to review the site draft", "2026-10-07", "15:00", "meeting"),
    ("Check Cloudflare Pages analytics on 3rd of next month", "2026-11-03", None, "task"),
    ("Call the bank at 4pm tomorrow", "2026-10-07", "16:00", "task"),
    ("Dentist on 14 Nov at 10:30am", "2026-11-14", "10:30", "task"),
    ("Plan next sprint next week", "2026-10-12", None, "task"),
    ("Pay rent tonight", "2026-10-06", "20:00", "task"),
    ("Send report friday", "2026-10-09", None, "task"),
    ("Review draft Nov 2", "2026-11-02", None, "task"),
]


@pytest.mark.parametrize("text,d,t,ty", TABLE)
def test_quickparse_table_zero_ai(client, text, d, t, ty):
    p = parse(text, TODAY)
    assert (p["date"].isoformat(), p["time"], p["type"]) == (d, t, ty)
    r = client.post("/api/quick", json={"text": text, "today": "2026-10-06"})
    c = r.get_json()["parsed"]
    assert (c["date"], c["time"], c["type"], c["source"]) == (d, t, ty, "rules")
    assert mock.CALLS == []


def test_quickparse_titles():
    assert parse("Call the bank at 4pm tomorrow", TODAY)["title"] == "Call the bank"
    assert parse("Dentist on 14 Nov at 10:30am", TODAY)["title"] == "Dentist"
    assert parse("Check Cloudflare Pages analytics on 3rd of next month", TODAY)["title"] == "Check Cloudflare Pages analytics"
    assert parse("Plan next sprint next week", TODAY)["week"] is True
    assert parse("Buy milk", TODAY)["matched"] is False


def test_miss_uses_jev_date_parts(client):
    def responder(state, questions):
        assert "m_L1" in questions and "mode_L1" in questions
        ans = mock.fake_answers(questions, p="none", conf=0.95)
        ans["mode_L1"]["choice"] = "relative"
        ans["anchor_L1"]["choice"] = "tomorrow"
        ans["m_L1"]["noul"] = 0.9
        return ans
    mock.RESPONDER = responder
    c = client.post("/api/quick", json={"text": "Lunch with Sam, day after the launch", "today": "2026-10-06"}).get_json()["parsed"]
    assert (c["source"], c["date"], c["type"]) == ("jev", "2026-10-07", "meeting")
    assert c["title"] == "Lunch with Sam, day after the launch"
    assert [k for k, _ in mock.CALLS] == ["jev"]


def test_miss_jev_down_defaults_today_no_llm(client):
    def boom(s, q):
        raise jev.JevError("down")
    mock.RESPONDER = boom
    c = client.post("/api/quick", json={"text": "Buy milk", "today": "2026-10-06"}).get_json()["parsed"]
    assert c["source"] == "none" and c["date"] == "2026-10-06" and c["note"]
    assert all(k == "jev" for k, _ in mock.CALLS)


def test_log_and_add(client):
    assert client.post("/api/quick", json={"text": "  "}).status_code == 400
    a = client.post("/api/quick", json={"text": "Call Sam at 4pm tomorrow", "today": "2026-10-06"}).get_json()
    client.post("/api/quick", json={"text": "Dentist on 14 Nov", "today": "2026-10-06"})
    log = client.get("/api/quick").get_json()
    assert [x["text"] for x in log] == ["Call Sam at 4pm tomorrow", "Dentist on 14 Nov"]
    r = client.post(f"/api/quick/{a['id']}/add", json={"type": "meeting"})
    assert r.status_code == 201
    tid = r.get_json()["task_id"]
    t = [x for x in client.get("/api/tasks?from=2026-10-07&to=2026-10-07").get_json() if x["id"] == tid][0]
    assert (t["title"], t["type"], t["due_time"], t["due_date"]) == ("Call Sam", "meeting", "16:00", "2026-10-07")
    assert [x["text"] for x in client.get("/api/quick").get_json()] == ["Dentist on 14 Nov"]   # added cards hidden
    assert client.get("/api/quick?all=1").get_json()[0]["task_id"] == tid                    # but kept as history
    assert client.post(f"/api/quick/{a['id']}/add", json={}).status_code == 409
    assert client.post("/api/quick/999/add", json={}).status_code == 404


def test_ai_fully_down_nothing_lost(client):
    """Jev and the LLM both fail: quick add still gives a card, preview still lists code-parsed tasks."""
    def boom(s, q):
        raise jev.JevError("down")
    def llm_boom(p):
        raise remote.ProviderError("down")
    mock.RESPONDER, mock.LLM_RESPONDER = boom, llm_boom
    c = client.post("/api/quick", json={"text": "Buy milk", "today": "2026-10-06"}).get_json()["parsed"]
    assert c["title"] == "Buy milk" and c["note"]
    import io, json
    data = {"meta": json.dumps({"files": [{"schedule": "week", "anchor_date": "2026-10-12"}], "today": "2026-10-06"}),
            "files": [(io.BytesIO(b"## Setup\n- Buy domain\n- Write copy\n"), "p.md")]}
    r = client.post("/api/ingest/preview", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    assert [t["title"] for t in r.get_json()["tasks"]] == ["Buy domain", "Write copy"]


def test_add_with_step_and_steps_list(client):
    a = client.post("/api/quick", json={"text": "Buy domain tomorrow", "today": "2026-10-06"}).get_json()
    assert client.post(f"/api/quick/{a['id']}/add", json={"step": 5}).status_code == 400
    r = client.post(f"/api/quick/{a['id']}/add", json={"step": "  Domain   setup "})
    assert r.status_code == 201 and r.get_json()["chat"]["parsed"]["step"] == "Domain setup"
    t = client.get("/api/tasks?from=2026-10-01&to=2026-10-31").get_json()
    assert [x["step"] for x in t if x["id"] == r.get_json()["task_id"]] == ["Domain setup"]
    b = client.post("/api/quick", json={"text": "Call Sam tomorrow", "today": "2026-10-06"}).get_json()
    tid = client.post(f"/api/quick/{b['id']}/add", json={"step": "   "}).get_json()["task_id"]
    assert [x["step"] for x in client.get("/api/tasks?from=2026-10-01&to=2026-10-31").get_json() if x["id"] == tid] == [None]
    assert client.get("/api/steps").get_json() == ["Domain setup"]


def test_discard_and_clear_pending(client):
    ids = [client.post("/api/quick", json={"text": t, "today": "2026-10-06"}).get_json()["id"]
           for t in ("Buy milk tomorrow", "Call Sam at 4pm", "Dentist on 14 Nov")]
    tid = client.post(f"/api/quick/{ids[0]}/add", json={}).get_json()["task_id"]
    assert client.delete(f"/api/quick/{ids[0]}").status_code == 409            # added: stays
    assert client.delete(f"/api/quick/{ids[1]}").status_code == 204
    assert client.delete(f"/api/quick/{ids[1]}").status_code == 404
    assert [x["id"] for x in client.get("/api/quick").get_json()] == [ids[2]]
    assert client.delete("/api/quick").get_json() == {"discarded": 1}
    assert client.get("/api/quick").get_json() == []
    assert [x["id"] for x in client.get("/api/quick?all=1").get_json()] == [ids[0]]
    assert any(t["id"] == tid for t in client.get("/api/tasks").get_json())     # task untouched

"""Plugin host (D-21): works with no plugins, draws a fake plugin's settings, runs its actions."""
import tomllib

import pytest

from app import create_app, plugins
from app.plugins import PluginError


class Fake:
    api_version = 1
    name = "fake"
    title = "Fake"
    description = "A test plugin."
    defaults = {"enabled": False, "at": "08:00"}
    fields = [{"key": "enabled", "label": "On", "type": "bool"}, {"key": "at", "label": "At", "type": "time"}]
    actions = [{"id": "ping", "label": "Ping"}, {"id": "boom", "label": "Boom"}, {"id": "crash", "label": "Crash"}]

    def __init__(self):
        self.started = []

    def validate(self, v):
        if not isinstance(v["enabled"], bool):
            raise ValueError("enabled must be true or false.")
        if v["at"] in ("", "nope"):
            raise ValueError("At must be a time.")
        return {"enabled": v["enabled"], "at": v["at"]}

    def status(self, ctx):
        return ["Key: set"]

    def run_action(self, ctx, action):
        if action == "boom":
            raise PluginError("Telegram said no.")
        if action == "crash":
            raise RuntimeError("https://api.example/bot123:SECRET/x")
        return f"{len(ctx.tasks())} open"

    def start(self, ctx):
        self.started.append(ctx.name)


@pytest.fixture
def fake():
    return Fake()


@pytest.fixture
def fclient(tmp_path, fake):
    return create_app(db_path=tmp_path / "t.db", plugin_list=[fake]).test_client()


def test_no_plugins_by_default(client):
    assert client.get("/api/plugins").get_json() == []
    assert client.put("/api/plugins/telegram", json={}).status_code == 404


def test_discovery_is_off_in_tests():
    assert plugins.discover() == []


def test_list_shows_fields_values_status(fclient):
    [p] = fclient.get("/api/plugins").get_json()
    assert p["name"] == "fake" and p["values"] == {"enabled": False, "at": "08:00"}
    assert p["status"] == ["Key: set"] and [a["id"] for a in p["actions"]] == ["ping", "boom", "crash"]


def test_save_writes_own_section_only(fclient, tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[ui]\ndate_format = "yyyy-mm-dd"\n')
    r = fclient.put("/api/plugins/fake", json={"enabled": True, "at": "21:30"})
    assert r.status_code == 200 and r.get_json()["values"] == {"enabled": True, "at": "21:30"}
    data = tomllib.loads(cfg.read_text())
    assert data["plugins"]["fake"] == {"enabled": True, "at": "21:30"}
    assert data["ui"]["date_format"] == "yyyy-mm-dd"


def test_save_rejects_bad_and_unknown_values(fclient):
    assert fclient.put("/api/plugins/fake", json={"at": "nope"}).get_json()["error"] == "At must be a time."
    assert fclient.put("/api/plugins/fake", json={"other": 1}).status_code == 400
    assert fclient.put("/api/plugins/fake", json=[1]).status_code == 400


def test_actions(fclient):
    fclient.post("/api/tasks", json={"title": "a", "due_date": "2026-11-24"})
    assert fclient.post("/api/plugins/fake/actions/ping").get_json() == {"ok": True, "message": "1 open"}
    assert fclient.post("/api/plugins/fake/actions/boom").get_json() == {"ok": False, "message": "Telegram said no."}
    crash = fclient.post("/api/plugins/fake/actions/crash").get_json()
    assert crash["ok"] is False and "SECRET" not in crash["message"]
    assert fclient.post("/api/plugins/fake/actions/nope").status_code == 404


def test_context_tasks_filters(tmp_path, fake):
    app = create_app(db_path=tmp_path / "t.db", plugin_list=[fake])
    c = app.test_client()
    for d in ("2026-11-23", "2026-11-24", "2026-11-25"):
        c.post("/api/tasks", json={"title": d, "due_date": d})
    tid = c.post("/api/tasks", json={"title": "done", "due_date": "2026-11-24"}).get_json()["id"]
    c.patch(f"/api/tasks/{tid}", json={"closed": True})
    ctx = app.config["PLUGINS"]["fake"][1]
    assert [t["title"] for t in ctx.tasks("2026-11-24", "2026-11-24")] == ["2026-11-24"]
    assert [t["title"] for t in ctx.tasks(None, "2026-11-23")] == ["2026-11-23"]
    assert len(ctx.tasks("2026-11-24", "2026-11-24", open_only=False)) == 2
    assert ctx.data_dir == tmp_path / "plugins" / "fake"


def test_start_services(tmp_path, fake):
    app = create_app(db_path=tmp_path / "t.db", plugin_list=[fake])
    plugins.start_services(app)
    assert fake.started == ["fake"]


def test_incompatible_plugin_is_skipped(monkeypatch, fake):
    class EP:
        name = "old"

        def load(self):
            fake.api_version = 0
            return fake

    class Broken:
        name = "broken"

        def load(self):
            raise ImportError("missing")

    monkeypatch.delenv("SOMAARI_NO_PLUGINS")
    monkeypatch.setattr(plugins, "entry_points", lambda group: [EP(), Broken()])
    assert plugins.discover() == []

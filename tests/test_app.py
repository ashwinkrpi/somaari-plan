import socket

import pytest

from app.__main__ import main
from app.config import ConfigError, resolve_server


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.get_json() == {"ok": True}


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200 and b"somaari-plan" in r.data


def test_precedence(tmp_path):
    t = tmp_path / "c.toml"
    t.write_text('[server]\nhost="1.1.1.1"\nport=9001\n')
    assert resolve_server(toml_path=t, env={})[:2] == ("1.1.1.1", 9001)
    assert resolve_server(toml_path=t, env={"SOMAARI_PORT": "9002"})[1] == 9002
    assert resolve_server(None, 9003, env={"SOMAARI_PORT": "9002"}, toml_path=t)[1] == 9003
    assert resolve_server(toml_path=tmp_path / "none.toml", env={})[:2] == ("0.0.0.0", 8710)


def test_bad_port():
    with pytest.raises(ConfigError):
        resolve_server(None, 80, env={})


def test_busy_port(capsys):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()
    port = s.getsockname()[1]
    with pytest.raises(SystemExit) as e:
        main(["--host", "127.0.0.1", "--port", str(port)])
    s.close()
    assert str(port) in str(e.value)


def test_shell_assets(client):
    html = client.get("/").data.decode()
    for r in ("today", "calendar", "dashboard", "new"):
        assert f'data-route="{r}"' in html and f'id="page-{r}"' in html
    for p in ("/css/app.css", "/js/app.js", "/fonts/BricolageGrotesque-var.woff2"):
        assert client.get(p).status_code == 200


def test_stage3_assets_and_toggle(client):
    html = client.get("/").data.decode()
    for hook in ('class="list-host"', 'data-view="day"', 'data-view="week"', 'data-view="month"', 'class="cal-body"'):
        assert hook in html
    for p in ("/js/store.js", "/js/today.js", "/js/calendar.js", "/js/dates.js", "/js/dom.js"):
        assert client.get(p).status_code == 200
    t = client.post("/api/tasks", json={"title": "x", "due_date": "2026-10-07"}).get_json()
    done = client.patch(f"/api/tasks/{t['id']}", json={"closed": True}).get_json()
    assert done["closed"] and done["closed_at"]
    rng = client.get("/api/tasks?from=2026-10-07&to=2026-10-07").get_json()
    assert rng[0]["closed"] is True

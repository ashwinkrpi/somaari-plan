import io
import urllib.error

import pytest

from app import config
from app.ai import jev, router
from app.ai.providers import mock

QS = {"t_L1": {"type": "noul", "instructions": "x"},
      "p_L1": {"type": "choice", "instructions": "y", "criteria": {"High": None, "Medium": None, "Low": None}}}


def test_decide_mock_and_cache():
    mock.RESPONDER = lambda s, q: mock.fake_answers(q, t=0.8, p="High")
    r = router.decide("s", QS)
    assert r["ok"] and r["provider"] == "mock_jev" and r["answers"]["p_L1"]["choice"] == "High"
    assert router.decide("s", QS)["cached"] is True
    assert len(mock.CALLS) == 1
    assert router.decide("s", QS, version="2")["cached"] is False


def test_mock_jev_missing_fixture_fails_loudly():
    with pytest.raises(AssertionError, match="missing fixture"):
        router.decide("no fixture", QS)


def test_decide_mode_off_and_llm():
    for m in ("off", "llm"):
        r = router.decide("s", QS, cfg=dict(config.load_ai(), mode=m))
        assert not r["ok"] and r["fallback"] == m


def test_jev_down_falls_back_as_configured():
    def boom(s, q):
        raise jev.JevError("Jev is unreachable")
    mock.RESPONDER = boom
    # RESPONDER raising JevError is routed through decide's handler
    assert router.decide("s", QS)["fallback"] == "llm"
    cfg = dict(config.load_ai(), generate_chain=[])
    assert router.decide("s", QS, cfg=cfg)["fallback"] == "off"


def test_generate_chain_and_json_retry():
    outs = iter(["not json", '{"a": 1}'])
    mock.LLM_RESPONDER = lambda p: next(outs)
    r = router.generate("p", expect_json=True)
    assert r["ok"] and r["data"] == {"a": 1} and len(mock.CALLS) == 2
    r = router.generate("p", cfg=dict(config.load_ai(), generate_chain=[]))
    assert not r["ok"]


def test_generate_all_bad():
    mock.LLM_RESPONDER = lambda p: "nope"
    r = router.generate("q", expect_json=True, cfg=dict(config.load_ai(), generate_chain=["openrouter_free", "gemini_api"]))
    assert not r["ok"] and len(mock.CALLS) == 4


def test_jev_retries_429_then_succeeds(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    waits, n = [], {"i": 0}
    monkeypatch.setattr(jev, "_sleep", waits.append)

    def post(body, key, timeout):
        n["i"] += 1
        if n["i"] < 3:
            raise urllib.error.HTTPError("u", 429, "x", {"retry-after": "1"}, io.BytesIO())
        return {"answers": {"a": {}}, "usage": {"input_tokens": 5}}
    monkeypatch.setattr(jev, "_post", post)
    assert jev.call("s", {}, "m")[1]["input_tokens"] == 5
    assert waits == [1.0, 1.0]
    n["i"] = -10
    with pytest.raises(jev.JevError):
        jev.call("s", {}, "m")


def test_jev_requires_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(jev.JevError):
        jev.call("s", {}, "m")


def test_log_has_no_content(tmp_path):
    mock.RESPONDER = lambda s, q: mock.fake_answers(q)
    router.decide("secret state text", QS)
    log = (tmp_path / "ai.log").read_text()
    assert "secret" not in log and "mock_jev" in log


def test_status_and_test_endpoints(client, monkeypatch):
    s = client.get("/api/ai/status").get_json()
    assert s["mode"] == "jev" and s["generate_chain"][0]["id"] == "openrouter_free"
    assert "key" not in str(s).lower()
    assert client.post("/api/ai/test", json={"provider": "jev"}).get_json()["ok"]
    assert client.post("/api/ai/test", json={"provider": "openrouter_free"}).get_json()["ok"]
    assert client.post("/api/ai/test", json={"provider": "bogus"}).status_code == 400


def test_settings_roundtrip(client, tmp_path):
    g = client.get("/api/settings").get_json()
    assert g["ai"]["mode"] == "jev" and g["server"]["port"] == 8710
    r = client.put("/api/settings", json={"ai": {"mode": "llm", "generate_chain": ["gemini_api", "openrouter_free"],
                                                  "thresholds": {"task_accept": 0.8}}})
    assert r.status_code == 200
    ai = client.get("/api/settings").get_json()["ai"]
    assert ai["mode"] == "llm" and ai["generate_chain"] == ["gemini_api", "openrouter_free"]
    assert ai["thresholds"]["task_accept"] == 0.8 and ai["thresholds"]["task_review"] == 0.4
    assert "[ai.thresholds]" in (tmp_path / "config.toml").read_text()


def test_settings_keeps_server_section(client, tmp_path):
    (tmp_path / "config.toml").write_text('[server]\nport = 9000\n')
    client.put("/api/settings", json={"ai": {"mode": "off"}})
    assert client.get("/api/settings").get_json()["server"]["port"] == 9000


@pytest.mark.parametrize("bad", [
    {"mode": "claude"}, {"generate_chain": ["claude"]}, {"generate_chain": ["gemini_api", "gemini_api"]},
    {"thresholds": {"task_accept": 2}}, {"thresholds": {"task_accept": 0.3}}, {"thresholds": {"x": 1}},
    {"timeout_s": 1}, {"jev_model": "a b;"}, {"rewrite_prose": "yes"},
])
def test_settings_rejects_bad(client, bad):
    assert client.put("/api/settings", json={"ai": bad}).status_code == 400


def test_settings_never_returns_keys(client, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "sekret-value")
    assert "sekret-value" not in client.get("/api/settings").get_data(as_text=True)
    assert "sekret-value" not in client.get("/api/ai/status").get_data(as_text=True)


def test_openrouter_logs_answering_model(tmp_path, monkeypatch):
    import json
    from app.ai.providers import remote
    monkeypatch.delenv("SOMAARI_AI_MOCK")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    replies = [{"model": "meta-llama/llama-3.3-70b:free", "usage": {"prompt_tokens": 12},
                "choices": [{"message": {"content": "ok"}}]}]
    monkeypatch.setattr(remote, "_post", lambda url, h, body, t: replies.pop(0) if replies else (_ for _ in ()).throw(remote.ProviderError("HTTP 500")))
    cfg = dict(config.load_ai(), generate_chain=["openrouter_free"])
    r = router.generate("ping", cfg=cfg, version="t-model")
    assert r["ok"] and r["text"] == "ok" and type(r["text"]) is str and r["model"] == "meta-llama/llama-3.3-70b:free"
    assert not router.generate("ping2", cfg=cfg, version="t-model")["ok"]
    lines = [json.loads(x) for x in (tmp_path / "ai.log").read_text().splitlines()]
    assert lines[0] == {**lines[0], "provider": "openrouter_free", "model": "meta-llama/llama-3.3-70b:free", "input_tokens": 12, "ok": True}
    assert lines[-1]["model"] == "openrouter/free" and lines[-1]["ok"] is False
    assert "ping" not in (tmp_path / "ai.log").read_text()


def test_settings_date_format(client, tmp_path):
    assert client.get("/api/settings").get_json()["ui"] == {"date_format": "dd/mm/yyyy"}   # default
    assert client.get("/api/settings").get_json()["date_formats"] == ["dd/mm/yyyy", "mm/dd/yyyy", "yyyy-mm-dd"]
    client.put("/api/settings", json={"ai": {"mode": "off"}})
    r = client.put("/api/settings", json={"ui": {"date_format": "yyyy-mm-dd"}})       # ui alone keeps [ai]
    assert r.status_code == 200 and r.get_json()["ui"]["date_format"] == "yyyy-mm-dd" and r.get_json()["ai"]["mode"] == "off"
    client.put("/api/settings", json={"ai": {"mode": "jev"}})                          # ai alone keeps [ui]
    assert client.get("/api/settings").get_json()["ui"]["date_format"] == "yyyy-mm-dd"
    for bad in ({"date_format": "dd-mm-yy"}, {"colour": "red"}, "x"):
        assert client.put("/api/settings", json={"ui": bad}).status_code == 400
    # a bad ui value writes nothing, not even a valid ai part
    assert client.put("/api/settings", json={"ai": {"mode": "off"}, "ui": {"date_format": "?"}}).status_code == 400
    assert client.get("/api/settings").get_json()["ai"]["mode"] == "jev"
    assert "[ui]" in (tmp_path / "config.toml").read_text()

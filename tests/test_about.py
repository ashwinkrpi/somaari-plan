import re

from somaari_about import load_debug_fields

from app import __version__, config


def test_about_has_every_debug_field_in_order(client):
    j = client.get("/api/about").get_json()
    keys = [f["key"] for f in load_debug_fields()]
    assert sorted(j["info"]) == sorted(keys)   # JSON keys are sorted; order comes from fields + text
    assert [f["key"] for f in j["fields"]] == keys
    assert j["info"]["app_name"] == "somaari-plan" and j["info"]["app_version"] == __version__
    lines = j["text"].splitlines()
    assert lines[0] == "[somaari debug info]" and j["text"].endswith("\n")
    assert [l.split(": ", 1)[0] for l in lines[1:1 + len(keys)]] == keys
    assert lines[1 + len(keys)] == "[developer]"
    assert j["developer"]["name"]


def test_about_reports_ai_names(client):
    info = client.get("/api/about").get_json()["info"]
    assert info["ai_provider"] == "jev (primary), openrouter_free (fallback)"
    assert info["ai_model"] == "jev-latest, openrouter/free"


def test_about_contains_no_secrets(client, monkeypatch, tmp_path):
    secrets = ["sk-or-v1-" + "a1" * 24, "ts_live_" + "Zx9" * 15, "AIza" + "B" * 35]
    monkeypatch.setenv("TYPESAFE_API_KEY", secrets[0])
    monkeypatch.setenv("OPENROUTER_API_KEY", secrets[1])
    monkeypatch.setenv("GEMINI_API_KEY", secrets[2])
    config.save_ai(dict(config.load_ai(), jev_model=secrets[1]))   # even a key pasted into a name field
    body = client.get("/api/about").get_data(as_text=True)
    for s in secrets:
        assert s not in body
    assert not re.search(r"(?i)(api[_-]?key|token|password)\s*[=:]", body)
    assert "[redacted]" in body

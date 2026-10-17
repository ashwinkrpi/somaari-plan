"""The only place the app calls AI. decide = Jev; generate = LLM fallback chain."""
import hashlib
import json
import os
import time

from .. import config
from . import jev
from .providers import mock, remote

CHUNK = 40
_cache = {}


def mocking():
    return os.environ.get("SOMAARI_AI_MOCK") == "1"


def chunk(items, n=CHUNK):
    return [items[i:i + n] for i in range(0, len(items), n)]


def _log(provider, model, tokens, started, ok):
    """Provider, model, input tokens, latency. Never content or keys."""
    path = os.environ.get("SOMAARI_AI_LOG") or str(config.ROOT / "data" / "ai.log")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "provider": provider, "model": model,
                                "input_tokens": tokens, "ms": int((time.time() - started) * 1000), "ok": ok}) + "\n")
    except OSError:
        pass


def _key(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()


def fallback_mode(cfg):
    return "llm" if cfg["generate_chain"] else "off"


def decide(state, questions, set_name="adhoc", version="1", cfg=None):
    """One Jev request. Returns {ok, answers, provider, model, fallback, error}.
    On failure ok=False and fallback names the mode to use instead ('llm' or 'off')."""
    cfg = cfg or config.load_ai()
    if cfg["mode"] != "jev":
        return {"ok": False, "answers": None, "provider": None, "fallback": cfg["mode"], "error": None}
    provider = "mock_jev" if mocking() else "jev"
    model = cfg["jev_model"]
    key = _key(provider, model, set_name, version, state, questions)
    if key in _cache:
        return {"ok": True, "answers": _cache[key], "provider": provider, "model": model, "cached": True}
    started = time.time()
    try:
        if mocking():
            answers, usage = mock.mock_jev(state, questions, set_name)
        else:
            answers, usage = jev.call(state, questions, model, cfg["timeout_s"])
    except jev.JevError as e:
        _log(provider, model, 0, started, False)
        return {"ok": False, "answers": None, "provider": provider, "model": model,
                "fallback": fallback_mode(cfg), "error": str(e)}
    _log(provider, model, usage.get("input_tokens", 0), started, True)
    _cache[key] = answers
    return {"ok": True, "answers": answers, "provider": provider, "model": model, "cached": False}


def _parse_json(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[4:] if t.lower().startswith("json") else t
    return json.loads(t)


def generate(prompt, expect_json=False, version="1", cfg=None):
    """Try the chain in order; one retry per provider on bad JSON/failure, then next.
    Returns {ok, text, data, provider, error}."""
    cfg = cfg or config.load_ai()
    chain = cfg["generate_chain"]
    if not chain:
        return {"ok": False, "text": None, "data": None, "provider": None, "error": "no generate provider configured"}
    last = "no provider answered"
    for pid in chain:
        provider = "mock_llm" if mocking() else pid
        asked = "mock" if mocking() else remote.requested(pid, cfg)
        key = _key(provider, asked, version, prompt, expect_json)
        if key in _cache:
            text, data = _cache[key]
            return {"ok": True, "text": text, "data": data, "provider": provider, "cached": True}
        for _ in range(2):
            started = time.time()
            try:
                text = mock.mock_llm(prompt) if mocking() else remote.PROVIDERS[pid](prompt, cfg)
                data = _parse_json(text) if expect_json else None
            except (remote.ProviderError, ValueError) as e:
                last = f"{pid}: {e}"
                _log(provider, asked, 0, started, False)
                continue
            model = getattr(text, "model", "") or asked
            _log(provider, model, getattr(text, "input_tokens", 0), started, True)
            text = str(text)
            _cache[key] = (text, data)
            return {"ok": True, "text": text, "data": data, "provider": provider, "model": model, "cached": False}
    return {"ok": False, "text": None, "data": None, "provider": None, "error": last}


def status(cfg=None):
    """Chain and availability. No secrets."""
    cfg = cfg or config.load_ai()
    m = mocking()
    return {
        "mode": cfg["mode"],
        "jev": {"model": cfg["jev_model"], "available": m or bool(os.environ.get("TYPESAFE_API_KEY"))},
        "generate_chain": [{"id": p, "model": cfg["models"].get(p, ""), "available": m or remote.available(p, cfg)}
                           for p in cfg["generate_chain"]],
        "fallback": fallback_mode(cfg),
        "mock": m,
    }


def test_provider(name, cfg=None):
    """One tiny real call to 'jev' or a generate provider."""
    cfg = cfg or config.load_ai()
    started = time.time()
    if name == "jev":
        qs = {"t": {"type": "noul", "instructions": "Is this text a greeting?"}}
        cfg = dict(cfg, mode="jev")
        r = decide("hello", qs, set_name="ping", version="ping", cfg=cfg) if not mocking() else \
            {"ok": True, "provider": "mock_jev", "model": cfg["jev_model"]}
        return {"ok": r["ok"], "provider": r.get("provider"), "model": r.get("model"),
                "ms": int((time.time() - started) * 1000), "error": r.get("error")}
    if name not in config.GENERATE_PROVIDERS:
        return {"ok": False, "error": "unknown provider"}
    r = generate("Reply with the single word: ok", cfg=dict(cfg, generate_chain=[name]), version="ping-" + str(time.time()))
    return {"ok": r["ok"], "provider": r.get("provider"), "model": r.get("model"),
            "ms": int((time.time() - started) * 1000), "error": r.get("error")}

"""Real generate providers. Keys come from env; never logged."""
import ipaddress
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class ProviderError(Exception):
    pass


def requested(pid, cfg):
    """Model the provider asks for ([ai.models]); logged when a call fails (no model reported back)."""
    return cfg["models"].get(pid, "")


class Reply(str):
    """Provider text that also carries the model that answered and the input token count (for the AI log)."""
    def __new__(cls, text, model="", input_tokens=0):
        s = super().__new__(cls, text)
        s.model, s.input_tokens = model, input_tokens
        return s


def _post(url, headers, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ProviderError(f"HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise ProviderError("unreachable or bad response")


def _chat(url, headers, model, prompt, timeout):
    """OpenAI-style /chat/completions (OpenRouter, OpenAI and compatible servers)."""
    r = _post(url, headers, {"model": model, "messages": [{"role": "user", "content": prompt}]}, timeout)
    try:
        usage = r.get("usage") or {}
        return Reply(r["choices"][0]["message"]["content"], r.get("model") or model, usage.get("prompt_tokens") or 0)
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ProviderError("unexpected response")


def openrouter_free(prompt, cfg):
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise ProviderError("OPENROUTER_API_KEY is not set")
    return _chat("https://openrouter.ai/api/v1/chat/completions", {"Authorization": f"Bearer {key}"},
                 requested("openrouter_free", cfg), prompt, cfg["timeout_s"])


def gemini_api(prompt, cfg):
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ProviderError("GEMINI_API_KEY is not set")
    model = requested("gemini_api", cfg)
    r = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model, safe='')}:generateContent",
              {"x-goog-api-key": key}, {"contents": [{"parts": [{"text": prompt}]}]}, cfg["timeout_s"])
    try:
        usage = r.get("usageMetadata") or {}
        return Reply(r["candidates"][0]["content"]["parts"][0]["text"], r.get("modelVersion") or model,
                     usage.get("promptTokenCount") or 0)
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ProviderError("unexpected response")


def _local(url):
    """True for a server on this Pi or the LAN (e.g. LM Studio, llama.cpp), which may need no key."""
    host = urllib.parse.urlsplit(url).hostname or ""
    if host == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def openai_compat(prompt, cfg):
    key, url = os.environ.get("OPENAI_API_KEY", ""), cfg["openai_base_url"]
    if not key and not _local(url):
        raise ProviderError("OPENAI_API_KEY is not set")
    return _chat(url + "/chat/completions", {"Authorization": f"Bearer {key}"} if key else {},
                 requested("openai_compat", cfg), prompt, cfg["timeout_s"])


PROVIDERS = {"openrouter_free": openrouter_free, "gemini_api": gemini_api, "openai_compat": openai_compat}


def available(pid, cfg):
    if pid == "openrouter_free":
        return bool(os.environ.get("OPENROUTER_API_KEY"))
    if pid == "gemini_api":
        return bool(os.environ.get("GEMINI_API_KEY"))
    if pid == "openai_compat":
        return bool(os.environ.get("OPENAI_API_KEY")) or _local(cfg["openai_base_url"])
    return False

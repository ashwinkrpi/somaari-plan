"""Real generate providers. Keys come from env; never logged."""
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request


class ProviderError(Exception):
    pass


# Model each provider asks for; logged when a call fails (no model reported back).
REQUESTED = {"openrouter_free": "openrouter/free", "gemini_api": "gemini-2.0-flash", "gemini_cli": "gemini-cli"}


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


def openrouter_free(prompt, timeout):
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise ProviderError("OPENROUTER_API_KEY is not set")
    r = _post("https://openrouter.ai/api/v1/chat/completions", {"Authorization": f"Bearer {key}"},
              {"model": REQUESTED["openrouter_free"], "messages": [{"role": "user", "content": prompt}]}, timeout)
    try:
        usage = r.get("usage") or {}
        return Reply(r["choices"][0]["message"]["content"], r.get("model") or REQUESTED["openrouter_free"],
                     usage.get("prompt_tokens") or 0)
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ProviderError("unexpected response")


def gemini_api(prompt, timeout):
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ProviderError("GEMINI_API_KEY is not set")
    r = _post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
              {"x-goog-api-key": key}, {"contents": [{"parts": [{"text": prompt}]}]}, timeout)
    try:
        usage = r.get("usageMetadata") or {}
        return Reply(r["candidates"][0]["content"]["parts"][0]["text"], r.get("modelVersion") or REQUESTED["gemini_api"],
                     usage.get("promptTokenCount") or 0)
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ProviderError("unexpected response")


def gemini_cli(prompt, timeout):
    exe = shutil.which("gemini")
    if not exe:
        raise ProviderError("gemini CLI not installed")
    try:
        p = subprocess.run([exe, "-p", prompt], capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        raise ProviderError("gemini CLI failed")
    if p.returncode != 0 or not p.stdout.strip():
        raise ProviderError("gemini CLI failed")
    return Reply(p.stdout, REQUESTED["gemini_cli"])


PROVIDERS = {"openrouter_free": openrouter_free, "gemini_api": gemini_api, "gemini_cli": gemini_cli}


def available(pid):
    if pid == "openrouter_free":
        return bool(os.environ.get("OPENROUTER_API_KEY"))
    if pid == "gemini_api":
        return bool(os.environ.get("GEMINI_API_KEY"))
    if pid == "gemini_cli":
        return shutil.which("gemini") is not None
    return False

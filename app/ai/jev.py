"""Jev (TypeSafe System One) client. stdlib urllib only; key from env, never logged."""
import json
import os
import time
import urllib.error
import urllib.request

URL = "https://api.typesafe.ai/v1/systemone"
MAX_TRIES = 3
_sleep = time.sleep


class JevError(Exception):
    pass


def _post(body, key, timeout):
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def call(state, questions, model, timeout=60):
    """One request. Returns (answers, usage). Retries 429 up to 3 tries."""
    key = os.environ.get("TYPESAFE_API_KEY", "")
    if not key:
        raise JevError("TYPESAFE_API_KEY is not set")
    body = {"state": state, "model": model, "questions": questions}
    for attempt in range(MAX_TRIES):
        try:
            resp = _post(body, key, timeout)
            return resp["answers"], resp.get("usage", {})
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_TRIES - 1:
                try:
                    wait = min(float(e.headers.get("retry-after", 2)), 30)
                except (TypeError, ValueError):
                    wait = 2
                _sleep(wait)
                continue
            raise JevError(f"Jev returned HTTP {e.code}")
        except (urllib.error.URLError, TimeoutError, OSError):
            raise JevError("Jev is unreachable")
        except (ValueError, KeyError):
            raise JevError("Jev sent an unexpected response")
    raise JevError("Jev rate limit")

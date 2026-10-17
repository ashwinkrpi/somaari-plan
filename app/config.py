"""Config: config.toml + env + CLI. Precedence: CLI > env > config.toml > defaults."""
import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = {"host": "0.0.0.0", "port": 8710, "threads": 4}


class ConfigError(ValueError):
    pass


def config_path():
    return Path(os.environ.get("SOMAARI_CONFIG") or ROOT / "config.toml")


def load_toml(path=None):
    path = Path(path) if path else config_path()
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def validate_port(value):
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise ConfigError(f"Invalid port {value!r}: must be a number 1024-65535.")
    if not 1024 <= port <= 65535:
        raise ConfigError(f"Invalid port {port}: must be between 1024 and 65535.")
    return port


def resolve_server(cli_host=None, cli_port=None, env=None, toml_path=None):
    env = os.environ if env is None else env
    server = load_toml(toml_path).get("server", {})
    host = cli_host or env.get("SOMAARI_HOST") or server.get("host") or DEFAULTS["host"]
    port = cli_port or env.get("SOMAARI_PORT") or server.get("port") or DEFAULTS["port"]
    threads = int(server.get("threads", DEFAULTS["threads"]))
    return host, validate_port(port), threads


# ---- AI settings ([ai] in config.toml) ----
MODES = ("jev", "llm", "off")
GENERATE_PROVIDERS = ("openrouter_free", "gemini_api")
AI_DEFAULTS = {
    "mode": "jev",
    "jev_model": "jev-latest",
    "generate_chain": ["openrouter_free"],
    "rewrite_prose": True,
    "timeout_s": 60,
    "thresholds": {"task_accept": 0.70, "task_review": 0.40, "confidence_review": 0.60},
}


def load_ai(path=None):
    raw = load_toml(path).get("ai", {})
    ai = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
          for k, v in AI_DEFAULTS.items()}
    for k, v in raw.items():
        if k == "thresholds" and isinstance(v, dict):
            ai["thresholds"].update(v)
        elif k in ai:
            ai[k] = v
    return ai


def validate_ai(data):
    """Return a clean [ai] dict or raise ConfigError."""
    if not isinstance(data, dict):
        raise ConfigError("ai settings must be an object.")
    out = load_ai()
    if "mode" in data:
        if data["mode"] not in MODES:
            raise ConfigError("mode must be jev, llm or off.")
        out["mode"] = data["mode"]
    if "jev_model" in data:
        m = data["jev_model"]
        if not isinstance(m, str) or not m.strip() or len(m) > 60 or not m.replace("-", "").replace(".", "").replace("_", "").isalnum():
            raise ConfigError("jev_model must be a short model name such as jev-latest.")
        out["jev_model"] = m.strip()
    if "generate_chain" in data:
        c = data["generate_chain"]
        if not isinstance(c, list) or len(set(c)) != len(c) or any(x not in GENERATE_PROVIDERS for x in c):
            raise ConfigError("generate_chain must be a list of: " + ", ".join(GENERATE_PROVIDERS) + ".")
        out["generate_chain"] = list(c)
    if "rewrite_prose" in data:
        if not isinstance(data["rewrite_prose"], bool):
            raise ConfigError("rewrite_prose must be true or false.")
        out["rewrite_prose"] = data["rewrite_prose"]
    if "timeout_s" in data:
        t = data["timeout_s"]
        if isinstance(t, bool) or not isinstance(t, int) or not 5 <= t <= 300:
            raise ConfigError("timeout_s must be a whole number from 5 to 300.")
        out["timeout_s"] = t
    for k, v in (data.get("thresholds") or {}).items():
        if k not in out["thresholds"]:
            raise ConfigError(f"Unknown threshold {k!r}.")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise ConfigError(f"{k} must be a number from 0 to 1.")
        out["thresholds"][k] = float(v)
    th = out["thresholds"]
    if th["task_review"] > th["task_accept"]:
        raise ConfigError("task_review cannot be higher than task_accept.")
    return out


# ---- UI settings ([ui] in config.toml) ----
DATE_FORMATS = ("dd/mm/yyyy", "mm/dd/yyyy", "yyyy-mm-dd")
UI_DEFAULTS = {"date_format": "dd/mm/yyyy"}


def load_ui(path=None):
    raw = load_toml(path).get("ui", {})
    ui = dict(UI_DEFAULTS)
    if raw.get("date_format") in DATE_FORMATS:
        ui["date_format"] = raw["date_format"]
    return ui


def validate_ui(data):
    if not isinstance(data, dict):
        raise ConfigError("ui must be an object.")
    out = dict(UI_DEFAULTS)
    for k, v in data.items():
        if k not in UI_DEFAULTS:
            raise ConfigError(f"Unknown ui setting {k!r}.")
        if k == "date_format" and v not in DATE_FORMATS:
            raise ConfigError("date_format must be one of: " + ", ".join(DATE_FORMATS) + ".")
        out[k] = v
    return out


def _toml_val(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_val(x) for x in v) + "]"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def dump_toml(data, prefix=""):
    lines = [f"{k} = {_toml_val(v)}" for k, v in data.items() if not isinstance(v, dict)]
    out = "\n".join(lines) + ("\n" if lines else "")
    for k, v in data.items():
        if isinstance(v, dict):
            name = f"{prefix}.{k}" if prefix else k
            out += f"\n[{name}]\n" + dump_toml(v, name)
    return out


def save_ai(ai, path=None):
    save_section("ai", ai, path)


def save_section(name, values, path=None):
    """Replace one [section] of config.toml, keeping the others ([server], [ai], [ui])."""
    path = Path(path) if path else config_path()
    data = load_toml(path)
    data[name] = values
    tmp = path.with_suffix(".tmp")
    tmp.write_text(dump_toml(data), encoding="utf-8")
    tmp.replace(path)


def load_dotenv(path=None):
    """Load KEY=VALUE lines from .env into os.environ (existing env wins)."""
    path = Path(path) if path else ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

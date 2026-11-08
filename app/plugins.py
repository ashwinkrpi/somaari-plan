"""Optional plugins (D-21, docs/PLUGINS_PLAN.md).

A plugin is a separate package that registers an object in the "somaari_plan.plugins"
entry-point group. The core never imports a plugin by name: with none installed, this
module finds nothing and the app behaves exactly as before.
"""
import os
import sys
from datetime import datetime
from importlib.metadata import entry_points
from pathlib import Path

from . import config, db

API_VERSION = 1
GROUP = "somaari_plan.plugins"
FIELD_TYPES = ("bool", "time", "text", "number")


class PluginError(Exception):
    """A plugin action failed; the message is shown to the user as is."""


class Context:
    """What a plugin may use. Plugins never touch the DB or config.toml directly."""

    def __init__(self, plugin, db_path):
        self.plugin = plugin
        self.name = plugin.name
        self.db_path = db_path
        self.data_dir = Path(db_path).parent / "plugins" / plugin.name   # data/plugins/<name>/

    def settings(self):
        out = dict(self.plugin.defaults)
        out.update({k: v for k, v in config.load_plugin(self.name).items() if k in out})
        return out

    def save_settings(self, values):
        config.save_plugin(self.name, values)

    def now(self):
        return datetime.now(db.IST)

    def today(self):
        return self.now().date()

    def tasks(self, from_date=None, to_date=None, open_only=True):
        """Tasks with due_date in [from_date, to_date] (ISO strings or dates; None = open-ended)."""
        where, args = [], []
        if from_date is not None:
            where.append("due_date >= ?")
            args.append(str(from_date))
        if to_date is not None:
            where.append("due_date <= ?")
            args.append(str(to_date))
        if open_only:
            where.append("closed_at IS NULL")
        sql = ("SELECT id, title, step, due_date, due_time, priority, type, closed_at FROM tasks"
               + (" WHERE " + " AND ".join(where) if where else "")
               + " ORDER BY due_date, sort_order, id")
        conn = db.connect(self.db_path)
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()

    def log(self, msg):
        print(f"somaari-plan [{self.name}] {msg}", file=sys.stderr, flush=True)


def _valid(p):
    return (getattr(p, "api_version", None) == API_VERSION and isinstance(getattr(p, "name", None), str)
            and p.name.isidentifier() and isinstance(getattr(p, "defaults", None), dict)
            and all(f.get("type") in FIELD_TYPES and f.get("key") in p.defaults for f in getattr(p, "fields", [])))


def discover():
    """Load installed plugins. A broken or incompatible plugin is skipped, never fatal.
    SOMAARI_NO_PLUGINS=1 turns discovery off (the test suite sets it)."""
    if os.environ.get("SOMAARI_NO_PLUGINS") == "1":
        return []
    found = []
    for ep in entry_points(group=GROUP):
        try:
            p = ep.load()
        except Exception as e:  # noqa: BLE001 - a plugin must never stop the app starting
            print(f"somaari-plan: plugin {ep.name!r} not loaded: {e}", file=sys.stderr)
            continue
        if not _valid(p):
            print(f"somaari-plan: plugin {ep.name!r} skipped (needs plugin API {API_VERSION})", file=sys.stderr)
            continue
        if any(q.name == p.name for q in found):
            continue
        found.append(p)
    return found


def setup(app, plugins=None):
    """Attach plugins and their contexts to the app (app.config["PLUGINS"]: name -> (plugin, ctx))."""
    plugins = discover() if plugins is None else plugins
    app.config["PLUGINS"] = {p.name: (p, Context(p, app.config["DB_PATH"])) for p in plugins}


def start_services(app):
    """Start plugin background services. Only the real server process calls this."""
    for p, ctx in app.config.get("PLUGINS", {}).values():
        start = getattr(p, "start", None)
        if start:
            try:
                start(ctx)
            except Exception as e:  # noqa: BLE001
                ctx.log(f"service not started: {e}")

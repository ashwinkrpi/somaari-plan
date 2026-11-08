"""Settings and buttons for installed plugins (D-21). Empty list when none are installed."""
from flask import Blueprint, current_app, jsonify, request

from ..plugins import PluginError

bp = Blueprint("plugins", __name__)


def _get(name):
    return current_app.config.get("PLUGINS", {}).get(name)


def _payload(p, ctx):
    try:
        status = list(p.status(ctx)) if hasattr(p, "status") else []
    except Exception:  # noqa: BLE001 - status lines are informational only
        status = ["Status unavailable."]
    return {"name": p.name, "title": getattr(p, "title", p.name), "description": getattr(p, "description", ""),
            "fields": list(getattr(p, "fields", [])), "values": ctx.settings(),
            "actions": list(getattr(p, "actions", [])), "status": status}


@bp.get("/api/plugins")
def list_plugins():
    return jsonify([_payload(p, ctx) for p, ctx in current_app.config.get("PLUGINS", {}).values()])


@bp.put("/api/plugins/<name>")
def save_plugin(name):
    found = _get(name)
    if not found:
        return jsonify({"error": f"No plugin named {name}."}), 404
    p, ctx = found
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) - set(p.defaults):
        return jsonify({"error": "Settings must be an object with known keys only."}), 400
    try:
        values = p.validate({**ctx.settings(), **data})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    ctx.save_settings(values)
    return jsonify(_payload(p, ctx))


@bp.post("/api/plugins/<name>/actions/<action>")
def run_action(name, action):
    found = _get(name)
    if not found:
        return jsonify({"error": f"No plugin named {name}."}), 404
    p, ctx = found
    if action not in {a["id"] for a in getattr(p, "actions", [])}:
        return jsonify({"error": f"Unknown action {action}."}), 404
    try:
        msg = p.run_action(ctx, action)
    except PluginError as e:
        return jsonify({"ok": False, "message": str(e)})
    except Exception:  # noqa: BLE001 - never leak a traceback (it may hold a URL with a token)
        ctx.log(f"action {action} failed unexpectedly")
        return jsonify({"ok": False, "message": "The plugin failed. See the service log."})
    return jsonify({"ok": True, "message": msg})

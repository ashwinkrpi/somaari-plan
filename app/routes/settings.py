from flask import Blueprint, jsonify, request

from .. import config

bp = Blueprint("settings", __name__)


def _payload():
    host, port, threads = config.resolve_server()
    return {"ai": config.load_ai(), "providers": list(config.GENERATE_PROVIDERS), "modes": list(config.MODES),
            "ui": config.load_ui(), "date_formats": list(config.DATE_FORMATS),
            "server": {"host": host, "port": port, "threads": threads, "note": "Changing these needs a restart."}}


@bp.get("/api/settings")
def get_settings():
    return jsonify(_payload())


@bp.put("/api/settings")
def put_settings():
    data = request.get_json(silent=True) or {}
    try:   # validate everything before writing anything
        ai = config.validate_ai(data["ai"]) if "ai" in data else (None if "ui" in data else config.validate_ai(data))
        ui = config.validate_ui(data["ui"]) if "ui" in data else None
    except config.ConfigError as e:
        return jsonify({"error": str(e)}), 400
    if ai is not None:
        config.save_ai(ai)
    if ui is not None:
        config.save_section("ui", ui)
    return jsonify(_payload())

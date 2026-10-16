"""About section (somaari-common/docs/ABOUT_SPEC.md): app, developer and debug info. No network."""
import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify
from somaari_about import as_text, collect, load_debug_fields, load_developer

from .. import __version__, config
from ..ai.providers.remote import REQUESTED

bp = Blueprint("about", __name__)
PACKAGES = ("flask", "waitress", "werkzeug")

try:
    from .._build_info import BUILD_COMMIT, BUILD_DATE
except ImportError:   # running from source
    BUILD_COMMIT = BUILD_DATE = None


def _ai_names():
    """Configured provider and model names only (never keys): Jev primary, then the generate chain."""
    ai = config.load_ai()
    if ai["mode"] == "off":
        return "off (code only)", None
    chain = ai["generate_chain"]
    providers = [f"{p} (fallback)" for p in chain]
    models = [REQUESTED.get(p, p) for p in chain]
    if ai["mode"] == "jev":
        providers.insert(0, "jev (primary)")
        models.insert(0, ai["jev_model"])
    return ", ".join(providers) or None, ", ".join(models) or None


def about_info():
    provider, model = _ai_names()
    log = os.environ.get("SOMAARI_AI_LOG") or str(config.ROOT / "data" / "ai.log")
    return collect(
        "somaari-plan", __version__,
        build_commit=BUILD_COMMIT, build_date=BUILD_DATE,
        packages=PACKAGES,
        data_dir=Path(current_app.config["DB_PATH"]).resolve().parent,
        config_dir=config.config_path().resolve().parent,
        log_dir=Path(log).resolve().parent,
        ai_provider=provider, ai_model=model,
    )


@bp.get("/api/about")
def get_about():
    info, developer = about_info(), load_developer()
    fields = [{"key": f["key"], "label": f["label"]} for f in load_debug_fields()]
    return jsonify({"info": info, "fields": fields, "developer": developer, "text": as_text(info, developer)})

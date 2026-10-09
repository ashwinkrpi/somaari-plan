from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from .db import DEFAULT_DB, init_db
from .routes.ai import bp as ai_bp
from .routes.export import bp as export_bp
from .routes.ingest import bp as ingest_bp
from .routes.quick import bp as quick_bp
from .routes.settings import bp as settings_bp
from .routes.tasks import bp as tasks_bp

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_app(db_path=None):
    app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="")
    app.config["DB_PATH"] = str(db_path or DEFAULT_DB)
    init_db(app.config["DB_PATH"])
    app.register_blueprint(tasks_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(ingest_bp)
    app.register_blueprint(quick_bp)
    app.register_blueprint(export_bp)
    app.config.setdefault("MAX_CONTENT_LENGTH", 24 * 1024 * 1024)

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    return app

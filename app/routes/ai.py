from flask import Blueprint, jsonify, request

from ..ai import router

bp = Blueprint("ai", __name__)


@bp.get("/api/ai/status")
def ai_status():
    return jsonify(router.status())


@bp.post("/api/ai/test")
def ai_test():
    name = (request.get_json(silent=True) or {}).get("provider", "")
    r = router.test_provider(name)
    return jsonify(r), (200 if r.get("error") != "unknown provider" else 400)

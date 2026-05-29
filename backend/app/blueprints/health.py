from datetime import datetime, timezone

from flask import Blueprint, current_app

from ..utils.response import success_response

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    """健康检查：验证 Flask 与 MongoDB 基础连通性。"""
    db_status = "ok"
    db_error = None
    try:
        current_app.db.command("ping")
    except Exception as exc:  # pragma: no cover - 真实环境中用于暴露连接问题
        db_status = "error"
        db_error = str(exc)

    data = {
        "service": current_app.config["APP_NAME"],
        "status": "ok" if db_status == "ok" else "degraded",
        "database": {
            "name": current_app.config["MONGO_DB_NAME"],
            "status": db_status,
            "error": db_error,
        },
        "external_capabilities": {
            "payment": current_app.config["PAYMENT_MODE"],
            "ai": current_app.config["AI_MODE"],
        },
        "time": datetime.now(timezone.utc).isoformat(),
    }
    return success_response(data)

from datetime import datetime, timezone

from flask import Blueprint, current_app, request

from ..utils.errors import UnauthorizedError
from ..utils.response import success_response

health_bp = Blueprint("health", __name__)


def _database_name():
    if current_app.config["DB_BACKEND"] == "mysql":
        return current_app.config["MYSQL_DATABASE"]
    return current_app.config["MONGO_DB_NAME"]


def _require_init_token():
    token = current_app.config.get("INIT_TOKEN")
    if not token or request.headers.get("X-Init-Token") != token:
        raise UnauthorizedError("初始化口令无效")


@health_bp.get("/health")
def health_check():
    db_status = "ok"
    db_error = None
    try:
        current_app.db.command("ping")
    except Exception as exc:  # pragma: no cover
        db_status = "error"
        db_error = str(exc)

    return success_response(
        {
            "service": current_app.config["APP_NAME"],
            "status": "ok" if db_status == "ok" else "degraded",
            "database": {
                "backend": current_app.config["DB_BACKEND"],
                "name": _database_name(),
                "status": db_status,
                "error": db_error,
            },
            "external_capabilities": {
                "payment": current_app.config["PAYMENT_MODE"],
                "ai": current_app.config["AI_MODE"],
            },
            "time": datetime.now(timezone.utc).isoformat(),
        }
    )


@health_bp.get("/health/db")
def health_db_check():
    started_at = datetime.now(timezone.utc)
    result = current_app.db.command("ping")
    latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
    return success_response(
        {
            "backend": current_app.config["DB_BACKEND"],
            "database": _database_name(),
            "result": result,
            "latency_ms": latency_ms,
        }
    )


@health_bp.get("/debug/storage")
def debug_storage():
    if not current_app.config.get("DEBUG") and not current_app.config.get("DEV_TEST_LOGIN_ENABLED"):
        raise UnauthorizedError("调试接口未启用")
    return success_response(
        {
            "storage_backend": current_app.config.get("STORAGE_BACKEND"),
            "cos_bucket": current_app.config.get("COS_BUCKET"),
            "cos_region": current_app.config.get("COS_REGION"),
            "cos_public_base_url": current_app.config.get("COS_PUBLIC_BASE_URL"),
            "has_cos_secret_id": bool(current_app.config.get("COS_SECRET_ID")),
            "has_cos_secret_key": bool(current_app.config.get("COS_SECRET_KEY")),
        }
    )


@health_bp.post("/init-demo-data")
def init_demo_data():
    _require_init_token()

    from scripts.init_db import ensure_collections, ensure_indexes, seed_categories, seed_products, seed_users

    ensure_collections(current_app.db)
    ensure_indexes(current_app.db)
    seed_categories(current_app.db)
    seed_users(current_app.db)
    seed_products(current_app.db)
    return success_response({"initialized": True})


@health_bp.post("/debug/demo-products/reset")
def reset_demo_products_endpoint():
    _require_init_token()

    from scripts.init_db import ensure_collections, ensure_indexes, reset_demo_products, seed_categories, seed_users

    ensure_collections(current_app.db)
    ensure_indexes(current_app.db)
    seed_categories(current_app.db)
    seed_users(current_app.db)
    result = reset_demo_products(current_app.db)
    return success_response(result)

import os
from pathlib import Path


def _load_env_file(env_path: Path) -> None:
    """轻量读取 .env，避免项目在安装 python-dotenv 前无法读取基础配置。"""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent
_load_env_file(BASE_DIR / ".env")


class Config:
    APP_NAME = os.getenv("APP_NAME", "campus_secondhand_platform")
    API_PREFIX = os.getenv("API_PREFIX", "/api/v1")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
    JWT_EXPIRES_SECONDS = int(os.getenv("JWT_EXPIRES_SECONDS", "604800"))

    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "campus_secondhand")

    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        str(PROJECT_ROOT / "uploads"),
    )

    PAYMENT_MODE = os.getenv("PAYMENT_MODE", "mock")
    AI_MODE = os.getenv("AI_MODE", "mock")
    WECHAT_AUTH_MODE = os.getenv("WECHAT_AUTH_MODE", "mock")
    WECHAT_APPID = os.getenv("WECHAT_APPID", "")
    WECHAT_APPSECRET = os.getenv("WECHAT_APPSECRET", "")
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
    ORDER_PAYMENT_TIMEOUT_MINUTES = int(os.getenv("ORDER_PAYMENT_TIMEOUT_MINUTES", "30"))
    ORDER_AUTO_RECEIVE_DAYS = int(os.getenv("ORDER_AUTO_RECEIVE_DAYS", "7"))
    REFUND_SELLER_TIMEOUT_HOURS = int(os.getenv("REFUND_SELLER_TIMEOUT_HOURS", "48"))

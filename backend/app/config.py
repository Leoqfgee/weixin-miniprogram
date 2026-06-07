import os
from pathlib import Path


def _load_env_file(env_path: Path) -> None:
    """Load local .env without overriding platform-provided environment variables."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _split_host_port(address: str, default_port: int = 3306):
    if ":" not in address:
        return address, default_port
    host, port = address.rsplit(":", 1)
    if not port.isdigit():
        return address, default_port
    return host, int(port)


BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent
_load_env_file(BASE_DIR / ".env")
_mysql_host, _mysql_port = _split_host_port(os.getenv("MYSQL_ADDRESS", "localhost"))


class Config:
    APP_NAME = os.getenv("APP_NAME", "campus_secondhand_platform")
    API_PREFIX = os.getenv("API_PREFIX", "/api/v1")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
    JWT_EXPIRES_SECONDS = int(os.getenv("JWT_EXPIRES_SECONDS", "604800"))

    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "campus_secondhand")
    DB_BACKEND = os.getenv("DB_BACKEND", "mongo").lower()
    MYSQL_HOST = os.getenv("MYSQL_HOST", _mysql_host)
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", str(_mysql_port)))
    MYSQL_USERNAME = os.getenv("MYSQL_USERNAME", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "flask_demo")
    INIT_TOKEN = os.getenv("INIT_TOKEN", "")

    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        str(PROJECT_ROOT / "uploads"),
    )

    PAYMENT_MODE = os.getenv("PAYMENT_MODE", "mock")
    AI_MODE = os.getenv("AI_MODE", "qwen")
    AI_BASE_URL = os.getenv("AI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")
    AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    WECHAT_AUTH_MODE = os.getenv("WECHAT_AUTH_MODE", "mock").strip()
    WECHAT_APPID = os.getenv("WECHAT_APPID", "").strip()
    WECHAT_SECRET = os.getenv("WECHAT_SECRET", "").strip()
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", os.getenv("PORT", "80")))
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
    ORDER_PAYMENT_TIMEOUT_MINUTES = int(os.getenv("ORDER_PAYMENT_TIMEOUT_MINUTES", "30"))
    ORDER_AUTO_RECEIVE_DAYS = int(os.getenv("ORDER_AUTO_RECEIVE_DAYS", "7"))
    REFUND_SELLER_TIMEOUT_HOURS = int(os.getenv("REFUND_SELLER_TIMEOUT_HOURS", "48"))

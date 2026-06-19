from flask import Blueprint, current_app, g, request

from ..services.files import FileService
from ..utils.errors import ForbiddenError
from ..utils.jwt import auth_required
from ..utils.response import success_response

files_bp = Blueprint("files", __name__)


@files_bp.post("/files/upload")
@auth_required
def upload_file():
    usage = request.form.get("usage", "product")
    data = FileService(current_app.db).upload_file(g.current_user_id, request.files.get("file"), usage)
    return success_response(data, http_status=201)


@files_bp.post("/files/upload-base64")
@auth_required
def upload_base64():
    data = FileService(current_app.db).upload_base64(g.current_user_id, request.get_json(silent=True) or {})
    return success_response(data, http_status=201)


@files_bp.get("/debug/storage")
def debug_storage():
    if not (current_app.debug or current_app.config.get("DEV_TEST_LOGIN_ENABLED")):
        raise ForbiddenError("调试接口仅在开发模式可用")
    data = {
        "storage_backend": current_app.config.get("STORAGE_BACKEND", ""),
        "cos_bucket": current_app.config.get("COS_BUCKET", ""),
        "cos_region": current_app.config.get("COS_REGION", ""),
        "cos_public_base_url": current_app.config.get("COS_PUBLIC_BASE_URL", ""),
        "has_cos_secret_id": bool(current_app.config.get("COS_SECRET_ID")),
        "has_cos_secret_key": bool(current_app.config.get("COS_SECRET_KEY")),
    }
    return success_response(data)

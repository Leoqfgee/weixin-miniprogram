from flask import Blueprint, current_app, g, request

from ..services.files import FileService
from ..utils.jwt import auth_required
from ..utils.response import success_response

files_bp = Blueprint("files", __name__)


@files_bp.post("/files/upload")
@auth_required
def upload_file():
    usage = request.form.get("usage", "product")
    data = FileService(current_app.db).upload_file(g.current_user_id, request.files.get("file"), usage)
    return success_response(data, http_status=201)

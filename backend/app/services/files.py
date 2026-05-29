from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import current_app, request
from werkzeug.utils import secure_filename

from ..utils.errors import ValidationError
from ..utils.serializers import serialize_doc


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


def utc_now():
    return datetime.now(timezone.utc)


class FileService:
    def __init__(self, db):
        self.db = db

    def upload_image(self, owner_id, file_storage, usage="product"):
        if not file_storage or not file_storage.filename:
            raise ValidationError("参数校验失败", [{"field": "file", "message": "请选择要上传的图片"}])

        original_name = secure_filename(file_storage.filename)
        suffix = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValidationError("参数校验失败", [{"field": "file", "message": "仅支持 jpg、png、webp、gif 图片"}])

        content = file_storage.read()
        if len(content) > MAX_IMAGE_SIZE:
            raise ValidationError("参数校验失败", [{"field": "file", "message": "单张图片不能超过 5MB"}])

        safe_usage = usage if usage in {"product", "avatar", "refund", "appeal"} else "misc"
        filename = f"{uuid4().hex}.{suffix}"
        upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
        target_dir = upload_root / safe_usage
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        target_path.write_bytes(content)

        relative_path = f"{safe_usage}/{filename}"
        file_url = f"{request.host_url.rstrip('/')}/uploads/{relative_path}"
        doc = {
            "owner_id": owner_id,
            "usage": safe_usage,
            "original_name": original_name,
            "filename": filename,
            "relative_path": relative_path,
            "url": file_url,
            "mime_type": file_storage.mimetype,
            "size": len(content),
            "created_at": utc_now(),
        }
        result = self.db.files.insert_one(doc)
        return serialize_doc(self.db.files.find_one({"_id": result.inserted_id}))

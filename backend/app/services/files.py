from datetime import datetime, timezone

from werkzeug.utils import secure_filename

from ..adapters.storage import StorageService
from ..utils.errors import ValidationError
from ..utils.serializers import serialize_doc


ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "mp4", "mov", "m4v", "mp3", "aac", "wav"}
MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_USAGES = {"product", "avatar", "refund", "appeal", "delivery", "chat"}


def utc_now():
    return datetime.now(timezone.utc)


def _safe_filename(filename):
    safe_name = secure_filename(filename or "") or "upload.jpg"
    if "." not in safe_name and "." in filename:
        suffix = filename.rsplit(".", 1)[-1]
        safe_name = secure_filename(f"upload.{suffix}") or "upload.jpg"
    return safe_name


class FileService:
    def __init__(self, db):
        self.db = db

    def upload_file(self, owner_id, file_storage, usage="product"):
        if not file_storage or not file_storage.filename:
            raise ValidationError("参数校验失败", [{"field": "file", "message": "请选择要上传的文件"}])

        original_name = _safe_filename(file_storage.filename)
        suffix = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValidationError("参数校验失败", [{"field": "file", "message": "仅支持常见图片、视频和音频格式"}])

        content = file_storage.read()
        if len(content) > MAX_FILE_SIZE:
            raise ValidationError("参数校验失败", [{"field": "file", "message": "单个文件不能超过 20MB"}])

        safe_usage = usage if usage in ALLOWED_USAGES else "misc"
        storage_result = StorageService().save(content, original_name, file_storage.mimetype, safe_usage)
        object_key = storage_result["object_key"]
        filename = object_key.rsplit("/", 1)[-1]
        doc = {
            "owner_id": owner_id,
            "usage": safe_usage,
            "original_name": original_name,
            "filename": filename,
            "object_key": object_key,
            "relative_path": object_key,
            "url": storage_result["url"],
            "storage_backend": storage_result["storage_backend"],
            "mime_type": file_storage.mimetype,
            "size": len(content),
            "created_at": utc_now(),
        }
        result = self.db.files.insert_one(doc)
        return serialize_doc(self.db.files.find_one({"_id": result.inserted_id}))

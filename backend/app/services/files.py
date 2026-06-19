import base64
import binascii
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
        return self._store(owner_id, content, original_name, file_storage.mimetype, safe_usage)

    def upload_base64(self, owner_id, payload):
        usage = payload.get("usage") or "product"
        filename = _safe_filename(payload.get("filename") or "upload.jpg")
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValidationError("参数校验失败", [{"field": "filename", "message": "仅支持常见图片、视频和音频格式"}])

        encoded = (payload.get("content_base64") or "").strip()
        if "," in encoded and encoded.split(",", 1)[0].startswith("data:"):
            encoded = encoded.split(",", 1)[1]
        if not encoded:
            raise ValidationError("参数校验失败", [{"field": "content_base64", "message": "请选择要上传的文件"}])
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise ValidationError("参数校验失败", [{"field": "content_base64", "message": "文件内容不合法"}])
        if len(content) > MAX_FILE_SIZE:
            raise ValidationError("参数校验失败", [{"field": "file", "message": "单个文件不能超过 20MB"}])

        safe_usage = usage if usage in ALLOWED_USAGES else "misc"
        mime_type = payload.get("mime_type") or _mime_from_suffix(suffix)
        return self._store(owner_id, content, filename, mime_type, safe_usage)

    def _store(self, owner_id, content, original_name, mime_type, safe_usage):
        storage_result = StorageService().save(content, original_name, mime_type, safe_usage)
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
            "mime_type": mime_type,
            "size": len(content),
            "created_at": utc_now(),
        }
        result = self.db.files.insert_one(doc)
        return serialize_doc(self.db.files.find_one({"_id": result.inserted_id}))


def _mime_from_suffix(suffix):
    mapping = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
    }
    return mapping.get(suffix, "application/octet-stream")

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import current_app, request

from ..utils.errors import AppError

try:
    from qcloud_cos import CosConfig, CosS3Client
except ImportError:  # pragma: no cover - local dev can run without COS SDK installed
    CosConfig = None
    CosS3Client = None


class StorageService:
    def __init__(self):
        self.backend = current_app.config.get("STORAGE_BACKEND", "local")

    def save(self, content: bytes, filename: str, mime_type: str, usage: str):
        if self.backend == "cos":
            return self._save_to_cos(content, filename, mime_type, usage)
        return self._save_to_local(content, filename, mime_type, usage)

    def _make_object_key(self, filename: str, usage: str):
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
        now = datetime.now()
        return f"{usage}/{now:%Y/%m}/{uuid4().hex}.{suffix}"

    def _save_to_cos(self, content: bytes, filename: str, mime_type: str, usage: str):
        if CosConfig is None or CosS3Client is None:
            raise AppError(50000, "COS SDK 未安装，请检查 cos-python-sdk-v5 依赖", 500)

        bucket = current_app.config.get("COS_BUCKET", "")
        region = current_app.config.get("COS_REGION", "")
        secret_id = current_app.config.get("COS_SECRET_ID", "")
        secret_key = current_app.config.get("COS_SECRET_KEY", "")
        public_base_url = current_app.config.get("COS_PUBLIC_BASE_URL", "").rstrip("/")

        if not all([bucket, region, secret_id, secret_key, public_base_url]):
            raise AppError(
                50000,
                "COS 配置缺失，请检查 COS_BUCKET、COS_REGION、COS_SECRET_ID、COS_SECRET_KEY、COS_PUBLIC_BASE_URL",
                500,
            )

        config = CosConfig(
            Region=region,
            SecretId=secret_id,
            SecretKey=secret_key,
            Scheme="https",
        )
        client = CosS3Client(config)
        object_key = self._make_object_key(filename, usage)

        client.put_object(
            Bucket=bucket,
            Body=content,
            Key=object_key,
            ContentType=mime_type or "application/octet-stream",
        )

        return {
            "id": object_key,
            "object_key": object_key,
            "url": f"{public_base_url}/{object_key}",
            "storage_backend": "cos",
        }

    def _save_to_local(self, content: bytes, filename: str, mime_type: str, usage: str):
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
        saved_name = f"{uuid4().hex}.{suffix}"
        upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
        target_dir = upload_root / usage
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / saved_name
        target_path.write_bytes(content)

        relative_path = f"{usage}/{saved_name}"
        url = f"{request.host_url.rstrip('/')}/uploads/{relative_path}"
        return {
            "id": relative_path,
            "object_key": relative_path,
            "url": url,
            "storage_backend": "local",
        }

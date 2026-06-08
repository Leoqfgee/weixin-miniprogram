import os
import sys
from pathlib import Path

from pymongo import MongoClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import Config  # noqa: E402


COS_PREFIX = "https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com/"


def _cos_images(images):
    return [url for url in (images or []) if str(url or "").startswith(COS_PREFIX)]


def _is_old_cover(url):
    value = str(url or "")
    return (
        not value
        or value.startswith("/uploads")
        or value.startswith("http://flask-fnnj")
        or "124.223.146.85" in value
    )


def main():
    client = MongoClient(os.getenv("MONGO_URI", Config.MONGO_URI))
    repaired = 0
    need_reupload = 0
    try:
        db = client[os.getenv("MONGO_DB_NAME", Config.MONGO_DB_NAME)]
        for product in db.products.find({}):
            cos_images = _cos_images(product.get("images") or [])
            cover = str(product.get("cover_image") or "")
            if cos_images and _is_old_cover(cover):
                db.products.update_one({"_id": product["_id"]}, {"$set": {"cover_image": cos_images[0]}})
                repaired += 1
            elif not cos_images and _is_old_cover(cover):
                need_reupload += 1
        print(f"已修复 cover_image: {repaired}")
        print(f"缺少 COS 图片、需要重新上传的商品: {need_reupload}")
    finally:
        client.close()


if __name__ == "__main__":
    main()

import os
import sys
from pathlib import Path

from pymongo import MongoClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import Config  # noqa: E402


COS_PREFIX = "https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com/"


def main():
    client = MongoClient(os.getenv("MONGO_URI", Config.MONGO_URI))
    try:
        db = client[os.getenv("MONGO_DB_NAME", Config.MONGO_DB_NAME)]
        products = list(db.products.find({}))
        total = len(products)
        cover_empty = 0
        images_empty = 0
        cover_cos = 0
        cover_uploads = 0
        cover_legacy_host = 0
        cover_flask_http = 0
        for product in products:
            cover = str(product.get("cover_image") or "")
            images = product.get("images") or []
            if not cover:
                cover_empty += 1
            if not images:
                images_empty += 1
            if cover.startswith(COS_PREFIX):
                cover_cos += 1
            if cover.startswith("/uploads"):
                cover_uploads += 1
            if "124.223.146.85" in cover:
                cover_legacy_host += 1
            if cover.startswith("http://flask-fnnj"):
                cover_flask_http += 1

        print(f"商品总数: {total}")
        print(f"cover_image 为空数量: {cover_empty}")
        print(f"images 为空数量: {images_empty}")
        print(f"cover_image 是 COS URL 数量: {cover_cos}")
        print(f"cover_image 是 /uploads 数量: {cover_uploads}")
        print(f"cover_image 是 124.223.146.85 数量: {cover_legacy_host}")
        print(f"cover_image 是 http://flask-fnnj 数量: {cover_flask_http}")
    finally:
        client.close()


if __name__ == "__main__":
    main()

import os

import pytest
from pymongo import MongoClient


# 测试使用独立数据库，避免 pytest 演示商品污染本地课程演示主库。
os.environ.setdefault("MONGO_DB_NAME", "campus_secondhand_test")
os.environ.setdefault("PYTHONNOUSERSITE", "1")


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_database():
    yield
    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    try:
        client.drop_database(os.getenv("MONGO_DB_NAME", "campus_secondhand_test"))
    finally:
        client.close()

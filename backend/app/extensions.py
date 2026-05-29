from pymongo import MongoClient


class MongoExtension:
    """集中管理 MongoDB 客户端，供 Service/Repository 层复用。"""

    def __init__(self) -> None:
        self.client = None
        self.db = None

    def init_app(self, app) -> None:
        self.client = MongoClient(app.config["MONGO_URI"])
        self.db = self.client[app.config["MONGO_DB_NAME"]]
        app.mongo_client = self.client
        app.db = self.db

    def close(self) -> None:
        if self.client:
            self.client.close()


mongo = MongoExtension()

class CategoryRepository:
    def __init__(self, db):
        self.db = db

    def list_enabled(self):
        return list(self.db.categories.find({"enabled": True}).sort("sort", 1))

    def exists(self, category_id):
        return self.db.categories.count_documents({"_id": category_id, "enabled": True}) > 0

    def find_by_code(self, code):
        return self.db.categories.find_one({"code": code, "enabled": True})

    def find_by_id(self, category_id):
        return self.db.categories.find_one({"_id": category_id, "enabled": True})

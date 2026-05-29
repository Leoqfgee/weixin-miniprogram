from bson import ObjectId


class UserRepository:
    def __init__(self, db):
        self.db = db

    def find_by_phone(self, phone):
        return self.db.users.find_one({"phone": phone})

    def find_by_id(self, user_id):
        object_id = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
        return self.db.users.find_one({"_id": object_id})

    def find_profile(self, user_id):
        object_id = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
        return self.db.user_profiles.find_one({"user_id": object_id})

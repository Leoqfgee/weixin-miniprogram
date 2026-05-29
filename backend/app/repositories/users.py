from bson import ObjectId


class UserRepository:
    def __init__(self, db):
        self.db = db

    def find_by_phone(self, phone):
        return self.db.users.find_one({"phone": phone})

    def find_by_openid(self, openid):
        return self.db.users.find_one({"openid": openid})

    def find_by_id(self, user_id):
        object_id = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
        return self.db.users.find_one({"_id": object_id})

    def find_profile(self, user_id):
        object_id = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
        return self.db.user_profiles.find_one({"user_id": object_id})

    def create_user(self, user_doc, profile_doc=None):
        result = self.db.users.insert_one(user_doc)
        user = self.find_by_id(result.inserted_id)
        if profile_doc is not None:
            profile_doc["user_id"] = user["_id"]
            self.db.user_profiles.insert_one(profile_doc)
        return user

    def update_user(self, user_id, fields):
        object_id = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
        self.db.users.update_one({"_id": object_id}, {"$set": fields})
        return self.find_by_id(object_id)

    def update_profile(self, user_id, fields):
        object_id = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
        self.db.user_profiles.update_one({"user_id": object_id}, {"$set": fields}, upsert=True)
        return self.find_profile(object_id)

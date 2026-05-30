from datetime import datetime, timezone

from bson import ObjectId
from pymongo import DESCENDING


def utc_now():
    return datetime.now(timezone.utc)


class OrderRepository:
    def __init__(self, db):
        self.db = db

    def create(self, order):
        order["created_at"] = utc_now()
        order["updated_at"] = utc_now()
        result = self.db.orders.insert_one(order)
        return self.find_by_id(result.inserted_id)

    def find_by_id(self, order_id):
        object_id = order_id if isinstance(order_id, ObjectId) else ObjectId(str(order_id))
        return self.db.orders.find_one({"_id": object_id})

    def find_by_idempotency_key(self, buyer_id, key):
        return self.db.orders.find_one({"buyer_id": buyer_id, "idempotency_key": key})

    def update_fields(self, order_id, fields):
        fields["updated_at"] = utc_now()
        self.db.orders.update_one({"_id": order_id}, {"$set": fields})
        return self.find_by_id(order_id)

    def list_for_user(self, user_id, status=None, page=1, page_size=20, role=None):
        if role == "buyer":
            query = {"buyer_id": user_id}
        elif role == "seller":
            query = {"seller_id": user_id}
        else:
            query = {"$or": [{"buyer_id": user_id}, {"seller_id": user_id}]}
        if status:
            query["status"] = status
        total = self.db.orders.count_documents(query)
        items = list(
            self.db.orders.find(query)
            .sort("created_at", DESCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return items, total


class OrderItemRepository:
    def __init__(self, db):
        self.db = db

    def create_many(self, items):
        if items:
            self.db.order_items.insert_many(items)

    def list_by_order(self, order_id):
        return list(self.db.order_items.find({"order_id": order_id}))

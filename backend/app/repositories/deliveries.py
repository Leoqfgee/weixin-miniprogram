from datetime import datetime, timezone

from bson import ObjectId


def utc_now():
    return datetime.now(timezone.utc)


class DeliveryRepository:
    def __init__(self, db):
        self.db = db

    def mark_delivering(self, order_id, seller_id):
        doc = {
            "order_id": order_id,
            "seller_id": seller_id,
            "status": "delivering",
            "delivered_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.db.deliveries.update_one(
            {"order_id": order_id},
            {"$set": doc, "$setOnInsert": {"created_at": utc_now()}},
            upsert=True,
        )
        return self.find_by_order(order_id)

    def confirm_receipt(self, order_id, buyer_id):
        self.db.deliveries.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "buyer_id": buyer_id,
                    "status": "confirmed",
                    "confirmed_at": utc_now(),
                    "updated_at": utc_now(),
                },
                "$setOnInsert": {"order_id": order_id, "created_at": utc_now()},
            },
            upsert=True,
        )
        return self.find_by_order(order_id)

    def find_by_order(self, order_id):
        object_id = order_id if isinstance(order_id, ObjectId) else ObjectId(str(order_id))
        return self.db.deliveries.find_one({"order_id": object_id})

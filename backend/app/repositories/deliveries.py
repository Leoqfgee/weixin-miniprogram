from datetime import datetime, timezone

from bson import ObjectId


def utc_now():
    return datetime.now(timezone.utc)


class DeliveryRepository:
    def __init__(self, db):
        self.db = db

    def mark_delivering(self, order, seller_id, payload, delivery_type):
        doc = {
            "order_id": order["_id"],
            "seller_id": seller_id,
            "buyer_id": order["buyer_id"],
            "delivery_type": delivery_type,
            "status": "delivered",
            "meet_location": payload.get("meet_location") or order.get("meet_location", ""),
            "meet_time": payload.get("meet_time") or "",
            "pickup_location": payload.get("pickup_location") or "",
            "pickup_time_range": payload.get("pickup_time_range") or "",
            "pickup_code": payload.get("pickup_code") or "",
            "campus_address": payload.get("campus_address") or "",
            "delivery_note": payload.get("delivery_note") or "",
            "express_company": payload.get("express_company") or "",
            "tracking_no": payload.get("tracking_no") or "",
            "receiver_name": payload.get("receiver_name") or "",
            "receiver_phone": payload.get("receiver_phone") or "",
            "receiver_address": payload.get("receiver_address") or "",
            "proof_images": payload.get("proof_images") or [],
            "delivered_at": utc_now(),
            "confirmed_at": None,
            "updated_at": utc_now(),
        }
        self.db.deliveries.update_one(
            {"order_id": order["_id"]},
            {"$set": doc, "$setOnInsert": {"created_at": utc_now()}},
            upsert=True,
        )
        return self.find_by_order(order["_id"])

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

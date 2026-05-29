from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId


def utc_now():
    return datetime.now(timezone.utc)


class PaymentRepository:
    def __init__(self, db):
        self.db = db

    def create_for_order(self, order_id, amount, channel="mock"):
        doc = {
            "order_id": order_id,
            "amount": amount,
            "channel": channel,
            "status": "pending",
            "out_trade_no": f"MOCK{uuid4().hex}",
            "paid_at": None,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        result = self.db.payments.insert_one(doc)
        return self.find_by_id(result.inserted_id)

    def find_by_id(self, payment_id):
        object_id = payment_id if isinstance(payment_id, ObjectId) else ObjectId(str(payment_id))
        return self.db.payments.find_one({"_id": object_id})

    def find_by_order(self, order_id):
        object_id = order_id if isinstance(order_id, ObjectId) else ObjectId(str(order_id))
        return self.db.payments.find_one({"order_id": object_id})

    def update_fields(self, payment_id, fields):
        fields["updated_at"] = utc_now()
        self.db.payments.update_one({"_id": payment_id}, {"$set": fields})
        return self.find_by_id(payment_id)

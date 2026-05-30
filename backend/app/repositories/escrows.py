from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc)


class EscrowRepository:
    def __init__(self, db):
        self.db = db

    def find_by_order(self, order_id):
        return self.db.escrow_records.find_one({"order_id": order_id})

    def create_holding(self, order):
        existing = self.find_by_order(order["_id"])
        if existing:
            return existing
        doc = {
            "order_id": order["_id"],
            "buyer_id": order["buyer_id"],
            "seller_id": order["seller_id"],
            "amount": order["pay_amount"],
            "status": "holding",
            "hold_at": utc_now(),
            "settle_at": None,
            "refund_at": None,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        result = self.db.escrow_records.insert_one(doc)
        return self.find_by_id(result.inserted_id)

    def find_by_id(self, escrow_id):
        return self.db.escrow_records.find_one({"_id": escrow_id})

    def update_status(self, order_id, status):
        fields = {"status": status, "updated_at": utc_now()}
        if status == "settled":
            fields["settle_at"] = utc_now()
        if status == "refunded":
            fields["refund_at"] = utc_now()
        self.db.escrow_records.update_one({"order_id": order_id}, {"$set": fields})
        return self.find_by_order(order_id)

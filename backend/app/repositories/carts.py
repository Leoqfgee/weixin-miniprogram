from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc)


class CartRepository:
    def __init__(self, db):
        self.db = db

    def get_by_user(self, user_id):
        return self.db.carts.find_one({"user_id": user_id})

    def save_items(self, user_id, items):
        self.db.carts.update_one(
            {"user_id": user_id},
            {
                "$set": {"items": items, "updated_at": utc_now()},
                "$setOnInsert": {"created_at": utc_now()},
            },
            upsert=True,
        )
        return self.get_by_user(user_id)

    def clear_products(self, user_id, product_ids):
        cart = self.get_by_user(user_id)
        if not cart:
            return None
        product_id_set = {str(item) for item in product_ids}
        items = [item for item in cart.get("items", []) if str(item.get("product_id")) not in product_id_set]
        return self.save_items(user_id, items)

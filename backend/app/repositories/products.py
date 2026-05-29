from datetime import datetime, timezone

from bson import ObjectId
from pymongo import DESCENDING


def utc_now():
    return datetime.now(timezone.utc)


class ProductRepository:
    def __init__(self, db):
        self.db = db

    def create(self, product):
        product["created_at"] = utc_now()
        product["updated_at"] = utc_now()
        result = self.db.products.insert_one(product)
        return self.find_by_id(result.inserted_id)

    def find_by_id(self, product_id):
        object_id = product_id if isinstance(product_id, ObjectId) else ObjectId(str(product_id))
        return self.db.products.find_one({"_id": object_id, "status": {"$ne": "deleted"}})

    def update_fields(self, product_id, fields):
        fields["updated_at"] = utc_now()
        self.db.products.update_one({"_id": product_id}, {"$set": fields})
        return self.find_by_id(product_id)

    def lock_stock(self, product_id, quantity):
        result = self.db.products.update_one(
            {"_id": product_id, "status": "on_sale", "stock": {"$gte": quantity}},
            {"$inc": {"stock": -quantity}, "$set": {"updated_at": utc_now()}},
        )
        return result.modified_count == 1

    def release_stock(self, product_id, quantity):
        self.db.products.update_one(
            {"_id": product_id},
            {"$inc": {"stock": quantity}, "$set": {"updated_at": utc_now()}},
        )

    def list_public(self, filters, page, page_size):
        query = {"status": "on_sale"}
        if filters.get("category_id"):
            query["category_id"] = filters["category_id"]
        if filters.get("condition"):
            query["condition"] = filters["condition"]
        if filters.get("keyword"):
            query["$text"] = {"$search": filters["keyword"]}
        if filters.get("min_price") is not None or filters.get("max_price") is not None:
            price_query = {}
            if filters.get("min_price") is not None:
                price_query["$gte"] = filters["min_price"]
            if filters.get("max_price") is not None:
                price_query["$lte"] = filters["max_price"]
            query["price"] = price_query

        total = self.db.products.count_documents(query)
        items = list(
            self.db.products.find(query)
            .sort("created_at", DESCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return items, total

    def list_admin(self, status=None, page=1, page_size=20):
        query = {"status": status} if status else {"status": {"$ne": "deleted"}}
        total = self.db.products.count_documents(query)
        items = list(
            self.db.products.find(query)
            .sort("created_at", DESCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return items, total

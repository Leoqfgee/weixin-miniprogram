import re
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING


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
        return self.db.products.find_one({"_id": object_id})

    def update_fields(self, product_id, fields):
        fields["updated_at"] = utc_now()
        self.db.products.update_one({"_id": product_id}, {"$set": fields})
        return self.find_by_id(product_id)

    def increment_view_count(self, product_id):
        self.db.products.update_one({"_id": product_id}, {"$inc": {"view_count": 1}})
        return self.find_by_id(product_id)

    def lock_stock(self, product_id, quantity):
        result = self.db.products.update_one(
            {"_id": product_id, "status": "on_sale", "stock": {"$gte": quantity}},
            {"$inc": {"stock": -quantity}, "$set": {"status": "locked", "updated_at": utc_now()}},
        )
        return result.modified_count == 1

    def release_stock(self, product_id, quantity):
        self.db.products.update_one(
            {"_id": product_id, "status": "locked"},
            {"$inc": {"stock": quantity}, "$set": {"status": "on_sale", "updated_at": utc_now()}},
        )

    def mark_sold(self, product_id):
        self.db.products.update_one(
            {"_id": product_id, "status": "locked"},
            {"$set": {"status": "sold", "updated_at": utc_now()}},
        )
        return self.find_by_id(product_id)

    def mark_off_shelf_after_refund(self, product_id):
        self.db.products.update_one(
            {"_id": product_id},
            {"$set": {"status": "off_shelf", "stock": 0, "updated_at": utc_now()}},
        )
        return self.find_by_id(product_id)

    def list_public(self, filters, page, page_size):
        query = self.build_public_query(filters)
        sort = filters.get("sort") or "newest"
        total = self.db.products.count_documents(query)
        if sort == "hot":
            matched = list(self.db.products.find(query))
            matched.sort(
                key=lambda item: (
                    int(item.get("view_count", 0) or 0) + int(item.get("favorite_count", 0) or 0) * 3,
                    item.get("created_at"),
                ),
                reverse=True,
            )
            return matched[(page - 1) * page_size : page * page_size], total
        sort_options = {
            "newest": [("created_at", DESCENDING)],
            "price_asc": [("price", ASCENDING), ("created_at", DESCENDING)],
            "price_desc": [("price", DESCENDING), ("created_at", DESCENDING)],
        }
        items = list(
            self.db.products.find(query)
            .sort(sort_options.get(sort, sort_options["newest"]))
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return items, total

    def list_public_all(self, filters):
        query = self.build_public_query(filters)
        return list(self.db.products.find(query))

    def build_public_query(self, filters):
        query = {
            "status": "on_sale",
            "deleted_at": {"$exists": False},
            "stock": {"$gt": 0},
        }
        if filters.get("category_id"):
            query["category_id"] = filters["category_id"]
        elif filters.get("category_ids"):
            query["category_id"] = {"$in": filters["category_ids"]}
        if filters.get("exclude_seller_id"):
            query["seller_id"] = {"$ne": filters["exclude_seller_id"]}
        if filters.get("condition"):
            query["condition"] = filters["condition"]
        if filters.get("keyword"):
            keyword = re.escape(filters["keyword"])
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
            ]
        if filters.get("campus"):
            query["campus"] = {"$regex": re.escape(filters["campus"]), "$options": "i"}
        if filters.get("date_from") or filters.get("date_to"):
            date_query = {}
            if filters.get("date_from"):
                date_query["$gte"] = filters["date_from"]
            if filters.get("date_to"):
                date_query["$lte"] = filters["date_to"]
            query["created_at"] = date_query
        if filters.get("min_price") is not None or filters.get("max_price") is not None:
            price_query = {}
            if filters.get("min_price") is not None:
                price_query["$gte"] = filters["min_price"]
            if filters.get("max_price") is not None:
                price_query["$lte"] = filters["max_price"]
            query["price"] = price_query
        return query

    def list_mine(self, seller_id, status=None, page=1, page_size=20):
        query = {"seller_id": seller_id, "deleted_at": {"$exists": False}}
        if status:
            query["status"] = status
        total = self.db.products.count_documents(query)
        items = list(
            self.db.products.find(query)
            .sort("created_at", DESCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return items, total

    def list_admin(self, status=None, page=1, page_size=20):
        query = {"status": status} if status else {}
        total = self.db.products.count_documents(query)
        items = list(
            self.db.products.find(query)
            .sort("created_at", DESCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return items, total

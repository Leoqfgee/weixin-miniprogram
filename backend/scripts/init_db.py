import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import CollectionInvalid
from werkzeug.security import generate_password_hash

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import Config  # noqa: E402


COLLECTIONS = [
    "users",
    "user_profiles",
    "categories",
    "products",
    "favorites",
    "carts",
    "orders",
    "order_items",
    "payments",
    "escrow_records",
    "deliveries",
    "messages",
    "reviews",
    "refunds",
    "appeals",
    "operation_logs",
    "business_logs",
    "ai_generation_logs",
    "files",
    "idempotency_keys",
]


BASE_CATEGORIES = [
    {"code": "digital", "name": "数码电子", "sort": 10},
    {"code": "book", "name": "教材书籍", "sort": 20},
    {"code": "daily", "name": "生活用品", "sort": 30},
    {"code": "sport", "name": "运动户外", "sort": 40},
    {"code": "clothing", "name": "服饰鞋包", "sort": 50},
    {"code": "other", "name": "其他", "sort": 99},
]


TEST_USERS = [
    {
        "openid": "mock_admin_openid",
        "phone": "18800000000",
        "password": "admin123456",
        "roles": ["admin"],
        "nickname": "测试管理员",
        "campus": "主校区",
        "student_no": "ADMIN001",
        "verified_status": "approved",
    },
    {
        "openid": "mock_seller_openid",
        "phone": "18800000001",
        "password": "seller123456",
        "roles": ["buyer", "seller"],
        "nickname": "测试卖家",
        "campus": "主校区",
        "student_no": "S2026001",
        "verified_status": "approved",
    },
    {
        "openid": "mock_buyer_openid",
        "phone": "18800000002",
        "password": "buyer123456",
        "roles": ["buyer"],
        "nickname": "测试买家",
        "campus": "东校区",
        "student_no": "B2026001",
        "verified_status": "approved",
    },
]


def now():
    return datetime.now(timezone.utc)


def ensure_collections(db):
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name in existing:
            continue
        try:
            db.create_collection(name)
            print(f"created collection: {name}")
        except CollectionInvalid:
            pass


def ensure_indexes(db):
    # 用户与资料
    db.users.create_index([("openid", ASCENDING)], unique=True, sparse=True)
    db.users.create_index([("phone", ASCENDING)], unique=True, sparse=True)
    db.users.create_index([("status", ASCENDING)])
    db.user_profiles.create_index([("user_id", ASCENDING)], unique=True)
    db.user_profiles.create_index([("verified_status", ASCENDING)])

    # 商品、分类、收藏、购物车
    db.categories.create_index([("code", ASCENDING)], unique=True)
    db.categories.create_index([("parent_id", ASCENDING), ("sort", ASCENDING)])
    db.products.create_index(
        [("seller_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)]
    )
    db.products.create_index(
        [("category_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)]
    )
    db.products.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    db.products.create_index([("title", "text"), ("description", "text")])
    db.products.create_index([("seed_code", ASCENDING)], unique=True, sparse=True)
    db.favorites.create_index([("user_id", ASCENDING), ("product_id", ASCENDING)], unique=True)
    db.carts.create_index([("user_id", ASCENDING)], unique=True)

    # 订单、支付、交付
    db.orders.create_index([("buyer_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)])
    db.orders.create_index([("seller_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)])
    db.orders.create_index([("product_id", ASCENDING)])
    db.orders.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    db.orders.create_index([("order_no", ASCENDING)], unique=True, sparse=True)
    db.orders.create_index([("idempotency_key", ASCENDING)], unique=True, sparse=True)
    db.order_items.create_index([("order_id", ASCENDING)])
    _drop_index_if_exists(db.payments, "order_id_1")
    db.payments.create_index([("order_id", ASCENDING)], unique=True, name="uniq_payment_order_id")
    db.payments.create_index([("transaction_no", ASCENDING)], unique=True, sparse=True)
    db.payments.create_index([("idempotency_key", ASCENDING)], unique=True, sparse=True)
    db.escrow_records.create_index([("order_id", ASCENDING)], unique=True)
    db.escrow_records.create_index([("buyer_id", ASCENDING), ("status", ASCENDING)])
    db.escrow_records.create_index([("seller_id", ASCENDING), ("status", ASCENDING)])
    _drop_index_if_exists(db.deliveries, "order_id_1")
    db.deliveries.create_index([("order_id", ASCENDING)], unique=True, name="uniq_delivery_order_id")

    # 消息、评价、退款、申诉、日志
    db.messages.create_index([("conversation_id", ASCENDING), ("created_at", ASCENDING)])
    db.messages.create_index([("receiver_id", ASCENDING), ("read_at", ASCENDING)])
    db.reviews.create_index([("order_id", ASCENDING), ("reviewer_id", ASCENDING)], unique=True)
    db.refunds.create_index([("order_id", ASCENDING), ("status", ASCENDING)])
    db.refunds.create_index([("buyer_id", ASCENDING), ("status", ASCENDING)])
    db.refunds.create_index([("seller_id", ASCENDING), ("status", ASCENDING)])
    db.appeals.create_index([("order_id", ASCENDING)])
    db.appeals.create_index([("refund_id", ASCENDING)])
    db.appeals.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    db.operation_logs.create_index([("target_type", ASCENDING), ("target_id", ASCENDING)])
    db.operation_logs.create_index([("trace_id", ASCENDING)])
    db.business_logs.create_index([("biz_type", ASCENDING), ("biz_id", ASCENDING)])
    db.business_logs.create_index([("target_type", ASCENDING), ("target_id", ASCENDING)])
    db.business_logs.create_index([("operator_id", ASCENDING), ("created_at", DESCENDING)])
    db.ai_generation_logs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.files.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
    db.idempotency_keys.create_index([("key", ASCENDING)], unique=True)


def _drop_index_if_exists(collection, name):
    if name in collection.index_information():
        collection.drop_index(name)


def seed_categories(db):
    for category in BASE_CATEGORIES:
        doc = {
            **category,
            "parent_id": None,
            "enabled": True,
            "updated_at": now(),
        }
        db.categories.update_one(
            {"code": category["code"]},
            {"$set": doc, "$setOnInsert": {"created_at": now()}},
            upsert=True,
        )
    print(f"seeded categories: {len(BASE_CATEGORIES)}")


def seed_users(db):
    for item in TEST_USERS:
        user_doc = {
            "openid": item["openid"],
            "phone": item["phone"],
            "password_hash": generate_password_hash(item["password"]),
            "roles": item["roles"],
            "status": "active",
            "updated_at": now(),
        }
        result = db.users.update_one(
            {"openid": item["openid"]},
            {"$set": user_doc, "$setOnInsert": {"created_at": now()}},
            upsert=True,
        )
        user = db.users.find_one({"openid": item["openid"]})
        profile_doc = {
            "user_id": user["_id"],
            "nickname": item["nickname"],
            "avatar_url": "",
            "campus": item["campus"],
            "student_no": item["student_no"],
            "verified_status": item["verified_status"],
            "credit_score": 100,
            "updated_at": now(),
        }
        db.user_profiles.update_one(
            {"user_id": user["_id"]},
            {"$set": profile_doc, "$setOnInsert": {"created_at": now()}},
            upsert=True,
        )
        action = "created" if result.upserted_id else "updated"
        print(f"{action} user: {item['nickname']} / {item['phone']}")


def seed_products(db):
    seller = db.users.find_one({"openid": "mock_seller_openid"})
    admin = db.users.find_one({"openid": "mock_admin_openid"})
    if not seller:
        print("skip products: seller user not found")
        return

    categories = {item["code"]: item for item in db.categories.find({"enabled": True})}
    demo_products = [
        {
            "seed_code": "demo_keyboard",
            "title": "九成新机械键盘",
            "description": "青轴机械键盘，按键灵敏，适合宿舍学习和编程使用。",
            "price": 99.0,
            "original_price": 199.0,
            "category_code": "digital",
            "condition": "good",
            "stock": 3,
            "images": ["/uploads/demo/keyboard.jpg"],
            "campus": "主校区",
            "delivery_options": ["meetup", "express"],
            "status": "on_sale",
        },
        {
            "seed_code": "demo_math_books",
            "title": "高等数学教材套装",
            "description": "高数上下册加习题册，书页完整，适合期末复习。",
            "price": 35.0,
            "original_price": 88.0,
            "category_code": "book",
            "condition": "fair",
            "stock": 5,
            "images": ["/uploads/demo/math-books.jpg"],
            "campus": "东校区",
            "delivery_options": ["meetup"],
            "status": "on_sale",
        },
        {
            "seed_code": "demo_pending_lamp",
            "title": "宿舍护眼台灯",
            "description": "三档亮度，可 USB 供电，待管理员审核演示使用。",
            "price": 45.0,
            "original_price": 79.0,
            "category_code": "daily",
            "condition": "like_new",
            "stock": 2,
            "images": ["/uploads/demo/lamp.jpg"],
            "campus": "主校区",
            "delivery_options": ["meetup"],
            "status": "pending_review",
        },
    ]

    count = 0
    for item in demo_products:
        category = categories.get(item.pop("category_code"))
        if not category:
            continue
        status = item["status"]
        review = {"result": "", "reason": "", "audited_by": None, "audited_at": None}
        if status == "on_sale":
            review = {
                "result": "approved",
                "reason": "初始化演示数据",
                "audited_by": admin["_id"] if admin else None,
                "audited_at": now(),
            }
        product_doc = {
            **item,
            "seller_id": seller["_id"],
            "category_id": category["_id"],
            "cover_image": item["images"][0] if item["images"] else "",
            "review": review,
            "sold_count": 0,
            "updated_at": now(),
        }
        db.products.update_one(
            {"seed_code": item["seed_code"]},
            {"$set": product_doc, "$setOnInsert": {"created_at": now()}},
            upsert=True,
        )
        count += 1
    print(f"seeded demo products: {count}")


def main():
    mongo_uri = os.getenv("MONGO_URI", Config.MONGO_URI)
    db_name = os.getenv("MONGO_DB_NAME", Config.MONGO_DB_NAME)
    client = MongoClient(mongo_uri)
    try:
        db = client[db_name]
        db.command("ping")
        ensure_collections(db)
        ensure_indexes(db)
        seed_categories(db)
        seed_users(db)
        seed_products(db)
        print(f"database initialized: {db_name}")
    finally:
        client.close()


if __name__ == "__main__":
    main()

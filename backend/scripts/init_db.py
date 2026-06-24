import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import CollectionInvalid
from werkzeug.security import generate_password_hash

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import Config  # noqa: E402
from app.domain.categories import CATEGORY_DEFINITIONS, category_name  # noqa: E402
from app.services.content_moderation import DEFAULT_BANNED_WORDS  # noqa: E402


COLLECTIONS = [
    "users",
    "user_profiles",
    "addresses",
    "categories",
    "products",
    "favorites",
    "orders",
    "order_items",
    "payments",
    "escrow_records",
    "deliveries",
    "messages",
    "reviews",
    "reports",
    "student_verifications",
    "banned_words",
    "content_block_records",
    "refunds",
    "appeals",
    "operation_logs",
    "business_logs",
    "ai_generation_logs",
    "files",
    "product_views",
    "idempotency_keys",
]


BASE_CATEGORIES = CATEGORY_DEFINITIONS


TEST_USERS = [
    {
        "openid": "mock_admin_openid",
        "phone": "18800000000",
        "password": "admin123456",
        "roles": ["admin"],
        "nickname": "测试管理员",
        "campus": "东校区",
        "student_no": "ADMIN001",
        "verified_status": "approved",
    },
    {
        "openid": "mock_seller_openid",
        "phone": "18800000001",
        "password": "seller123456",
        "roles": ["buyer", "seller"],
        "nickname": "测试卖家",
        "campus": "西校区",
        "student_no": "S2026001",
        "verified_status": "approved",
    },
    {
        "openid": "mock_buyer_openid",
        "phone": "18800000002",
        "password": "buyer123456",
        "roles": ["buyer", "seller"],
        "nickname": "测试买家A",
        "campus": "东校区",
        "student_no": "B2026001",
        "verified_status": "approved",
    },
    {
        "openid": "mock_buyer_b_openid",
        "phone": "18800000003",
        "password": "buyerb123456",
        "roles": ["buyer", "seller"],
        "nickname": "测试买家B",
        "campus": "西校区",
        "student_no": "B2026002",
        "verified_status": "approved",
    },
]


DEMO_PRODUCTS = [
    {
        "seed_code": "demo_logitech_mouse",
        "title": "罗技静音无线鼠标",
        "description": "轻微使用痕迹，按键灵敏，适合宿舍学习和办公。",
        "price": 39.0,
        "category_code": "digital",
        "condition": "good",
        "stock": 2,
        "images": ["/assets/images/demo-mouse.png"],
        "campus": "东校区",
        "delivery_options": ["meetup"],
        "view_count": 16,
        "favorite_count": 2,
    },
    {
        "seed_code": "demo_math_books",
        "title": "高等数学教材套装",
        "description": "高数上下册加习题册，笔记少，适合期末复习。",
        "price": 35.0,
        "category_code": "book",
        "condition": "fair",
        "stock": 4,
        "images": ["/assets/images/demo-books.png"],
        "campus": "东校区",
        "delivery_options": ["meetup"],
        "view_count": 28,
        "favorite_count": 4,
    },
    {
        "seed_code": "demo_desk_lamp",
        "title": "宿舍护眼台灯",
        "description": "三档亮度，可 USB 供电，晚上看书不刺眼。",
        "price": 42.0,
        "category_code": "home",
        "condition": "like_new",
        "stock": 1,
        "images": ["/assets/images/demo-lamp.png"],
        "campus": "西校区",
        "delivery_options": ["meetup", "express"],
        "view_count": 19,
        "favorite_count": 3,
    },
    {
        "seed_code": "demo_basketball",
        "title": "斯伯丁室外篮球",
        "description": "手感好，气很足，适合操场和球场日常训练。",
        "price": 58.0,
        "category_code": "other",
        "condition": "good",
        "stock": 1,
        "images": ["/assets/images/demo-basketball.png"],
        "campus": "西校区",
        "delivery_options": ["meetup"],
        "view_count": 11,
        "favorite_count": 1,
    },
    {
        "seed_code": "demo_backpack",
        "title": "通勤双肩背包",
        "description": "容量大，可放电脑，拉链顺滑，适合上课和短途出行。",
        "price": 49.0,
        "category_code": "clothing",
        "condition": "good",
        "stock": 1,
        "images": ["/assets/images/demo-backpack.png"],
        "campus": "东校区",
        "delivery_options": ["meetup"],
        "view_count": 24,
        "favorite_count": 2,
    },
    {
        "seed_code": "demo_headphones",
        "title": "头戴式蓝牙耳机",
        "description": "续航正常，耳罩干净，适合自习室听课和通勤。",
        "price": 75.0,
        "category_code": "digital",
        "condition": "good",
        "stock": 1,
        "images": ["/assets/images/demo-headphones.png"],
        "campus": "东校区",
        "delivery_options": ["meetup", "express"],
        "view_count": 31,
        "favorite_count": 5,
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
    _drop_index_if_exists(db.orders, "idempotency_key_1")
    _drop_index_if_exists(db.payments, "idempotency_key_1")

    db.users.create_index([("openid", ASCENDING)], unique=True, sparse=True)
    db.users.create_index([("phone", ASCENDING)], unique=True, sparse=True)
    db.users.create_index([("status", ASCENDING)])
    db.user_profiles.create_index([("user_id", ASCENDING)], unique=True)
    db.user_profiles.create_index([("verified_status", ASCENDING)])
    db.addresses.create_index([("user_id", ASCENDING), ("is_default", DESCENDING), ("created_at", DESCENDING)])

    db.categories.create_index([("code", ASCENDING)], unique=True)
    db.categories.create_index([("parent_id", ASCENDING), ("sort", ASCENDING)])
    db.products.create_index([("seller_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)])
    db.products.create_index([("category_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)])
    db.products.create_index([("category", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)])
    db.products.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    db.products.create_index([("status", ASCENDING), ("price", ASCENDING)])
    db.products.create_index([("status", ASCENDING), ("campus", ASCENDING)])
    db.products.create_index([("status", ASCENDING), ("view_count", DESCENDING)])
    db.products.create_index([("title", "text"), ("description", "text")])
    db.products.create_index([("seed_code", ASCENDING)], unique=True, sparse=True)
    db.favorites.create_index([("user_id", ASCENDING), ("product_id", ASCENDING)], unique=True)

    db.orders.create_index([("buyer_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)])
    db.orders.create_index([("seller_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)])
    db.orders.create_index([("product_id", ASCENDING)])
    db.orders.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    db.orders.create_index([("order_no", ASCENDING)], unique=True, sparse=True)
    db.orders.create_index(
        [("idempotency_key", ASCENDING)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    db.order_items.create_index([("order_id", ASCENDING)])
    _drop_index_if_exists(db.payments, "order_id_1")
    db.payments.create_index([("order_id", ASCENDING)], unique=True, name="uniq_payment_order_id")
    db.payments.create_index([("transaction_no", ASCENDING)], unique=True, sparse=True)
    db.payments.create_index(
        [("idempotency_key", ASCENDING)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    db.escrow_records.create_index([("order_id", ASCENDING)], unique=True)
    db.escrow_records.create_index([("buyer_id", ASCENDING), ("status", ASCENDING)])
    db.escrow_records.create_index([("seller_id", ASCENDING), ("status", ASCENDING)])
    _drop_index_if_exists(db.deliveries, "order_id_1")
    db.deliveries.create_index([("order_id", ASCENDING)], unique=True, name="uniq_delivery_order_id")

    db.messages.create_index([("conversation_id", ASCENDING), ("created_at", ASCENDING)])
    db.messages.create_index([("receiver_id", ASCENDING), ("read_at", ASCENDING)])
    db.reviews.create_index([("order_id", ASCENDING), ("reviewer_id", ASCENDING)], unique=True)
    db.reviews.create_index([("reviewee_id", ASCENDING), ("created_at", DESCENDING)])
    db.reports.create_index([("target_type", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)])
    db.reports.create_index([("reporter_id", ASCENDING), ("target_user_id", ASCENDING), ("status", ASCENDING)])
    db.reports.create_index([("reporter_id", ASCENDING), ("product_id", ASCENDING), ("status", ASCENDING)])
    db.student_verifications.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
    db.student_verifications.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    db.banned_words.create_index([("word", ASCENDING)], unique=True)
    db.banned_words.create_index([("enabled", ASCENDING), ("category", ASCENDING)])
    db.content_block_records.create_index([("scene", ASCENDING), ("created_at", DESCENDING)])
    db.content_block_records.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
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
    db.product_views.create_index([("user_id", ASCENDING), ("product_id", ASCENDING)], unique=True)
    db.product_views.create_index([("user_id", ASCENDING), ("viewed_at", DESCENDING)])
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


def seed_banned_words(db):
    count = 0
    for item in DEFAULT_BANNED_WORDS:
        db.banned_words.update_one(
            {"word": item["word"]},
            {
                "$set": {
                    "category": item.get("category", "default"),
                    "severity": item.get("severity", "medium"),
                    "enabled": True,
                    "updated_at": now(),
                },
                "$setOnInsert": {"created_at": now()},
            },
            upsert=True,
        )
        count += 1
    print(f"seeded banned words: {count}")


def seed_users(db):
    for item in TEST_USERS:
        user_doc = {
            "openid": item["openid"],
            "phone": item["phone"],
            "password_hash": generate_password_hash(item["password"]),
            "roles": item["roles"],
            "status": "active",
            "nickname": item["nickname"],
            "avatar_url": "",
            "profile_completed": True,
            "identity_type": "custom",
            "last_login_at": now(),
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
            "avatar": "",
            "profile_completed": True,
            "identity_type": "custom",
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


def reset_demo_products(db):
    seed_codes = [item["seed_code"] for item in DEMO_PRODUCTS]
    legacy_query = {
        "$or": [
            {"seed_code": {"$exists": True}},
            {"title": {"$regex": r"^COS", "$options": "i"}},
            {"title": {"$regex": r"^pytest-", "$options": "i"}},
        ]
    }
    legacy_products = list(db.products.find(legacy_query))
    legacy_ids = [item["_id"] for item in legacy_products]
    deleted_products = db.products.delete_many({"_id": {"$in": legacy_ids}}).deleted_count if legacy_ids else 0
    if legacy_ids:
        db.favorites.delete_many({"product_id": {"$in": legacy_ids}})
        db.product_views.delete_many({"product_id": {"$in": legacy_ids}})
    seed_products(db, seed_codes=seed_codes)
    return {"deleted_products": deleted_products, "created_or_updated_products": len(seed_codes)}


def seed_products(db, seed_codes=None):
    seller = db.users.find_one({"openid": "mock_seller_openid"})
    admin = db.users.find_one({"openid": "mock_admin_openid"})
    if not seller:
        print("skip products: seller user not found")
        return

    selected_codes = set(seed_codes or [item["seed_code"] for item in DEMO_PRODUCTS])
    categories = {item["code"]: item for item in db.categories.find({"enabled": True})}
    count = 0
    for item in DEMO_PRODUCTS:
        if item["seed_code"] not in selected_codes:
            continue
        category = categories.get(item["category_code"])
        if not category:
            continue
        images = list(item["images"])
        product_doc = {
            "seed_code": item["seed_code"],
            "title": item["title"],
            "description": item["description"],
            "price": item["price"],
            "category_id": category["_id"],
            "category": category["code"],
            "category_name": category_name(category["code"]),
            "category_source": "seed",
            "condition": item["condition"],
            "stock": item["stock"],
            "images": images,
            "cover_image": images[0] if images else "",
            "campus": item["campus"],
            "delivery_options": item["delivery_options"],
            "status": "on_sale",
            "review": {
                "result": "approved",
                "reason": "初始化演示数据",
                "audited_by": admin["_id"] if admin else None,
                "audited_at": now(),
            },
            "seller_id": seller["_id"],
            "sold_count": 0,
            "view_count": item["view_count"],
            "favorite_count": item["favorite_count"],
            "updated_at": now(),
        }
        db.products.update_one(
            {"seed_code": item["seed_code"]},
            {"$set": product_doc, "$setOnInsert": {"created_at": now()}},
            upsert=True,
        )
        count += 1
    print(f"seeded demo products: {count}")


def get_db():
    if Config.DB_BACKEND == "mysql":
        from app.mysql_document import MySQLDocumentDB

        return MySQLDocumentDB(
            {
                "MYSQL_HOST": Config.MYSQL_HOST,
                "MYSQL_PORT": Config.MYSQL_PORT,
                "MYSQL_USERNAME": Config.MYSQL_USERNAME,
                "MYSQL_PASSWORD": Config.MYSQL_PASSWORD,
                "MYSQL_DATABASE": Config.MYSQL_DATABASE,
            }
        ), None

    mongo_uri = os.getenv("MONGO_URI", Config.MONGO_URI)
    db_name = os.getenv("MONGO_DB_NAME", Config.MONGO_DB_NAME)
    client = MongoClient(mongo_uri)
    return client[db_name], client


def close_db(db, client=None):
    if client:
        client.close()
        return
    close = getattr(type(db), "close", None)
    if callable(close):
        db.close()


def initialize_database(reset_demo=False):
    db, client = get_db()
    try:
        db.command("ping")
        ensure_collections(db)
        ensure_indexes(db)
        seed_categories(db)
        seed_banned_words(db)
        seed_users(db)
        result = reset_demo_products(db) if reset_demo else {"created_or_updated_products": 0}
        if not reset_demo:
            seed_products(db)
        backend_name = Config.MYSQL_DATABASE if Config.DB_BACKEND == "mysql" else Config.MONGO_DB_NAME
        print(f"database initialized: {Config.DB_BACKEND}/{backend_name}")
        return result
    finally:
        close_db(db, client)


def main():
    reset_demo = "--reset-demo" in sys.argv
    initialize_database(reset_demo=reset_demo)


if __name__ == "__main__":
    main()

from uuid import uuid4

from bson import ObjectId

from app import create_app
from scripts.init_db import main as init_db


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, phone, password):
    response = client.post("/api/v1/auth/password-login", json={"phone": phone, "password": password})
    assert response.status_code == 200
    return response.get_json()["data"]["token"]


def setup_app():
    init_db()
    app = create_app()
    client = app.test_client()
    app.db.products.delete_many({"title": {"$regex": "^pytest-report-"}})
    app.db.reports.delete_many({"product_title_snapshot": {"$regex": "^pytest-report-"}})
    app.db.credit_records.delete_many({})
    seller_token = login(client, "18800000001", "seller123456")
    buyer_token = login(client, "18800000002", "buyer123456")
    buyer_b_token = login(client, "18800000003", "buyerb123456")
    admin_token = login(client, "18800000000", "admin123456")
    return app, client, seller_token, buyer_token, buyer_b_token, admin_token


def create_product(client, seller_token, title=None):
    category_id = client.get("/api/v1/categories").get_json()["data"]["items"][0]["id"]
    title = title or f"pytest-report-{uuid4().hex}"
    response = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": title,
            "description": "举报与信用分测试商品",
            "price": 18.5,
            "category_id": category_id,
            "condition": "good",
            "stock": 2,
            "images": ["https://example.com/report.png"],
            "campus": "东校区",
            "delivery_options": ["meetup"],
            "submit_action": "publish",
        },
    )
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["status"] == "on_sale"
    return data


def test_publish_is_on_sale_and_low_credit_blocks_publish_and_chat():
    app, client, seller_token, buyer_token, _, _ = setup_app()
    product = create_product(client, seller_token)
    public = client.get(f"/api/v1/products?keyword={product['title']}")
    assert public.status_code == 200
    assert public.get_json()["data"]["items"][0]["status"] == "on_sale"

    seller = app.db.users.find_one({"phone": "18800000001"})
    app.db.user_profiles.update_one({"user_id": seller["_id"]}, {"$set": {"credit_score": 55}})
    blocked = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": f"pytest-report-{uuid4().hex}",
            "description": "低信用禁止发布",
            "price": 9,
            "category": "book",
            "stock": 1,
            "campus": "东校区",
            "submit_action": "publish",
        },
    )
    assert blocked.status_code == 403
    credit = client.get("/api/v1/users/me/credit", headers=auth_headers(seller_token)).get_json()["data"]
    assert credit["credit_score"] == 55
    assert credit["can_publish"] is False
    assert credit["need_score_to_publish"] == 5

    chat = client.post(
        "/api/v1/messages",
        headers=auth_headers(seller_token),
        json={"receiver_id": app.db.users.find_one({"phone": "18800000002"})["_id"].__str__(), "content": "hello"},
    )
    assert chat.status_code == 403
    buy = client.post("/api/v1/orders", headers=auth_headers(buyer_token), json={"product_id": product["id"]})
    assert buy.status_code == 201


def test_report_approved_takes_product_down_deducts_credit_and_notifies_users():
    app, client, seller_token, buyer_token, _, admin_token = setup_app()
    product = create_product(client, seller_token)
    seller = app.db.users.find_one({"phone": "18800000001"})
    buyer = app.db.users.find_one({"phone": "18800000002"})

    own_report = client.post(
        "/api/v1/reports",
        headers=auth_headers(seller_token),
        json={"product_id": product["id"], "reason_type": "fake_info"},
    )
    assert own_report.status_code == 403

    report_response = client.post(
        "/api/v1/reports",
        headers=auth_headers(buyer_token),
        json={"product_id": product["id"], "reason_type": "prohibited", "description": "疑似违规", "evidence_images": []},
    )
    assert report_response.status_code == 201
    report = report_response.get_json()["data"]
    duplicate = client.post(
        "/api/v1/reports",
        headers=auth_headers(buyer_token),
        json={"product_id": product["id"], "reason_type": "prohibited"},
    )
    assert duplicate.status_code == 409

    pending = client.get("/api/v1/admin/reports?status=pending", headers=auth_headers(admin_token))
    assert pending.status_code == 200
    assert pending.get_json()["data"]["pending_count"] >= 1

    handled = client.post(
        f"/api/v1/admin/reports/{report['id']}/handle",
        headers=auth_headers(admin_token),
        json={"result": "approved", "admin_note": "违规内容成立", "credit_deduct": 20},
    )
    assert handled.status_code == 200
    assert handled.get_json()["data"]["status_text"] == "举报成立"
    product_doc = app.db.products.find_one({"_id": ObjectId(product["id"])})
    assert product_doc["status"] == "taken_down"
    assert app.db.user_profiles.find_one({"user_id": seller["_id"]})["credit_score"] == 80
    assert app.db.credit_records.count_documents({"user_id": seller["_id"], "related_report_id": ObjectId(report["id"])}) == 1
    assert client.get(f"/api/v1/products?keyword={product['title']}").get_json()["data"]["items"] == []
    assert app.db.messages.count_documents({"receiver_id": seller["_id"], "system_action": "product_taken_down_by_report"}) == 1
    assert app.db.messages.count_documents({"receiver_id": buyer["_id"], "system_action": "report_approved"}) == 1
    after = client.get("/api/v1/admin/reports?status=pending", headers=auth_headers(admin_token)).get_json()["data"]
    assert all(item["id"] != report["id"] for item in after["items"])


def test_report_rejected_and_malicious_do_not_take_product_down_and_apply_expected_credit():
    app, client, seller_token, buyer_token, buyer_b_token, admin_token = setup_app()
    first = create_product(client, seller_token)
    second = create_product(client, seller_token)
    buyer_b = app.db.users.find_one({"phone": "18800000003"})

    rejected_report = client.post(
        "/api/v1/reports",
        headers=auth_headers(buyer_token),
        json={"product_id": first["id"], "reason_type": "fake_info"},
    ).get_json()["data"]
    rejected = client.post(
        f"/api/v1/admin/reports/{rejected_report['id']}/handle",
        headers=auth_headers(admin_token),
        json={"result": "rejected", "admin_note": "未发现违规", "credit_deduct": 0},
    )
    assert rejected.status_code == 200
    assert app.db.products.find_one({"_id": ObjectId(first["id"])})["status"] == "on_sale"

    malicious_report = client.post(
        "/api/v1/reports",
        headers=auth_headers(buyer_b_token),
        json={"product_id": second["id"], "reason_type": "other"},
    ).get_json()["data"]
    malicious = client.post(
        f"/api/v1/admin/reports/{malicious_report['id']}/handle",
        headers=auth_headers(admin_token),
        json={"result": "malicious", "admin_note": "恶意举报", "credit_deduct": 5},
    )
    assert malicious.status_code == 200
    assert app.db.products.find_one({"_id": ObjectId(second["id"])})["status"] == "on_sale"
    assert app.db.user_profiles.find_one({"user_id": buyer_b["_id"]})["credit_score"] == 95
    assert app.db.credit_records.count_documents({"user_id": buyer_b["_id"], "related_report_id": ObjectId(malicious_report["id"])}) == 1

from uuid import uuid4

from app import create_app
from scripts.init_db import main as init_db


def auth_headers(token, idem=None):
    headers = {"Authorization": f"Bearer {token}"}
    if idem:
        headers["X-Idempotency-Key"] = idem
    return headers


def login(client, phone, password):
    response = client.post("/api/v1/auth/mock-login", json={"phone": phone, "password": password})
    assert response.status_code == 200
    return response.get_json()["data"]


def create_product_and_order(client, seller_token, admin_token, buyer_token):
    category_id = client.get("/api/v1/categories").get_json()["data"]["items"][0]["id"]
    product_response = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": f"pytest-phase6-{uuid4().hex}",
            "description": "第六阶段测试商品",
            "price": 88,
            "category_id": category_id,
            "condition": "good",
            "stock": 2,
            "images": [],
            "campus": "主校区",
            "delivery_options": ["meetup"],
            "submit_action": "review",
        },
    )
    product_id = product_response.get_json()["data"]["id"]
    client.post(
        f"/api/v1/admin/products/{product_id}/audit",
        headers=auth_headers(admin_token),
        json={"result": "approved", "reason": "第六阶段测试"},
    )
    order_response = client.post(
        "/api/v1/orders",
        headers=auth_headers(buyer_token, f"phase6-{uuid4().hex}"),
        json={"product_id": product_id, "quantity": 1},
    )
    order = order_response.get_json()["data"]
    client.post(
        "/api/v1/payments/mock-confirm",
        headers=auth_headers(buyer_token),
        json={"payment_id": order["payment"]["id"], "mock_result": "success"},
    )
    return product_id, order["id"]


def test_phase6_message_review_refund_ai_and_admin_reports():
    init_db()
    app = create_app()
    client = app.test_client()

    seller = login(client, "18800000001", "seller123456")
    buyer = login(client, "18800000002", "buyer123456")
    admin = login(client, "18800000000", "admin123456")

    product_id, order_id = create_product_and_order(client, seller["token"], admin["token"], buyer["token"])
    product_detail = client.get(f"/api/v1/products/{product_id}", headers=auth_headers(buyer["token"])).get_json()["data"]

    message_response = client.post(
        "/api/v1/messages",
        headers=auth_headers(buyer["token"]),
        json={
            "receiver_id": product_detail["seller"]["id"],
            "product_id": product_id,
            "content": "商品还在吗？",
        },
    )
    assert message_response.status_code == 201
    conversations = client.get("/api/v1/messages/conversations", headers=auth_headers(seller["token"]))
    assert conversations.status_code == 200
    assert conversations.get_json()["data"]["items"]

    ai_response = client.post(
        "/api/v1/ai/product-copy",
        headers=auth_headers(seller["token"]),
        json={"keywords": "蓝牙耳机"},
    )
    assert ai_response.status_code == 200
    assert "description" in ai_response.get_json()["data"]

    confirm_response = client.post(f"/api/v1/deliveries/{order_id}/confirm", headers=auth_headers(buyer["token"]))
    assert confirm_response.status_code == 200

    review_response = client.post(
        "/api/v1/reviews",
        headers=auth_headers(buyer["token"]),
        json={"order_id": order_id, "rating": 5, "content": "交易顺利"},
    )
    assert review_response.status_code == 201

    refund_response = client.post(
        "/api/v1/refunds",
        headers=auth_headers(buyer["token"]),
        json={"order_id": order_id, "amount": 20, "reason": "课程退款演示", "evidence_images": []},
    )
    assert refund_response.status_code == 201
    refund_id = refund_response.get_json()["data"]["id"]

    seller_handle = client.post(
        f"/api/v1/refunds/{refund_id}/seller-handle",
        headers=auth_headers(seller["token"]),
        json={"result": "rejected", "reason": "需要平台介入"},
    )
    assert seller_handle.status_code == 200
    assert seller_handle.get_json()["data"]["status"] == "arbitration"

    arbitrate = client.post(
        f"/api/v1/admin/refunds/{refund_id}/arbitrate",
        headers=auth_headers(admin["token"]),
        json={"result": "approved", "reason": "管理员仲裁通过"},
    )
    assert arbitrate.status_code == 200
    assert arbitrate.get_json()["data"]["status"] == "approved"

    stats = client.get("/api/v1/admin/stats", headers=auth_headers(admin["token"]))
    assert stats.status_code == 200
    assert stats.get_json()["data"]["orders"] >= 1

    logs = client.get("/api/v1/admin/operation-logs", headers=auth_headers(admin["token"]))
    assert logs.status_code == 200
    assert logs.get_json()["data"]["items"]

    notifications = client.get("/api/v1/notifications", headers=auth_headers(buyer["token"]))
    assert notifications.status_code == 200

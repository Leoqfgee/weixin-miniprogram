from uuid import uuid4

from bson import ObjectId

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
    return response.get_json()["data"]["token"]


def create_on_sale_product(client, seller_token, admin_token, stock=3, price=99.0):
    category_id = client.get("/api/v1/categories").get_json()["data"]["items"][0]["id"]
    title = f"pytest-trade-{uuid4().hex}"
    create_response = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": title,
            "description": "第三阶段交易闭环测试商品。",
            "price": price,
            "category_id": category_id,
            "condition": "good",
            "stock": stock,
            "images": [],
            "campus": "主校区",
            "delivery_options": ["meetup"],
            "submit_action": "review",
        },
    )
    assert create_response.status_code == 201
    product_id = create_response.get_json()["data"]["id"]

    audit_response = client.post(
        f"/api/v1/admin/products/{product_id}/audit",
        headers=auth_headers(admin_token),
        json={"result": "approved", "reason": "交易测试通过"},
    )
    assert audit_response.status_code == 200
    return product_id, title


def test_cart_order_payment_and_confirm_flow():
    init_db()
    app = create_app()
    client = app.test_client()
    app.db.products.delete_many({"title": {"$regex": "^pytest-trade-"}})

    seller_token = login(client, "18800000001", "seller123456")
    buyer_token = login(client, "18800000002", "buyer123456")
    admin_token = login(client, "18800000000", "admin123456")
    product_id, _ = create_on_sale_product(client, seller_token, admin_token, stock=3, price=99.0)

    add_cart_response = client.post(
        "/api/v1/cart/items",
        headers=auth_headers(buyer_token),
        json={"product_id": product_id, "quantity": 2},
    )
    assert add_cart_response.status_code == 201
    assert add_cart_response.get_json()["data"]["items"][0]["quantity"] == 2

    idempotency_key = f"pytest-{uuid4().hex}"
    order_payload = {
        "product_id": product_id,
        "quantity": 2,
        "delivery_type": "meetup",
        "meet_location": "图书馆门口",
        "client_amount": 1,
    }
    order_response = client.post(
        "/api/v1/orders",
        headers=auth_headers(buyer_token, idempotency_key),
        json=order_payload,
    )
    assert order_response.status_code == 201
    order = order_response.get_json()["data"]
    assert order["status"] == "pending_payment"
    assert order["total_amount"] == 198.0
    assert order["items"][0]["product_snapshot"]["title"]
    assert order["allowed_actions"]["can_pay"] is True
    assert order["allowed_actions"]["can_cancel"] is True

    duplicated_response = client.post(
        "/api/v1/orders",
        headers=auth_headers(buyer_token, idempotency_key),
        json=order_payload,
    )
    assert duplicated_response.status_code == 201
    assert duplicated_response.get_json()["data"]["id"] == order["id"]

    product_after_order = app.db.products.find_one({"_id": ObjectId(product_id)})
    assert product_after_order["stock"] == 1

    payment_id = order["payment"]["id"]
    pay_response = client.post(
        "/api/v1/payments/mock-confirm",
        headers=auth_headers(buyer_token, f"pay-{uuid4().hex}"),
        json={"payment_id": payment_id, "mock_result": "success"},
    )
    assert pay_response.status_code == 200
    assert pay_response.get_json()["data"]["order_status"] == "paid"

    duplicate_pay_response = client.post(
        "/api/v1/payments/mock-confirm",
        headers=auth_headers(buyer_token, f"pay-{uuid4().hex}"),
        json={"payment_id": payment_id, "mock_result": "success"},
    )
    assert duplicate_pay_response.status_code == 200
    assert duplicate_pay_response.get_json()["data"]["order_status"] == "paid"

    detail_response = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(buyer_token))
    detail = detail_response.get_json()["data"]
    assert detail["status"] == "paid"
    assert detail["allowed_actions"]["can_confirm_receipt"] is True

    confirm_response = client.post(
        f"/api/v1/deliveries/{order['id']}/confirm",
        headers=auth_headers(buyer_token),
    )
    assert confirm_response.status_code == 200
    assert confirm_response.get_json()["data"]["order"]["status"] == "completed"


def test_cancel_order_releases_stock_and_self_purchase_is_blocked():
    init_db()
    app = create_app()
    client = app.test_client()

    seller_token = login(client, "18800000001", "seller123456")
    buyer_token = login(client, "18800000002", "buyer123456")
    admin_token = login(client, "18800000000", "admin123456")
    product_id, _ = create_on_sale_product(client, seller_token, admin_token, stock=2, price=50.0)

    self_order = client.post(
        "/api/v1/orders",
        headers=auth_headers(seller_token),
        json={"product_id": product_id, "quantity": 1},
    )
    assert self_order.status_code == 403

    order_response = client.post(
        "/api/v1/orders",
        headers=auth_headers(buyer_token, f"cancel-{uuid4().hex}"),
        json={"product_id": product_id, "quantity": 1},
    )
    order = order_response.get_json()["data"]
    assert app.db.products.find_one({"_id": ObjectId(product_id)})["stock"] == 1

    cancel_response = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        headers=auth_headers(buyer_token),
    )
    assert cancel_response.status_code == 200
    assert cancel_response.get_json()["data"]["status"] == "closed"
    assert app.db.products.find_one({"_id": ObjectId(product_id)})["stock"] == 2

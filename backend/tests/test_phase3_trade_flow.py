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
    response = client.post("/api/v1/auth/password-login", json={"phone": phone, "password": password})
    assert response.status_code == 200
    return response.get_json()["data"]["token"]


def create_on_sale_product(client, seller_token, admin_token, stock=3, price=99.0):
    category_id = client.get("/api/v1/categories").get_json()["data"]["items"][0]["id"]
    title = f"pytest-trade-{uuid4().hex}"
    response = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": title,
            "description": "交易闭环测试商品。",
            "price": price,
            "category_id": category_id,
            "condition": "good",
            "stock": stock,
            "images": [],
            "campus": "主校区",
            "delivery_options": ["offline_meetup"],
            "submit_action": "review",
        },
    )
    product_id = response.get_json()["data"]["id"]
    client.post(
        f"/api/v1/admin/products/{product_id}/audit",
        headers=auth_headers(admin_token),
        json={"result": "approved", "reason": "交易测试通过"},
    )
    return product_id


def setup_flow():
    init_db()
    app = create_app()
    client = app.test_client()
    app.db.products.delete_many({"title": {"$regex": "^pytest-trade-"}})
    seller_token = login(client, "18800000001", "seller123456")
    buyer_token = login(client, "18800000002", "buyer123456")
    admin_token = login(client, "18800000000", "admin123456")
    return app, client, seller_token, buyer_token, admin_token


def create_order(client, buyer_token, product_id, quantity=1):
    response = client.post(
        "/api/v1/orders",
        headers=auth_headers(buyer_token, f"order-{uuid4().hex}"),
        json={
            "product_id": product_id,
            "quantity": quantity,
            "delivery_type": "offline_meetup",
            "meet_location": "图书馆门口",
        },
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def pay_order(client, buyer_token, order_id):
    prepay = client.post(
        "/api/v1/payments/prepay",
        headers=auth_headers(buyer_token, f"prepay-{uuid4().hex}"),
        json={"order_id": order_id},
    )
    assert prepay.status_code == 201
    payment = prepay.get_json()["data"]["payment"]
    response = client.post(
        "/api/v1/payments/mock-confirm",
        headers=auth_headers(buyer_token, f"pay-{uuid4().hex}"),
        json={"payment_id": payment["id"], "mock_result": "success"},
    )
    assert response.status_code == 200
    return response.get_json()["data"]


def test_order_payment_delivery_receive_and_review_flow():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    product_id = create_on_sale_product(client, seller_token, admin_token, stock=2)

    order = create_order(client, buyer_token, product_id)
    assert order["status"] == "pending_payment"
    assert order["allowed_actions"]["can_pay"] is True
    product_after_order = app.db.products.find_one({"_id": ObjectId(product_id)})
    assert product_after_order["status"] == "locked"

    pay_data = pay_order(client, buyer_token, order["id"])
    assert pay_data["order_status"] == "pending_delivery"
    assert pay_data["payment"]["status"] == "paid"
    assert pay_data["escrow"]["status"] == "holding"

    duplicate_pay = client.post(
        "/api/v1/payments/mock-confirm",
        headers=auth_headers(buyer_token, f"pay-{uuid4().hex}"),
        json={"order_id": order["id"], "mock_result": "success"},
    )
    assert duplicate_pay.status_code == 200
    assert app.db.escrow_records.count_documents({"order_id": ObjectId(order["id"])}) == 1

    not_seller = client.post(
        f"/api/v1/deliveries/{order['id']}/seller-deliver",
        headers=auth_headers(buyer_token),
        json={"delivery_type": "offline_meetup", "meet_location": "图书馆门口"},
    )
    assert not_seller.status_code == 403

    deliver = client.post(
        f"/api/v1/deliveries/{order['id']}/seller-deliver",
        headers=auth_headers(seller_token),
        json={"delivery_type": "offline_meetup", "meet_location": "图书馆门口", "proof_images": []},
    )
    assert deliver.status_code == 200
    assert deliver.get_json()["data"]["order"]["status"] == "pending_receive"

    receive = client.post(f"/api/v1/deliveries/{order['id']}/buyer-confirm", headers=auth_headers(buyer_token))
    assert receive.status_code == 200
    assert receive.get_json()["data"]["order"]["status"] == "pending_review"
    assert receive.get_json()["data"]["escrow"]["status"] == "settled"

    review = client.post(
        "/api/v1/reviews",
        headers=auth_headers(buyer_token),
        json={"order_id": order["id"], "rating": 5, "content": "交易顺利"},
    )
    assert review.status_code == 201
    assert app.db.orders.find_one({"_id": ObjectId(order["id"])})["status"] == "completed"
    assert app.db.products.find_one({"_id": ObjectId(product_id)})["status"] == "sold"


def test_buyer_cancel_reopens_product_and_self_purchase_is_blocked():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    product_id = create_on_sale_product(client, seller_token, admin_token, stock=1)

    self_order = client.post("/api/v1/orders", headers=auth_headers(seller_token), json={"product_id": product_id})
    assert self_order.status_code == 403

    order = create_order(client, buyer_token, product_id)
    cancel = client.post(f"/api/v1/orders/{order['id']}/buyer-cancel", headers=auth_headers(buyer_token))
    assert cancel.status_code == 200
    assert cancel.get_json()["data"]["status"] == "closed"
    assert app.db.products.find_one({"_id": ObjectId(product_id)})["status"] == "on_sale"


def test_illegal_state_transition_returns_409():
    app, client, seller_token, buyer_token, admin_token = setup_flow()
    product_id = create_on_sale_product(client, seller_token, admin_token, stock=1)
    order = create_order(client, buyer_token, product_id)
    bad_deliver = client.post(
        f"/api/v1/deliveries/{order['id']}/seller-deliver",
        headers=auth_headers(seller_token),
        json={"delivery_type": "offline_meetup", "meet_location": "图书馆门口"},
    )
    assert bad_deliver.status_code == 409

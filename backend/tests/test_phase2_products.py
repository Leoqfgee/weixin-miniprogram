from uuid import uuid4

from bson import ObjectId

from app import create_app
from scripts.init_db import main as init_db


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, phone, password):
    response = client.post(
        "/api/v1/auth/mock-login",
        json={"phone": phone, "password": password},
    )
    assert response.status_code == 200
    return response.get_json()["data"]["token"]


def test_product_review_flow():
    init_db()
    app = create_app()
    client = app.test_client()
    app.db.products.delete_many({"title": {"$regex": "^pytest-"}})
    app.db.operation_logs.delete_many({"detail.test_case": "phase2"})

    seller_token = login(client, "18800000001", "seller123456")
    admin_token = login(client, "18800000000", "admin123456")
    buyer_token = login(client, "18800000002", "buyer123456")

    category_response = client.get("/api/v1/categories")
    category_id = category_response.get_json()["data"]["items"][0]["id"]

    title = f"pytest-{uuid4().hex}"
    create_response = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": title,
            "description": "九成新课程教材，适合本地演示测试。",
            "price": 18.5,
            "category_id": category_id,
            "condition": "good",
            "stock": 2,
            "images": [],
            "campus": "主校区",
            "delivery_options": ["meetup"],
            "submit_action": "draft",
        },
    )
    assert create_response.status_code == 201
    product = create_response.get_json()["data"]
    assert product["status"] == "draft"
    assert product["allowed_actions"]["can_submit_review"] is True

    public_detail = client.get(f"/api/v1/products/{product['id']}")
    assert public_detail.status_code == 404

    submit_response = client.post(
        f"/api/v1/products/{product['id']}/submit-review",
        headers=auth_headers(seller_token),
    )
    assert submit_response.status_code == 200
    assert submit_response.get_json()["data"]["status"] == "pending_review"

    admin_list_response = client.get(
        "/api/v1/admin/products?status=pending_review",
        headers=auth_headers(admin_token),
    )
    assert admin_list_response.status_code == 200
    pending_items = admin_list_response.get_json()["data"]["items"]
    assert any(item["id"] == product["id"] for item in pending_items)

    audit_response = client.post(
        f"/api/v1/admin/products/{product['id']}/audit",
        headers=auth_headers(admin_token),
        json={"result": "approved", "reason": "测试通过", "test_case": "phase2"},
    )
    assert audit_response.status_code == 200
    assert audit_response.get_json()["data"]["status"] == "on_sale"

    list_response = client.get(f"/api/v1/products?keyword={title}")
    items = list_response.get_json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == title

    buyer_detail = client.get(f"/api/v1/products/{product['id']}", headers=auth_headers(buyer_token))
    actions = buyer_detail.get_json()["data"]["allowed_actions"]
    assert actions["can_buy"] is True
    assert "can_add_cart" not in actions

    off_shelf_response = client.post(
        f"/api/v1/products/{product['id']}/off-shelf",
        headers=auth_headers(admin_token),
        json={"reason": "阶段测试下架", "test_case": "phase2"},
    )
    assert off_shelf_response.status_code == 200
    assert off_shelf_response.get_json()["data"]["status"] == "off_shelf"

    hidden_response = client.get(f"/api/v1/products?keyword={title}")
    assert hidden_response.get_json()["data"]["items"] == []

    log_count = app.db.operation_logs.count_documents(
        {
            "target_type": "product",
            "target_id": ObjectId(product["id"]),
            "action": {"$in": ["product_audit", "product_force_off_shelf"]},
        }
    )
    assert log_count == 2


def test_non_owner_cannot_edit_product():
    init_db()
    app = create_app()
    client = app.test_client()

    seller_token = login(client, "18800000001", "seller123456")
    buyer_token = login(client, "18800000002", "buyer123456")
    category_id = client.get("/api/v1/categories").get_json()["data"]["items"][0]["id"]

    title = f"pytest-{uuid4().hex}"
    response = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": title,
            "description": "非本人编辑测试。",
            "price": 12,
            "category_id": category_id,
            "condition": "fair",
            "stock": 1,
            "images": [],
            "campus": "主校区",
            "delivery_options": ["meetup"],
        },
    )
    product_id = response.get_json()["data"]["id"]

    edit_response = client.put(
        f"/api/v1/products/{product_id}",
        headers=auth_headers(buyer_token),
        json={"title": "不应该成功"},
    )
    assert edit_response.status_code == 403

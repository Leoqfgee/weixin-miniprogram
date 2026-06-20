from uuid import uuid4

from bson import ObjectId

from app import create_app
from scripts.init_db import main as init_db


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, phone, password):
    response = client.post(
        "/api/v1/auth/password-login",
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
    categories = category_response.get_json()["data"]["items"]
    category_id = categories[0]["id"]
    other_category_id = categories[1]["id"]

    title = f"pytest-{uuid4().hex}"
    image_url = f"https://example.com/{title}.png"
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
            "images": [image_url],
            "campus": "东校区",
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

    list_response = client.get(f"/api/v1/products?keyword={title}&mode=latest")
    items = list_response.get_json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == title
    assert items[0]["cover_image"] == image_url
    assert items[0]["images"] == [image_url]

    hot_response = client.get(f"/api/v1/products?keyword={title}&mode=hot")
    assert hot_response.status_code == 200
    assert hot_response.get_json()["data"]["items"][0]["id"] == product["id"]

    buyer_detail = client.get(f"/api/v1/products/{product['id']}", headers=auth_headers(buyer_token))
    actions = buyer_detail.get_json()["data"]["allowed_actions"]
    assert actions["can_buy"] is True
    assert "can_add_cart" not in actions
    assert app.db.product_views.count_documents({"product_id": ObjectId(product["id"])}) == 1

    other_title = f"pytest-{uuid4().hex}"
    other_create = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": other_title,
            "description": "不同分类也必须留在推荐列表中。",
            "price": 26,
            "category_id": other_category_id,
            "condition": "good",
            "stock": 1,
            "images": [],
            "campus": "东校区",
            "delivery_options": ["meetup"],
            "submit_action": "review",
        },
    )
    assert other_create.status_code == 201
    other_product = other_create.get_json()["data"]
    other_audit = client.post(
        f"/api/v1/admin/products/{other_product['id']}/audit",
        headers=auth_headers(admin_token),
        json={"result": "approved", "reason": "推荐全量排序测试", "test_case": "phase2"},
    )
    assert other_audit.status_code == 200

    recommend_response = client.get("/api/v1/products?mode=recommend", headers=auth_headers(buyer_token))
    assert recommend_response.status_code == 200
    recommend_items = recommend_response.get_json()["data"]["items"]
    recommend_ids = {item["id"] for item in recommend_items}
    assert product["id"] in recommend_ids
    assert other_product["id"] in recommend_ids
    assert all("recommendation_score" in item for item in recommend_items)

    favorite_response = client.post(
        "/api/v1/favorites",
        headers=auth_headers(buyer_token),
        json={"product_id": product["id"]},
    )
    assert favorite_response.status_code == 201
    app.db.products.update_one({"_id": ObjectId(product["id"])}, {"$set": {"price": 16.0}})
    dropped = client.get("/api/v1/favorites?type=price_drop", headers=auth_headers(buyer_token))
    assert dropped.status_code == 200
    dropped_data = dropped.get_json()["data"]
    assert dropped_data["items"][0]["price_dropped"] is True

    off_shelf_response = client.post(
        f"/api/v1/products/{product['id']}/off-shelf",
        headers=auth_headers(admin_token),
        json={"reason": "阶段测试下架", "test_case": "phase2"},
    )
    assert off_shelf_response.status_code == 200
    assert off_shelf_response.get_json()["data"]["status"] == "off_shelf"

    hidden_response = client.get(f"/api/v1/products?keyword={title}")
    assert hidden_response.get_json()["data"]["items"] == []

    invalid = client.get("/api/v1/favorites?type=invalid", headers=auth_headers(buyer_token))
    assert invalid.status_code == 200
    assert invalid.get_json()["data"]["items"][0]["favorite_invalid"] is True
    cleanup = client.post("/api/v1/favorites/cleanup-invalid", headers=auth_headers(buyer_token))
    assert cleanup.status_code == 200
    assert cleanup.get_json()["data"]["removed"] == 1

    log_count = app.db.operation_logs.count_documents(
        {
            "target_type": "product",
            "target_id": ObjectId(product["id"]),
            "action": {"$in": ["product_audit", "product_force_off_shelf"]},
        }
    )
    assert log_count == 2


def test_debug_storage_masks_secrets():
    init_db()
    app = create_app()
    app.config.update(
        DEV_TEST_LOGIN_ENABLED=True,
        STORAGE_BACKEND="cos",
        COS_BUCKET="campus-secondhand-1440900946",
        COS_REGION="ap-shanghai",
        COS_PUBLIC_BASE_URL="https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com",
        COS_SECRET_ID="secret-id-for-test",
        COS_SECRET_KEY="secret-key-for-test",
    )
    client = app.test_client()

    response = client.get("/api/v1/debug/storage")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["storage_backend"] == "cos"
    assert data["cos_region"] == "ap-shanghai"
    assert data["has_cos_secret_id"] is True
    assert data["has_cos_secret_key"] is True
    assert "secret-id-for-test" not in str(data)
    assert "secret-key-for-test" not in str(data)


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
            "campus": "西校区",
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


def test_product_campus_must_be_east_or_west():
    init_db()
    app = create_app()
    client = app.test_client()

    seller_token = login(client, "18800000001", "seller123456")
    category_id = client.get("/api/v1/categories").get_json()["data"]["items"][0]["id"]

    response = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": f"pytest-{uuid4().hex}",
            "description": "非法校区测试。",
            "price": 12,
            "category_id": category_id,
            "condition": "fair",
            "stock": 1,
            "images": [],
            "campus": "主校区",
            "delivery_options": ["meetup"],
            "submit_action": "review",
        },
    )
    assert response.status_code == 422
    assert response.get_json()["errors"][0]["field"] == "campus"

    filter_response = client.get("/api/v1/products?campus=主校区")
    assert filter_response.status_code == 422
    assert filter_response.get_json()["errors"][0]["field"] == "campus"

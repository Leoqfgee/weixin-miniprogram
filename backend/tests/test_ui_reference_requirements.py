from uuid import uuid4

from test_phase3_trade_flow import auth_headers, setup_flow


def _create_product(client, seller_token, admin_token, title, description, category=None):
    payload = {
        "title": title,
        "description": description,
        "price": 18,
        "condition": "good",
        "stock": 1,
        "images": [],
        "campus": "东校区",
        "delivery_options": ["meetup"],
        "submit_action": "review",
    }
    if category:
        payload["category"] = category
        payload["category_source"] = "manual"
    response = client.post("/api/v1/products", headers=auth_headers(seller_token), json=payload)
    assert response.status_code == 201
    product = response.get_json()["data"]
    audit = client.post(
        f"/api/v1/admin/products/{product['id']}/audit",
        headers=auth_headers(admin_token),
        json={"result": "approved", "reason": "ui reference requirement"},
    )
    assert audit.status_code == 200
    return audit.get_json()["data"]


def test_auto_category_and_manual_category_priority():
    app, client, seller_token, buyer_token, admin_token = setup_flow()

    samples = [
        ("高等数学 同济七版 上册", "课程教材，适合期末复习", "book"),
        ("罗技机械键盘 茶轴", "键盘手感清脆，宿舍自用", "digital"),
        ("白色双肩包", "容量大，通勤上课都可用", "clothing"),
        ("宿舍台灯", "三档亮度，夜间看书", "home"),
        (f"pytest-unknown-{uuid4().hex[:8]}", "描述无法判断分类", "other"),
    ]
    for title, description, expected in samples:
        product = _create_product(client, seller_token, admin_token, title, description)
        assert product["category"] == expected
        assert product["category_source"] == "auto"
        filtered = client.get(f"/api/v1/products?category={expected}&keyword={title}")
        assert any(item["id"] == product["id"] for item in filtered.get_json()["data"]["items"])

    manual = _create_product(client, seller_token, admin_token, "罗技机械键盘 手动归类测试", "标题会命中数码", "book")
    assert manual["category"] == "book"
    assert manual["category_source"] == "manual"


def test_recommendations_are_real_products_and_exclude_current_product():
    app, client, seller_token, buyer_token, admin_token = setup_flow()

    current = _create_product(client, seller_token, admin_token, "pytest 推荐教材 A", "高数教材", "book")
    related = _create_product(client, seller_token, admin_token, "pytest 推荐教材 B", "英语教材", "book")
    _create_product(client, seller_token, admin_token, "pytest 推荐耳机", "蓝牙耳机", "digital")

    response = client.get(f"/api/v1/products/{current['id']}/recommendations?limit=6", headers=auth_headers(buyer_token))
    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    assert all(item["id"] != current["id"] for item in items)
    assert any(item["id"] == related["id"] for item in items)
    assert all(item["status"] == "on_sale" for item in items)

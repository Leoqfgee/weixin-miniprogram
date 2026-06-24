import json

from bson import ObjectId

from app import create_app
from app.domain.campus import ALLOWED_CAMPUSES
from app.services.content_moderation import ContentModerationService
from scripts.init_db import main as init_db
from test_phase3_trade_flow import auth_headers, login


VALID_CAMPUS = next(iter(ALLOWED_CAMPUSES))


class FakeAiResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def setup_app():
    init_db()
    app = create_app()
    client = app.test_client()
    seller_token = login(client, "18800000001", "seller123456")
    buyer_token = login(client, "18800000002", "buyer123456")
    admin_token = login(client, "18800000000", "admin123456")
    app.db.student_verifications.delete_many({})
    app.db.reports.delete_many({"target_type": "user"})
    app.db.content_block_records.delete_many({})
    return app, client, seller_token, buyer_token, admin_token


def test_student_verification_submit_and_admin_review_updates_profile_and_message():
    app, client, seller_token, _, admin_token = setup_app()
    response = client.post(
        "/api/v1/student-verifications",
        headers=auth_headers(seller_token),
        json={
            "school": "测试大学",
            "real_name": "张三",
            "student_no": "S1001",
            "card_image_url": "https://example.com/card.jpg",
        },
    )
    assert response.status_code == 200
    application = response.get_json()["data"]
    assert application["status"] == "pending"

    duplicate = client.post(
        "/api/v1/student-verifications",
        headers=auth_headers(seller_token),
        json={"school": "测试大学", "real_name": "张三", "card_image_url": "https://example.com/card.jpg"},
    )
    assert duplicate.status_code == 409

    reviewed = client.post(
        f"/api/v1/admin/student-verifications/{application['id']}/review",
        headers=auth_headers(admin_token),
        json={"result": "verified"},
    )
    assert reviewed.status_code == 200
    seller = app.db.users.find_one({"phone": "18800000001"})
    profile = app.db.user_profiles.find_one({"user_id": seller["_id"]})
    assert profile["student_verify_status"] == "verified"
    assert profile["student_verified"] is True
    assert app.db.messages.count_documents({"receiver_id": seller["_id"], "system_action": "student_verification_verified"}) == 1


def test_search_returns_user_results_with_credit_and_on_sale_count():
    _, client, seller_token, _, admin_token = setup_app()
    category_id = client.get("/api/v1/categories").get_json()["data"]["items"][0]["id"]
    product = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": "pytest-search-user-product",
            "description": "普通商品描述",
            "price": 10,
            "category_id": category_id,
            "condition": "good",
            "stock": 1,
            "images": [],
            "campus": VALID_CAMPUS,
            "delivery_options": ["meetup"],
            "submit_action": "publish",
        },
    )
    assert product.status_code == 201
    search = client.get("/api/v1/search?q=测试卖家&type=all", headers=auth_headers(admin_token))
    assert search.status_code == 200
    users = search.get_json()["data"]["users"]["items"]
    assert users
    assert {"user_id", "nickname", "avatar_url", "campus", "credit_score", "student_verify_status", "on_sale_count"} <= set(users[0].keys())


def test_ai_search_recalls_real_products_from_current_candidates(monkeypatch):
    app, client, seller_token, _, _ = setup_app()
    category_id = client.get("/api/v1/categories").get_json()["data"]["items"][0]["id"]
    product = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": "奶龙",
            "description": "黄色卡通生物玩偶，适合放在宿舍桌面。",
            "price": 18,
            "category_id": category_id,
            "condition": "good",
            "stock": 1,
            "images": [],
            "campus": VALID_CAMPUS,
            "delivery_options": ["meetup"],
            "submit_action": "publish",
        },
    )
    assert product.status_code == 201
    product_id = product.get_json()["data"]["id"]
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        content = json.dumps({"matched_product_ids": [product_id, "000000000000000000000000"], "reason": "黄色卡通生物相关"}, ensure_ascii=False)
        return FakeAiResponse({"choices": [{"message": {"content": content}}]})

    monkeypatch.setenv("AI_SEARCH_ENABLED", "true")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setattr("app.services.users.urlopen", fake_urlopen)

    search = client.get("/api/v1/search?q=神秘黄色生物&type=all&ai=1", headers=auth_headers(seller_token))
    assert search.status_code == 200
    data = search.get_json()["data"]
    ids = [item["id"] for item in data["products"]["items"]]
    assert product_id in ids
    assert data["ai_search"]["matched_product_ids"] == [product_id]
    assert data["products"]["items"][ids.index(product_id)]["search_match_type"] == "ai"
    prompt = captured["body"]["messages"][1]["content"]
    assert "奶龙" in prompt
    assert "神秘黄色生物" in prompt


def test_ai_search_failure_falls_back_to_plain_keyword_search(monkeypatch):
    _, client, seller_token, _, _ = setup_app()
    category_id = client.get("/api/v1/categories").get_json()["data"]["items"][0]["id"]
    product = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": "荔枝",
            "description": "新鲜水果，校内自提。",
            "price": 12,
            "category_id": category_id,
            "condition": "new",
            "stock": 1,
            "images": [],
            "campus": VALID_CAMPUS,
            "delivery_options": ["meetup"],
            "submit_action": "publish",
        },
    )
    assert product.status_code == 201
    product_id = product.get_json()["data"]["id"]

    monkeypatch.setenv("AI_SEARCH_ENABLED", "true")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setattr("app.services.users.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("timeout")))

    search = client.get("/api/v1/search?q=荔枝&type=all&ai=1", headers=auth_headers(seller_token))
    assert search.status_code == 200
    data = search.get_json()["data"]
    assert product_id in [item["id"] for item in data["products"]["items"]]
    assert data["ai_search"]["used"] is False


def test_user_report_lifecycle_can_deduct_target_user_credit_and_notify_both_sides():
    app, client, seller_token, buyer_token, admin_token = setup_app()
    seller = app.db.users.find_one({"phone": "18800000001"})
    report_response = client.post(
        "/api/v1/reports",
        headers=auth_headers(buyer_token),
        json={"target_type": "user", "target_user_id": str(seller["_id"]), "reason_type": "fraud", "description": "疑似欺诈", "evidence_images": []},
    )
    assert report_response.status_code == 201
    report = report_response.get_json()["data"]

    self_report = client.post(
        "/api/v1/reports",
        headers=auth_headers(seller_token),
        json={"target_type": "user", "target_user_id": str(seller["_id"]), "reason_type": "other"},
    )
    assert self_report.status_code == 403

    handled = client.post(
        f"/api/v1/admin/reports/{report['id']}/handle",
        headers=auth_headers(admin_token),
        json={"result": "approved", "credit_deduct": 12, "admin_note": "举报成立"},
    )
    assert handled.status_code == 200
    assert app.db.user_profiles.find_one({"user_id": seller["_id"]})["credit_score"] == 88
    assert app.db.credit_records.count_documents({"user_id": seller["_id"], "related_report_id": ObjectId(report["id"])}) == 1
    assert app.db.messages.count_documents({"receiver_id": seller["_id"], "system_action": "user_report_approved"}) == 1


def test_content_moderation_blocks_product_chat_review_report_and_nickname():
    app, client, seller_token, buyer_token, admin_token = setup_app()
    category_id = client.get("/api/v1/categories").get_json()["data"]["items"][0]["id"]
    blocked_product = client.post(
        "/api/v1/products",
        headers=auth_headers(seller_token),
        json={
            "title": "含有违 禁 词的标题",
            "description": "普通描述",
            "price": 10,
            "category_id": category_id,
            "condition": "good",
            "stock": 1,
            "images": [],
            "campus": VALID_CAMPUS,
            "delivery_options": ["meetup"],
            "submit_action": "publish",
        },
    )
    assert blocked_product.status_code == 422

    seller = app.db.users.find_one({"phone": "18800000001"})
    chat = client.post(
        "/api/v1/messages",
        headers=auth_headers(buyer_token),
        json={"receiver_id": str(seller["_id"]), "message_type": "text", "content": "这里有违-禁-词"},
    )
    assert chat.status_code == 422

    nickname = client.put("/api/v1/users/me", headers=auth_headers(buyer_token), json={"nickname": "违 禁 词用户"})
    assert nickname.status_code == 422

    report = client.post(
        "/api/v1/reports",
        headers=auth_headers(buyer_token),
        json={"target_type": "user", "target_user_id": str(seller["_id"]), "reason_type": "fraud", "description": "违禁词说明"},
    )
    assert report.status_code == 422
    assert app.db.content_block_records.count_documents({}) >= 4

    words = client.get("/api/v1/admin/banned-words", headers=auth_headers(admin_token))
    assert words.status_code == 200
    assert any(item["word"] == "违禁词" for item in words.get_json()["data"]["items"])


def test_content_moderation_blocks_common_insult_with_obfuscation():
    app, _, _, _, _ = setup_app()
    service = ContentModerationService(app.db)
    result = service.check_fields({"chat": "你真是傻 逼"})
    assert result["passed"] is False
    assert result["matches"][0]["hit_words"] == ["傻逼"]
    assert result["matches"][0]["risk_level"] == "high"


def test_ai_moderation_blocks_when_dashscope_returns_risk(monkeypatch):
    app, _, _, _, _ = setup_app()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return (
                b'{"choices":[{"message":{"content":"{\\"passed\\":false,\\"risk_level\\":\\"high\\",'
                b'\\"reason\\":\\"contains harassment\\",\\"hit_categories\\":[\\"harassment\\"]}"}}]}'
            )

    monkeypatch.setenv("CONTENT_AI_MODERATION_ENABLED", "true")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setattr("app.services.content_moderation.urlopen", lambda *args, **kwargs: FakeResponse())
    service = ContentModerationService(app.db)
    result = service.check_fields({"chat": "这句话没有命中本地词库但 AI 判定有风险"})
    assert result["passed"] is False
    assert result["matches"][0]["hit_categories"] == ["harassment"]


def test_admin_credit_adjust_writes_record_and_message():
    app, client, _, buyer_token, admin_token = setup_app()
    buyer = app.db.users.find_one({"phone": "18800000002"})
    response = client.post(
        f"/api/v1/admin/users/{buyer['_id']}/credit/adjust",
        headers=auth_headers(admin_token),
        json={"change_value": -7, "reason_text": "管理员测试扣分"},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["credit"]["credit_score"] == 93
    assert app.db.credit_records.count_documents({"user_id": buyer["_id"], "reason_text": "管理员测试扣分"}) == 1
    assert app.db.messages.count_documents({"receiver_id": buyer["_id"], "system_action": "credit_score_changed"}) == 1

from io import BytesIO

from app import create_app
from scripts.init_db import main as init_db


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_wechat_login_register_bind_phone_and_change_password():
    init_db()
    app = create_app()
    client = app.test_client()

    openid = "local_wechat_pytest-code"
    app.db.users.delete_many({"openid": openid})
    app.db.users.delete_many({"phone": "19900000001"})
    response = client.post(
        "/api/v1/auth/wechat-login",
        json={"code": "pytest-code", "nickname": "微信测试用户", "avatar_url": "https://example.com/a.png"},
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["need_bind_phone"] is True
    assert "buyer" in data["user"]["roles"]
    assert "user" not in data["user"]["roles"]
    assert data["user"]["profile"]["nickname"] == ""
    assert data["user"]["profile_completed"] is False
    first_user_id = data["user"]["id"]

    second_response = client.post(
        "/api/v1/auth/wechat-login",
        json={"code": "pytest-code", "nickname": "另一个昵称"},
    )
    assert second_response.status_code == 200
    second_data = second_response.get_json()["data"]
    assert second_data["user"]["id"] == first_user_id
    assert second_data["user"]["profile"]["nickname"] == ""

    bind_response = client.post(
        "/api/v1/auth/bind-phone",
        headers=auth_headers(data["token"]),
        json={"phone": "19900000001", "password": "test123456"},
    )
    assert bind_response.status_code == 200
    assert bind_response.get_json()["data"]["phone"] == "19900000001"

    change_response = client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers(data["token"]),
        json={"old_password": "test123456", "new_password": "new123456"},
    )
    assert change_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/password-login",
        json={"phone": "19900000001", "password": "new123456"},
    )
    assert login_response.status_code == 200


def test_upload_image_returns_static_url():
    init_db()
    app = create_app()
    client = app.test_client()
    login = client.post(
        "/api/v1/auth/password-login",
        json={"phone": "18800000001", "password": "seller123456"},
    ).get_json()["data"]

    response = client.post(
        "/api/v1/files/upload",
        headers=auth_headers(login["token"]),
        data={"usage": "product", "file": (BytesIO(b"fake-image-content"), "demo.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    file_doc = response.get_json()["data"]
    assert file_doc["url"].endswith(".png")
    assert "/uploads/product/" in file_doc["url"]


def test_upload_delivery_image_uses_delivery_folder():
    init_db()
    app = create_app()
    client = app.test_client()
    login = client.post(
        "/api/v1/auth/password-login",
        json={"phone": "18800000001", "password": "seller123456"},
    ).get_json()["data"]

    response = client.post(
        "/api/v1/files/upload",
        headers=auth_headers(login["token"]),
        data={"usage": "delivery", "file": (BytesIO(b"fake-delivery-image"), "proof.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    file_doc = response.get_json()["data"]
    assert "/uploads/delivery/" in file_doc["url"]


def test_wechat_login_default_role_is_buyer():
    init_db()
    app = create_app()
    client = app.test_client()

    openid = "local_wechat_pytest-role-code"
    app.db.users.delete_many({"openid": openid})
    response = client.post(
        "/api/v1/auth/wechat-login",
        json={"code": "pytest-role-code", "nickname": "默认买家"},
    )
    assert response.status_code == 200
    roles = response.get_json()["data"]["user"]["roles"]
    assert "buyer" in roles
    assert "user" not in roles


def test_update_me_completes_platform_identity_and_masks_openid():
    init_db()
    app = create_app()
    client = app.test_client()

    app.db.users.delete_many({"openid": "local_wechat_profile-code"})
    login = client.post("/api/v1/auth/wechat-login", json={"code": "profile-code"}).get_json()["data"]
    update = client.put(
        "/api/v1/users/me",
        headers=auth_headers(login["token"]),
        json={
            "nickname": "平台昵称",
            "avatar_url": "https://example.com/avatar.png",
            "identity_type": "custom",
            "contact_phone": "19900000009",
        },
    )
    assert update.status_code == 200
    user = update.get_json()["data"]
    assert user["profile_completed"] is True
    assert user["identity_type"] == "custom"
    assert user["profile"]["nickname"] == "平台昵称"
    assert user["profile"]["avatar_url"] == "https://example.com/avatar.png"

    me = client.get("/api/v1/users/me", headers=auth_headers(login["token"]))
    assert me.status_code == 200
    body = me.get_json()["data"]
    assert body["openid_mask"].startswith("local_")
    assert "session_key" not in body


def test_dev_test_login_requires_switch_and_can_login_seed_user(monkeypatch):
    init_db()
    app = create_app()
    client = app.test_client()

    disabled = client.post("/api/v1/auth/dev-test-login", json={"account": "buyer_a"})
    assert disabled.status_code == 404

    app.config["DEV_TEST_LOGIN_ENABLED"] = True
    enabled = client.post("/api/v1/auth/dev-test-login", json={"account": "buyer_a"})
    assert enabled.status_code == 200
    assert enabled.get_json()["data"]["user"]["phone"] == "18800000002"

import base64
from io import BytesIO

from app import create_app
from app.adapters import storage as storage_adapter
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
    assert file_doc["storage_backend"] == "local"
    assert file_doc["object_key"].startswith("product/")


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
    assert file_doc["storage_backend"] == "local"
    assert file_doc["object_key"].startswith("delivery/")


def test_upload_avatar_base64_returns_static_url():
    init_db()
    app = create_app()
    client = app.test_client()
    login = client.post(
        "/api/v1/auth/password-login",
        json={"phone": "18800000001", "password": "seller123456"},
    ).get_json()["data"]

    response = client.post(
        "/api/v1/files/upload-base64",
        headers=auth_headers(login["token"]),
        json={
            "usage": "avatar",
            "filename": "avatar.jpg",
            "mime_type": "image/jpeg",
            "content_base64": base64.b64encode(b"fake-avatar-content").decode("ascii"),
        },
    )

    assert response.status_code == 201
    file_doc = response.get_json()["data"]
    assert file_doc["usage"] == "avatar"
    assert file_doc["url"].endswith(".jpg")
    assert "/uploads/avatar/" in file_doc["url"]
    assert file_doc["storage_backend"] == "local"
    assert file_doc["object_key"].startswith("avatar/")


def test_upload_avatar_base64_rejects_invalid_content():
    init_db()
    app = create_app()
    client = app.test_client()
    login = client.post(
        "/api/v1/auth/password-login",
        json={"phone": "18800000001", "password": "seller123456"},
    ).get_json()["data"]

    response = client.post(
        "/api/v1/files/upload-base64",
        headers=auth_headers(login["token"]),
        json={
            "usage": "avatar",
            "filename": "avatar.jpg",
            "mime_type": "image/jpeg",
            "content_base64": "not-base64!",
        },
    )

    assert response.status_code == 422


def test_cos_storage_returns_public_url(monkeypatch):
    app = create_app()
    app.config.update(
        STORAGE_BACKEND="cos",
        COS_BUCKET="campus-secondhand-1440900946",
        COS_REGION="ap-shanghai",
        COS_SECRET_ID="fake-id",
        COS_SECRET_KEY="fake-key",
        COS_PUBLIC_BASE_URL="https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com",
    )
    uploaded = {}

    class FakeCosConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeCosClient:
        def __init__(self, config):
            self.config = config

        def put_object(self, **kwargs):
            uploaded.update(kwargs)

    monkeypatch.setattr(storage_adapter, "CosConfig", FakeCosConfig)
    monkeypatch.setattr(storage_adapter, "CosS3Client", FakeCosClient)

    with app.test_request_context():
        result = storage_adapter.StorageService().save(b"avatar", "me.png", "image/png", "avatar")

    assert result["storage_backend"] == "cos"
    assert result["object_key"].startswith("avatar/")
    assert result["object_key"].endswith(".png")
    assert result["url"] == f"{app.config['COS_PUBLIC_BASE_URL']}/{result['object_key']}"
    assert uploaded["Bucket"] == "campus-secondhand-1440900946"
    assert uploaded["Key"] == result["object_key"]
    assert uploaded["ContentType"] == "image/png"


def test_upload_with_cos_backend_persists_cos_url(monkeypatch):
    init_db()
    app = create_app()
    app.config.update(
        STORAGE_BACKEND="cos",
        COS_BUCKET="campus-secondhand-1440900946",
        COS_REGION="ap-shanghai",
        COS_SECRET_ID="fake-id",
        COS_SECRET_KEY="fake-key",
        COS_PUBLIC_BASE_URL="https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com",
    )
    uploaded = {}

    class FakeCosConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeCosClient:
        def __init__(self, config):
            self.config = config

        def put_object(self, **kwargs):
            uploaded.update(kwargs)

    monkeypatch.setattr(storage_adapter, "CosConfig", FakeCosConfig)
    monkeypatch.setattr(storage_adapter, "CosS3Client", FakeCosClient)
    client = app.test_client()
    login = client.post(
        "/api/v1/auth/password-login",
        json={"phone": "18800000001", "password": "seller123456"},
    ).get_json()["data"]

    response = client.post(
        "/api/v1/files/upload",
        headers=auth_headers(login["token"]),
        data={"usage": "avatar", "file": (BytesIO(b"fake-avatar"), "avatar.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    file_doc = response.get_json()["data"]
    assert file_doc["storage_backend"] == "cos"
    assert file_doc["object_key"].startswith("avatar/")
    assert file_doc["url"] == f"{app.config['COS_PUBLIC_BASE_URL']}/{file_doc['object_key']}"
    assert uploaded["Key"] == file_doc["object_key"]

    persisted = app.db.files.find_one({"object_key": file_doc["object_key"]})
    assert persisted["storage_backend"] == "cos"
    assert persisted["url"] == file_doc["url"]


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


def test_update_me_rejects_invalid_contact_phone_and_accepts_valid_phone():
    init_db()
    app = create_app()
    client = app.test_client()

    app.db.users.delete_many({"openid": "local_wechat_phone-code"})
    login = client.post("/api/v1/auth/wechat-login", json={"code": "phone-code"}).get_json()["data"]
    headers = auth_headers(login["token"])
    base_payload = {
        "nickname": "手机号测试",
        "avatar_url": "https://example.com/avatar.png",
        "identity_type": "custom",
    }

    for value in ["1283864646464", "123", "1880000000", "abcdef"]:
        response = client.put(
            "/api/v1/users/me",
            headers=headers,
            json={**base_payload, "contact_phone": value},
        )
        assert response.status_code == 422
        body = response.get_json()
        assert "手机号格式不正确" in str(body)

    valid = client.put(
        "/api/v1/users/me",
        headers=headers,
        json={**base_payload, "contact_phone": "18800000001"},
    )
    assert valid.status_code == 200
    assert valid.get_json()["data"]["profile"]["contact_phone"] == "18800000001"


def test_profile_avatar_is_isolated_between_phone_accounts():
    init_db()
    app = create_app()
    client = app.test_client()

    app.db.users.delete_many({"phone": {"$in": ["19900000011", "19900000012"]}})
    app.db.users.delete_many({"openid": {"$in": ["pytest-profile-a", "pytest-profile-b"]}})

    account_a = client.post(
        "/api/v1/auth/register",
        json={
            "phone": "19900000011",
            "password": "test123456",
            "nickname": "Account A",
            "campus": "东校区",
            "openid": "pytest-profile-a",
        },
    )
    assert account_a.status_code == 201
    token_a = account_a.get_json()["data"]["token"]
    user_a_id = account_a.get_json()["data"]["user"]["id"]

    update_a = client.put(
        "/api/v1/users/me",
        headers=auth_headers(token_a),
        json={
            "nickname": "Account A Updated",
            "avatar_url": "https://example.com/account-a-avatar.png",
            "campus": "西校区",
            "contact_phone": "19900000011",
        },
    )
    assert update_a.status_code == 200
    updated_a = update_a.get_json()["data"]
    assert updated_a["id"] == user_a_id
    assert updated_a["profile"]["avatar_url"] == "https://example.com/account-a-avatar.png"
    assert updated_a["profile"]["campus"] == "西校区"

    account_b = client.post(
        "/api/v1/auth/register",
        json={
            "phone": "19900000012",
            "password": "test123456",
            "nickname": "Account B",
            "campus": "东校区",
            "openid": "pytest-profile-b",
        },
    )
    assert account_b.status_code == 201
    token_b = account_b.get_json()["data"]["token"]
    user_b = account_b.get_json()["data"]["user"]

    me_b = client.get("/api/v1/users/me", headers=auth_headers(token_b))
    assert me_b.status_code == 200
    body_b = me_b.get_json()["data"]
    assert body_b["id"] == user_b["id"]
    assert body_b["id"] != user_a_id
    assert body_b["profile"]["nickname"] == "Account B"
    assert body_b["profile"]["campus"] == "东校区"
    assert body_b["profile"]["avatar_url"] == ""
    assert body_b["stats"] == {"published": 0, "bought": 0, "sold": 0, "favorites": 0}

    login_a = client.post(
        "/api/v1/auth/password-login",
        json={"phone": "19900000011", "password": "test123456"},
    )
    assert login_a.status_code == 200
    relogin_token_a = login_a.get_json()["data"]["token"]
    me_a = client.get("/api/v1/users/me", headers=auth_headers(relogin_token_a))
    assert me_a.status_code == 200
    body_a = me_a.get_json()["data"]
    assert body_a["id"] == user_a_id
    assert body_a["profile"]["nickname"] == "Account A Updated"
    assert body_a["profile"]["avatar_url"] == "https://example.com/account-a-avatar.png"
    assert body_a["profile"]["campus"] == "西校区"


def test_phone_account_cannot_save_wechat_avatar_identity():
    init_db()
    app = create_app()
    client = app.test_client()

    phone = "19900000013"
    app.db.users.delete_many({"phone": phone})
    account = client.post(
        "/api/v1/auth/register",
        json={"phone": phone, "password": "test123456", "nickname": "Phone Account"},
    )
    assert account.status_code == 201
    token = account.get_json()["data"]["token"]

    response = client.put(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={
            "nickname": "Phone Account",
            "avatar_url": "https://example.com/wechat-avatar.png",
            "identity_type": "wechat",
        },
    )
    assert response.status_code == 403
    assert "手机号账号不能使用微信头像身份" in str(response.get_json())


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


def test_cancel_account_disables_login_and_releases_phone():
    init_db()
    app = create_app()
    client = app.test_client()

    phone = "19900000021"
    app.db.users.delete_many({"phone": phone})
    account = client.post(
        "/api/v1/auth/register",
        json={"phone": phone, "password": "test123456", "nickname": "注销测试"},
    )
    assert account.status_code == 201
    token = account.get_json()["data"]["token"]

    cancel = client.delete("/api/v1/users/me", headers=auth_headers(token))
    assert cancel.status_code == 200
    assert cancel.get_json()["data"]["cancelled"] is True

    login = client.post("/api/v1/auth/password-login", json={"phone": phone, "password": "test123456"})
    assert login.status_code == 401
    assert app.db.users.find_one({"phone": phone}) is None

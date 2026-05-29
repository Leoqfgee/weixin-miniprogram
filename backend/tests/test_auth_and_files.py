from io import BytesIO

from app import create_app
from scripts.init_db import main as init_db


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_wechat_login_register_bind_phone_and_change_password():
    init_db()
    app = create_app()
    client = app.test_client()

    openid = "pytest_wechat_openid"
    app.db.users.delete_many({"openid": openid})
    app.db.users.delete_many({"phone": "19900000001"})
    response = client.post(
        "/api/v1/auth/wechat-login",
        json={"code": "pytest-code", "mock_openid": openid, "nickname": "微信测试用户"},
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["need_bind_phone"] is True

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
        "/api/v1/auth/mock-login",
        json={"phone": "19900000001", "password": "new123456"},
    )
    assert login_response.status_code == 200


def test_upload_image_returns_static_url():
    init_db()
    app = create_app()
    client = app.test_client()
    login = client.post(
        "/api/v1/auth/mock-login",
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

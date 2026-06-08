from app import create_app


def test_health_response_shape():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/v1/health")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 0
    assert payload["message"] == "success"
    assert "trace_id" in payload
    assert payload["data"]["service"] == "campus_secondhand_platform"


def test_debug_storage_masks_cos_secret():
    app = create_app()
    app.config.update(
        DEBUG=True,
        STORAGE_BACKEND="cos",
        COS_BUCKET="campus-secondhand-1440900946",
        COS_REGION="ap-shanghai",
        COS_PUBLIC_BASE_URL="https://campus-secondhand-1440900946.cos.ap-shanghai.myqcloud.com",
        COS_SECRET_ID="secret-id",
        COS_SECRET_KEY="secret-key",
    )
    client = app.test_client()

    response = client.get("/api/v1/debug/storage")
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert data["storage_backend"] == "cos"
    assert data["cos_region"] == "ap-shanghai"
    assert data["has_cos_secret_id"] is True
    assert data["has_cos_secret_key"] is True
    assert "secret-id" not in str(data)
    assert "secret-key" not in str(data)

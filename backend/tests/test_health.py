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

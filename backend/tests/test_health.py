from app import create_app


def test_health_returns_ok():
    app = create_app({"GIT_COMMIT": "abc123", "TESTING": True})
    client = app.test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["service"] == "whats-in-my-food-backend"
    assert body["commit"] == "abc123"


def test_unknown_route_is_404():
    app = create_app({"TESTING": True})
    client = app.test_client()

    assert client.get("/api/does-not-exist").status_code == 404

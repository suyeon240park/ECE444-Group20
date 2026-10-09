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


def test_health_reports_render_commit_unless_git_commit_is_set(monkeypatch):
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "f00dfeed")
    assert create_app({"TESTING": True}).test_client().get("/api/health").get_json()["commit"] == (
        "f00dfeed"
    )

    monkeypatch.setenv("GIT_COMMIT", "abc123")
    assert create_app({"TESTING": True}).test_client().get("/api/health").get_json()["commit"] == (
        "abc123"
    )

    monkeypatch.delenv("GIT_COMMIT")
    monkeypatch.delenv("RENDER_GIT_COMMIT")
    assert create_app({"TESTING": True}).test_client().get("/api/health").get_json()["commit"] == (
        "dev"
    )


def test_unknown_route_is_404():
    app = create_app({"TESTING": True})
    client = app.test_client()

    assert client.get("/api/does-not-exist").status_code == 404


def test_cors_allows_each_origin_in_a_comma_separated_list():
    app = create_app({"TESTING": True, "CORS_ORIGINS": "https://a.example, https://b.example"})
    client = app.test_client()

    for origin in ("https://a.example", "https://b.example"):
        response = client.get("/api/health", headers={"Origin": origin})
        assert response.headers.get("Access-Control-Allow-Origin") == origin


def test_cors_rejects_origin_not_in_list():
    app = create_app({"TESTING": True, "CORS_ORIGINS": "https://a.example"})
    client = app.test_client()

    response = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in response.headers


def test_cors_wildcard_allows_any_origin():
    app = create_app({"TESTING": True, "CORS_ORIGINS": "*"})
    client = app.test_client()

    response = client.get("/api/health", headers={"Origin": "https://anything.example"})
    # flask-cors answers a wildcard either literally or by echoing the request origin
    assert response.headers.get("Access-Control-Allow-Origin") in ("*", "https://anything.example")

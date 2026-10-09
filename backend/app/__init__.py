"""Flask application factory for the What's in My Food? backend."""

from __future__ import annotations

import os

from flask import Flask
from flask_cors import CORS

from app.routes.health import health_bp


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the Flask app.

    Configuration comes from environment variables (see ``.env.example``).
    Tests pass ``test_config`` to override values without touching the environment.
    """
    app = Flask(__name__)
    app.config.update(
        ENV=os.getenv("FLASK_ENV", "production"),
        DATABASE_URL=os.getenv("DATABASE_URL", ""),
        # Render sets RENDER_GIT_COMMIT on every deploy (#22); GIT_COMMIT overrides it.
        GIT_COMMIT=os.getenv("GIT_COMMIT") or os.getenv("RENDER_GIT_COMMIT") or "dev",
        CORS_ORIGINS=os.getenv("CORS_ORIGINS", "*"),
    )
    if test_config:
        app.config.update(test_config)

    CORS(app, origins=parse_origins(app.config["CORS_ORIGINS"]))

    app.register_blueprint(health_bp, url_prefix="/api")
    return app


def parse_origins(value: str | list[str]) -> str | list[str]:
    """Turn the CORS_ORIGINS setting into what flask-cors expects.

    ``"*"`` stays a wildcard. A comma-separated string such as
    ``"https://a.example, https://b.example"`` becomes a list of exact origins;
    flask-cors treats a plain string as a single origin, so passing the raw
    value through would match nothing.
    """
    if isinstance(value, list):
        return value
    value = value.strip()
    if value == "*" or value == "":
        return "*"
    return [origin.strip() for origin in value.split(",") if origin.strip()]

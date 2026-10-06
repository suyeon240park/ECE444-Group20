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
        GIT_COMMIT=os.getenv("GIT_COMMIT", "dev"),
        CORS_ORIGINS=os.getenv("CORS_ORIGINS", "*"),
    )
    if test_config:
        app.config.update(test_config)

    CORS(app, origins=app.config["CORS_ORIGINS"])

    app.register_blueprint(health_bp, url_prefix="/api")
    return app

"""Flask application factory for the What's in My Food? backend."""

from __future__ import annotations

import os

from flask import Flask
from flask_cors import CORS

from app.routes.health import health_bp
from app.routes.products import products_bp
from app.services.cache import TTLCache
from app.services.open_food_facts import OpenFoodFactsClient
from app.services.product_lookup import ProductLookupService


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
        OFF_BASE_URL=os.getenv("OFF_BASE_URL", "https://world.openfoodfacts.org"),
        OFF_USER_AGENT=os.getenv("OFF_USER_AGENT", "WhatsInMyFood/0.1 (ECE444 student project)"),
        OFF_TIMEOUT_SECONDS=float(os.getenv("OFF_TIMEOUT_SECONDS", "8")),
        PRODUCT_CACHE_TTL_SECONDS=float(os.getenv("PRODUCT_CACHE_TTL_SECONDS", "86400")),
    )
    if test_config:
        app.config.update(test_config)

    CORS(app, origins=parse_origins(app.config["CORS_ORIGINS"]))

    app.extensions["product_lookup"] = build_product_lookup(app.config)

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(products_bp, url_prefix="/api")
    return app


def build_product_lookup(config) -> ProductLookupService:
    """Wire the Open Food Facts client and cache from configuration.

    Stored in ``app.extensions["product_lookup"]``, which tests replace with a fake.
    """
    client = OpenFoodFactsClient(
        config["OFF_BASE_URL"], config["OFF_USER_AGENT"], config["OFF_TIMEOUT_SECONDS"]
    )
    return ProductLookupService(client, TTLCache(config["PRODUCT_CACHE_TTL_SECONDS"]))


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

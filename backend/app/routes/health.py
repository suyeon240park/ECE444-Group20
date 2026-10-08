"""Health check endpoint used by the client, CI and the staging deployment (#22)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """Return service status and the running commit so the client can show it."""
    return jsonify(
        {
            "status": "ok",
            "service": "whats-in-my-food-backend",
            "commit": current_app.config["GIT_COMMIT"],
        }
    )

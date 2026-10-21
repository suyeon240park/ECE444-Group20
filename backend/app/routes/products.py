"""Product lookup endpoint. The response contract is docs/api/openapi.yaml."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from app.services.errors import ProductLookupError

products_bp = Blueprint("products", __name__)


@products_bp.get("/products/<barcode>")
def get_product(barcode: str):
    """Look a packaged food up by barcode (F1)."""
    service = current_app.extensions["product_lookup"]
    try:
        result = service.lookup(barcode)
    except ProductLookupError as exc:
        error = exc.error
        return jsonify(error.to_dict()), error.http_status
    return jsonify(result.to_dict())

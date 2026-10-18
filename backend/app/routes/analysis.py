"""Product-analysis endpoints (#43). The response contract is ``AnalysisResult`` in
docs/api/openapi.yaml; docs/api/analysis.md explains it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from app.models.product import ErrorCode, ProductResult, is_valid_barcode
from app.routes.nutrition_label import uploaded_image
from app.services.errors import ProductLookupError
from app.services.fallback_routing import build_nutrition_only, merge_label_nutrition, route_lookup
from app.services.label_reading import LabelReading, LabelReadingError

analysis_bp = Blueprint("analysis", __name__)


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


@analysis_bp.get("/analysis/<barcode>")
def analyze_barcode(barcode: str):
    """Analyze a packaged food identified by barcode (F1 path 1/2).

    Errors are those of ``GET /api/products/{barcode}``: 400, 404, 502, 504. The
    ``next_step`` says whether to ask for a Nutrition Facts photo.
    """
    try:
        result = current_app.extensions["product_lookup"].lookup(barcode)
    except ProductLookupError as exc:
        return jsonify(exc.error.to_dict()), exc.error.http_status
    analysis = current_app.extensions["analysis"].analyze(result, route_lookup(result))
    return jsonify(analysis.to_dict())


@analysis_bp.post("/analysis/label-photo")
def analyze_label_photo():
    """Analyze a Nutrition Facts photo (F1 path 2/3).

    Request: ``multipart/form-data`` with the photo in ``image`` and, optionally, the
    scanned ``barcode``. With a barcode the database finds, the label's values are
    merged into that product (path 2). Otherwise the result is ``nutrition_only``
    and never claims a product was identified (path 3). Errors are those of
    ``POST /api/nutrition-label``, plus 400 ``invalid_barcode``.
    """
    barcode = (request.form.get("barcode") or "").strip() or None
    if barcode is not None and not is_valid_barcode(barcode):
        # Checked before the photo is read, so a client bug does not cost a model call.
        return _error(ErrorCode.INVALID_BARCODE.value, "Barcode must be 8 to 14 digits.", 400)
    try:
        reading = current_app.extensions["label_reader"].read(uploaded_image())
    except LabelReadingError as error:
        return _error(error.code, error.message, error.status)

    result = _with_product(reading, barcode) or build_nutrition_only(
        reading.serving, reading.nutrition, datetime.now(timezone.utc), reading.package
    )
    return jsonify(current_app.extensions["analysis"].analyze(result).to_dict())


def _with_product(reading: LabelReading, barcode: str | None) -> ProductResult | None:
    """The product the barcode identifies with the label merged in, or None if there is none."""
    if barcode is None:
        return None
    try:
        database = current_app.extensions["product_lookup"].lookup(barcode)
    except ProductLookupError as exc:
        # Not found, or the database failed: either way the product is not identified.
        current_app.logger.info("Label photo with barcode %s: %s", barcode, exc.code.value)
        return None
    return merge_label_nutrition(database, reading.serving, reading.nutrition, reading.package)

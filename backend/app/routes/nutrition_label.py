"""Nutrition Facts photo endpoint (#42).

``POST /api/nutrition-label`` reads a photo of a Nutrition Facts table and returns a
``nutrition_only`` product result (#20). It does not identify a product: when a
barcode lookup found the product but nutrition was missing (#15, path 2), the
pipeline (#43) merges this reading into the product with ``merge_label_nutrition``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from app.services.fallback_routing import build_nutrition_only
from app.services.label_reading import LabelReadingError

nutrition_label_bp = Blueprint("nutrition_label", __name__)

UPLOAD_FIELD = "image"

# Every error code this endpoint returns, in the order docs/api/openapi.yaml lists them.
ERROR_CODES = (
    "missing_image",
    "invalid_image",
    "file_too_large",
    "image_too_large",
    "unsupported_media_type",
    "nutrition_table_not_found",
    "upstream_unavailable",
    "photo_reading_unavailable",
    "upstream_timeout",
)


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


@nutrition_label_bp.post("/nutrition-label")
def read_nutrition_label():
    """Read the nutrition values on a Nutrition Facts photo.

    Request: ``multipart/form-data`` with the photo in the ``image`` field.

    Responses:
        200 ``ProductResult`` with ``result: nutrition_only``; every value is
            ``uncertain`` until the user confirms it (Q1)
        400 ``missing_image`` or ``invalid_image``
        413 ``file_too_large`` or ``image_too_large``
        415 ``unsupported_media_type``
        422 ``nutrition_table_not_found``
        502 ``upstream_unavailable``, 504 ``upstream_timeout``: the vision model failed
        503 ``photo_reading_unavailable``: no API key configured
    """
    try:
        reading = current_app.extensions["label_reader"].read(uploaded_image())
    except LabelReadingError as error:
        return _error(error.code, error.message, error.status)

    result = build_nutrition_only(
        reading.serving, reading.nutrition, datetime.now(timezone.utc), reading.package
    )
    return jsonify(result.to_dict())


def uploaded_image() -> bytes:
    """The photo in the request's ``image`` field; also used by the #43 pipeline."""
    if request.mimetype != "multipart/form-data":
        raise LabelReadingError(
            "missing_image",
            f"Send the photo as multipart/form-data in the '{UPLOAD_FIELD}' field.",
            400,
        )
    upload = request.files.get(UPLOAD_FIELD)
    if upload is None:
        raise LabelReadingError(
            "missing_image", f"No file was sent in the '{UPLOAD_FIELD}' field.", 400
        )
    return upload.read()


@nutrition_label_bp.errorhandler(RequestEntityTooLarge)
def too_large(_error_instance):
    """Flask raises this while reading the upload if it exceeds MAX_CONTENT_LENGTH."""
    return _error("file_too_large", "The uploaded file is too large. Upload a smaller photo.", 413)

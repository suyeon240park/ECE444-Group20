"""Barcode detection endpoint (#13).

``POST /api/barcode`` takes a product photo and returns the barcode in it. It does not
look the product up; the client passes the barcode to ``GET /api/products/{barcode}`` (#14).
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from app.services.barcode import BarcodeError, detect_barcode

barcode_bp = Blueprint("barcode", __name__)

UPLOAD_FIELD = "image"


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


@barcode_bp.post("/barcode")
def detect():
    """Detect the barcode in an uploaded product photo.

    Request: ``multipart/form-data`` with the photo in the ``image`` field.

    Responses:
        200 ``{"barcode": "...", "format": "EAN13"}``
        400 ``missing_image`` or ``invalid_image``
        413 ``file_too_large`` or ``image_too_large``
        415 ``unsupported_media_type``
        422 ``no_barcode_found``: the image is fine but no barcode could be read
    """
    if request.mimetype != "multipart/form-data":
        return _error(
            "missing_image",
            f"Send the photo as multipart/form-data in the '{UPLOAD_FIELD}' field.",
            400,
        )

    upload = request.files.get(UPLOAD_FIELD)
    if upload is None:
        return _error("missing_image", f"No file was sent in the '{UPLOAD_FIELD}' field.", 400)

    try:
        result = detect_barcode(upload.read())
    except BarcodeError as error:
        return _error(error.code, error.message, error.status)

    return jsonify({"barcode": result.barcode, "format": result.format})


@barcode_bp.errorhandler(RequestEntityTooLarge)
def too_large(_error_instance):
    """Flask raises this while reading the upload if it exceeds MAX_CONTENT_LENGTH."""
    return _error("file_too_large", "The uploaded file is too large. Upload a smaller photo.", 413)

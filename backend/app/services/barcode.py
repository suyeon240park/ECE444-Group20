"""Barcode detection from a product photo (#13).

``detect_barcode`` takes the raw bytes of an uploaded image and returns the retail
barcode in it, or raises ``BarcodeError`` with a stable ``code`` the route turns into
the API's ``{"error": {"code", "message"}}`` body.

This module only finds the barcode. Looking the product up is ``GET /api/products/{barcode}``
(#14); the Nutrition Facts fallback is #15.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import zxingcpp
from PIL import Image, ImageOps, UnidentifiedImageError

# Image formats accepted from the client. Detected from the file contents, not from the
# filename or the Content-Type header, which a client can set to anything.
SUPPORTED_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

# Reject photos larger than this before decoding. A 12 MP phone photo is well inside it.
MAX_IMAGE_PIXELS = 40_000_000

# Retail barcode symbologies from the product contract: EAN-8, UPC-A, EAN-13, GTIN-14.
# UPC-A is not listed because it is an EAN-13 with a leading 0; see ``_normalize``.
_FORMATS = (
    zxingcpp.BarcodeFormat.EAN8,
    zxingcpp.BarcodeFormat.EAN13,
    zxingcpp.BarcodeFormat.ITF14,
)

# The product contract accepts barcodes of 8 to 14 digits.
_MIN_DIGITS = 8
_MAX_DIGITS = 14


class BarcodeError(Exception):
    """A failure with a stable machine-readable ``code`` and the HTTP status to return."""

    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class DetectedBarcode:
    barcode: str
    format: str


def _too_many_pixels() -> BarcodeError:
    return BarcodeError(
        "image_too_large", "The image has too many pixels. Upload a smaller photo.", 413
    )


def load_image(data: bytes) -> Image.Image:
    """Validate ``data`` as a supported image and return it, rotated upright.

    Raises ``BarcodeError`` for empty, corrupt, unsupported or oversized images.
    """
    if not data:
        raise BarcodeError("invalid_image", "The uploaded file is empty.", 400)

    try:
        with Image.open(io.BytesIO(data)) as probe:
            image_format = probe.format
            width, height = probe.size
            probe.verify()
    except Image.DecompressionBombError:
        # Pillow refuses to open an image far past its own pixel limit (about 179 MP by
        # default) and raises this before our check below runs.
        raise _too_many_pixels() from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise BarcodeError(
            "invalid_image", "The uploaded file is not a readable image.", 400
        ) from None

    if image_format not in SUPPORTED_IMAGE_FORMATS:
        raise BarcodeError(
            "unsupported_media_type",
            "Unsupported image type. Upload a JPEG, PNG or WebP photo.",
            415,
        )
    if width * height > MAX_IMAGE_PIXELS:
        raise _too_many_pixels()

    try:
        # verify() leaves the image unusable, so decode from a fresh handle.
        image = Image.open(io.BytesIO(data))
        image.load()
    except (OSError, SyntaxError, ValueError):
        raise BarcodeError(
            "invalid_image", "The uploaded file is not a readable image.", 400
        ) from None

    # Phone photos often store their rotation in EXIF instead of in the pixels.
    return ImageOps.exif_transpose(image).convert("RGB")


def _normalize(text: str, format_name: str) -> DetectedBarcode:
    """Name the symbology and return the number as printed on the package.

    A UPC-A is an EAN-13 whose first digit is 0, and a scanner cannot tell them apart.
    Packages print the 12-digit UPC-A, so that is what is returned for them.
    """
    if format_name == "EAN13" and text.startswith("0"):
        return DetectedBarcode(barcode=text[1:], format="UPCA")
    return DetectedBarcode(barcode=text, format=format_name)


def detect_barcode(data: bytes) -> DetectedBarcode:
    """Return the retail barcode found in the image bytes ``data``.

    Raises ``BarcodeError`` if the image is invalid or contains no readable barcode.
    """
    image = load_image(data)

    for result in zxingcpp.read_barcodes(image, formats=_FORMATS):
        text = result.text
        if result.valid and text.isdigit() and _MIN_DIGITS <= len(text) <= _MAX_DIGITS:
            return _normalize(text, str(result.format).replace("-", ""))

    raise BarcodeError(
        "no_barcode_found",
        "No readable barcode was found. Retake the photo with the barcode flat, "
        "in focus and fully in frame.",
        422,
    )

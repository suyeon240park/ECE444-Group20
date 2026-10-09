"""Tests for ``POST /api/barcode`` (#13).

Barcode images are generated with python-barcode, so no binary fixtures are committed.
"""

from __future__ import annotations

import io

import barcode
import pytest
from barcode.writer import ImageWriter
from PIL import Image

from app import create_app
from app.services import barcode as barcode_service

EAN13 = "5901234123457"
EAN8 = "96385074"
UPCA = "036000291452"


def barcode_image(kind: str, value: str) -> Image.Image:
    """Render ``value`` as a barcode image of the given python-barcode symbology."""
    buffer = io.BytesIO()
    barcode.get(kind, value, writer=ImageWriter()).write(buffer)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


def encode(image: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture
def client():
    return create_app({"TESTING": True}).test_client()


def post_image(client, data: bytes, filename: str = "photo.png", content_type: str = "image/png"):
    return client.post(
        "/api/barcode",
        data={"image": (io.BytesIO(data), filename, content_type)},
        content_type="multipart/form-data",
    )


def assert_error(response, status: int, code: str):
    assert response.status_code == status
    body = response.get_json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]


# --- a readable barcode is detected -------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "value", "expected_format"),
    [("ean13", EAN13, "EAN13"), ("ean8", EAN8, "EAN8"), ("upca", UPCA, "UPCA")],
)
def test_detects_supported_barcodes(client, kind, value, expected_format):
    response = post_image(client, encode(barcode_image(kind, value)))

    # ``barcode`` is the number printed on the package, and is what
    # GET /api/products/{barcode} accepts (8 to 14 digits).
    assert response.status_code == 200
    assert response.get_json() == {"barcode": value, "format": expected_format}


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_accepts_each_supported_image_format(client, fmt):
    response = post_image(client, encode(barcode_image("ean13", EAN13), fmt))

    assert response.status_code == 200
    assert response.get_json()["barcode"] == EAN13


def test_detects_barcode_in_a_rotated_photo(client):
    image = barcode_image("ean13", EAN13).rotate(90, expand=True)

    assert post_image(client, encode(image)).get_json()["barcode"] == EAN13


def test_detects_barcode_on_a_larger_photo(client):
    """A barcode occupying a small part of a bigger photo, as on a real package."""
    code = barcode_image("ean13", EAN13)
    canvas = Image.new("RGB", (1600, 1200), (225, 215, 190))
    canvas.paste(code, (500, 450))

    assert post_image(client, encode(canvas, "JPEG")).get_json()["barcode"] == EAN13


def test_type_is_decided_by_file_contents_not_the_header(client):
    data = encode(barcode_image("ean13", EAN13))

    response = post_image(client, data, filename="photo.bin", content_type="application/x-foo")

    assert response.status_code == 200


# --- an image without a readable barcode returns a defined failure ------------------


def test_blank_image_has_no_barcode(client):
    response = post_image(client, encode(Image.new("RGB", (400, 300), "white")))

    assert_error(response, 422, "no_barcode_found")


def test_non_retail_barcode_is_not_returned(client):
    """Code 128 is a real barcode but not one of the retail formats the API accepts."""
    response = post_image(client, encode(barcode_image("code128", "HELLO-123")))

    assert_error(response, 422, "no_barcode_found")


# --- invalid input produces a clear error -------------------------------------------


def test_missing_image_field(client):
    response = client.post(
        "/api/barcode",
        data={"other": (io.BytesIO(b"x"), "x.png")},
        content_type="multipart/form-data",
    )

    assert_error(response, 400, "missing_image")


def test_request_that_is_not_multipart(client):
    response = client.post("/api/barcode", json={"image": "abc"})

    assert_error(response, 400, "missing_image")


def test_empty_file(client):
    assert_error(post_image(client, b""), 400, "invalid_image")


def test_file_that_is_not_an_image(client):
    response = post_image(client, b"definitely not an image", "notes.png", "image/png")

    assert_error(response, 400, "invalid_image")


def test_truncated_image(client):
    data = encode(barcode_image("ean13", EAN13))

    assert_error(post_image(client, data[: len(data) // 2]), 400, "invalid_image")


def test_unsupported_image_type(client):
    response = post_image(
        client, encode(barcode_image("ean13", EAN13), "GIF"), "photo.gif", "image/gif"
    )

    assert_error(response, 415, "unsupported_media_type")


def test_upload_over_size_limit():
    small_limit_client = create_app({"TESTING": True, "MAX_CONTENT_LENGTH": 1024}).test_client()

    response = post_image(small_limit_client, encode(barcode_image("ean13", EAN13)))

    assert_error(response, 413, "file_too_large")


def test_image_with_too_many_pixels(client, monkeypatch):
    monkeypatch.setattr(barcode_service, "MAX_IMAGE_PIXELS", 100)

    response = post_image(client, encode(barcode_image("ean13", EAN13)))

    assert_error(response, 413, "image_too_large")


def test_wrong_method_is_405(client):
    assert client.get("/api/barcode").status_code == 405

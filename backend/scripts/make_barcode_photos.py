"""Make the barcode photo set for the Q2 load test (#68).

Writes ``tests/fixtures/barcode_photos/``: one photo per row of ``manifest.csv`` whose
``photo`` is a file in that folder. Each is a package-like picture with an EAN-13 barcode
printed on it, slightly rotated and blurred, saved as a phone-sized JPEG. The pictures are
drawn, not photographed, so the set is free to share and the same each time it is made.
Rows that point at a Nutrition Facts photo (``../nutrition_labels/...``) are real photos
with no barcode in them and are not written.

Run from ``backend/`` (needs the dev requirements, for ``python-barcode``)::

    python -m scripts.make_barcode_photos

Then check that every photo reads as the manifest says: ``pytest tests/test_load_test.py``.
"""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

from barcode import EAN13
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parents[2]
PHOTOS = REPO / "tests" / "fixtures" / "barcode_photos"
MANIFEST = PHOTOS / "manifest.csv"

SIZE = (1600, 1200)
BACKGROUNDS = [(236, 226, 203), (250, 250, 245), (214, 232, 240), (246, 220, 214), (226, 240, 220)]


def barcode_image(digits: str) -> Image.Image:
    """The EAN-13 symbol for ``digits`` (12- or 13-digit GTIN), black on white."""
    ean = digits.zfill(13)
    writer = ImageWriter()
    options = {"module_width": 0.4, "module_height": 18, "quiet_zone": 4, "font_size": 12}
    return EAN13(ean, writer=writer).render(options).convert("RGB")


def package(seed: int, digits: str | None) -> Image.Image:
    """A package side with text-like blocks and, if ``digits`` is given, a barcode."""
    rng = random.Random(seed)
    canvas = Image.new("RGB", SIZE, rng.choice(BACKGROUNDS))
    draw = ImageDraw.Draw(canvas)
    for _ in range(14):  # lines of "text" around the barcode
        x, y = rng.randint(60, 1100), rng.randint(60, 1100)
        draw.rectangle(
            [x, y, x + rng.randint(120, 420), y + rng.randint(10, 22)], fill=(70, 70, 70)
        )
    if digits:
        symbol = barcode_image(digits)
        symbol = symbol.resize((int(symbol.width * 1.6), int(symbol.height * 1.6)))
        symbol = symbol.rotate(rng.uniform(-6, 6), expand=True, fillcolor=(255, 255, 255))
        x = rng.randint(200, SIZE[0] - symbol.width - 200)
        y = rng.randint(250, SIZE[1] - symbol.height - 150)
        canvas.paste(symbol, (x, y))
    return canvas.filter(ImageFilter.GaussianBlur(rng.uniform(0.6, 1.2)))


def read_manifest() -> list[dict[str, str]]:
    with MANIFEST.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def main() -> int:
    written = 0
    for number, row in enumerate(read_manifest()):
        if "/" in row["photo"]:
            continue  # a real photo kept elsewhere
        image = package(number, row["barcode"] or None)
        image.save(PHOTOS / row["photo"], "JPEG", quality=85)
        written += 1
    print(f"wrote {written} photos to {PHOTOS.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The Nutrition Facts benchmark set keeps the shape issue #17 and Q1 ask for.

These tests check size, categories, hard photos and the folder rules. They cannot tell
whether a value is right: that is the teammates' check described in the README.
"""

import csv
from collections import Counter

from PIL import Image

from scripts.label_benchmark import DEFAULT_FIXTURES, FIELDS, NOT_FOUND, UNREADABLE, load_truth

IMAGES = DEFAULT_FIXTURES / "images"
TRUTH = load_truth(DEFAULT_FIXTURES / "ground_truth.csv")
with (DEFAULT_FIXTURES / "images.csv").open(newline="", encoding="utf-8") as f:
    META = {row["image"]: row for row in csv.DictReader(f)}

STATUS_ONLY = (NOT_FOUND, UNREADABLE)


def status(image: str) -> str | None:
    return next((r.expected for r in TRUTH[image] if r.field == "status"), None)


def scored_images() -> list[str]:
    return [image for image in TRUTH if status(image) not in STATUS_ONLY]


def test_every_photo_has_ground_truth_and_a_row_in_images_csv():
    photos = {p.name for p in IMAGES.glob("*.jpg")}
    assert photos == set(TRUTH) == set(META)


def test_scored_photos_list_every_q1_field_once():
    fields = [f for f in FIELDS if f != "status"]
    for image in scored_images():
        assert sorted(r.field for r in TRUTH[image]) == sorted(fields), image


def test_status_only_photos_have_a_single_row():
    for image in TRUTH:
        if status(image) is not None:
            assert len(TRUTH[image]) == 1, image


def test_meets_issue_17():
    scored = scored_images()
    assert len(scored) >= 50
    assert len({META[i]["category"] for i in scored}) >= 5
    hard = [i for i in scored if META[i]["difficulty"] in ("glare", "curved")]
    assert len(hard) >= 10
    assert any(status(i) == UNREADABLE for i in TRUTH)
    assert any(status(i) == NOT_FOUND for i in TRUTH)


def test_products_are_distinct():
    barcodes = Counter(
        m["barcode"] for i, m in META.items() if m["barcode"] and i in scored_images()
    )
    assert [code for code, n in barcodes.items() if n > 1] == []


def test_photos_follow_the_folder_rules():
    for path in IMAGES.glob("*.jpg"):
        assert path.stat().st_size < 2_000_000, path.name
        with Image.open(path) as im:
            assert not im.getexif(), f"{path.name} has EXIF metadata"


def test_downloaded_photos_carry_their_licence():
    for image, meta in META.items():
        if meta["source"] == "Open Food Facts":
            assert meta["license"] == "CC BY-SA 3.0", image
            assert meta["image_url"].startswith("https://images.openfoodfacts.org/"), image

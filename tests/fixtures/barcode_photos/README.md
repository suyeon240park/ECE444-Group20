# Barcode photos (Q2 load test)

The photo set for the Q2 load test (issue #68, `backend/scripts/load_test.py`): 20 photos, one per row of `manifest.csv`, sent to `POST /api/barcode` all at once.

| Case | Photos | What the server should answer |
|---|---:|---|
| `known` | 12 | the barcode, then the product from Open Food Facts (cereal, chips, soup, pasta, yogurt, juice sold in Canada, from the #28 sample) |
| `unknown` | 3 | the barcode, then `product_not_found`: valid check digits, not in Open Food Facts |
| `no_barcode` | 5 | `no_barcode_found` |

The 15 barcodes are exactly Open Food Facts' 15 product reads per minute, so the first round stays within its rate limit.

`01` to `16` are drawn by `python -m scripts.make_barcode_photos` (run from `backend/`): an EAN-13 barcode on a package-like background, rotated up to 6° and slightly blurred, as a 1600 × 1200 JPEG. They are drawn rather than photographed so they can be shared and made again exactly. The other four `no_barcode` rows are real Nutrition Facts photos from `../nutrition_labels/images/`, so the barcode reader also gets a real phone photo with nothing to find.

`tests/test_load_test.py` checks that every photo reads as `manifest.csv` says and stays under Q2's 10 MB limit. To change the set, edit `manifest.csv`, re-run the script, and run that test. Keep at most 15 rows with a barcode.

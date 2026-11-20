# Developer scripts

Run from `backend/` with the virtual environment active. They read `backend/.env`.

## Vision-model label extraction prototype (#16)

Time-boxed spike: can a vision-model API read Canadian Nutrition Facts tables well enough to keep the photo fallback (Q1, #4)? The extraction code is `app/services/label_extraction.py`; it uses Google's Gemini API.

Setup:

1. Create an API key at <https://aistudio.google.com/apikey> (free tier, no card).
2. In `backend/.env` set `GEMINI_API_KEY`, and `VISION_MODEL` if `gemini-3.5-flash` is no longer offered (Google retires older models for new keys; on October 8, 2026 `gemini-3.8-flash` was overloaded and its free quota ran out within minutes). Optionally set `VISION_PRICE_INPUT_PER_MTOK` and `VISION_PRICE_OUTPUT_PER_MTOK` from <https://ai.google.dev/pricing> to get cost per photo.
3. Fill in `tests/fixtures/nutrition_labels/ground_truth.csv` (format in that folder's README).

One photo:

```
python -m scripts.extract_label ../tests/fixtures/nutrition_labels/images/005_crackers.jpg
```

Whole set, as a Markdown report for the issue:

```
python -m scripts.label_benchmark --out ../.label-results
python -m scripts.label_benchmark --from ../.label-results   # re-score without calling the API
```

What is measured: aggregate and per-field accuracy under Q1's rules (fields not printed are not counted), every mismatch, "extra" values the model returned for fields that are not printed, response time, tokens and cost per photo.

Known limits of the prototype:

- Vision models give no per-field confidence. The model is told to return `null` for anything it cannot read with certainty and to list it in `unreadable_fields`; Q1's confidence rule is not implemented.
- Free-tier requests may be used by Google to improve its models. The fixtures contain only package photos, so this is acceptable for the benchmark but must be revisited before user photos are sent.

## Recording replies for the end-to-end tests (#44)

`tests/test_end_to_end.py` replays real Gemini replies so CI makes no API calls. To record one (needs `GEMINI_API_KEY`):

```
python -m scripts.record_gemini_reply ../tests/fixtures/nutrition_labels/images/010_dark-sauce.jpg tests/fixtures/e2e/gemini_010_dark-sauce.json
```

The photo is prepared as the server prepares it, and `VISION_MODEL` then each fallback model is tried. Only the reply and the model that gave it are saved, never the request or the key. List new recordings in `tests/fixtures/e2e/README.md`.

## Smoke test of staging (#72)

Checks the deployed app end to end: health and commit, CORS, a barcode photo, a complete product, an incomplete product with a label photo and confirmation, an unknown barcode with a label photo, and bad input. It waits up to 120 s for a sleeping Render backend (`--wake-seconds`).

```
python -m scripts.smoke_test                  # staging
python -m scripts.smoke_test --skip-photos    # no vision-model calls
```

`--api` and `--app` point it at another deployment; the commit check needs a web build (`npm run build:web`), not the Expo dev server. Exit status 0 when every check passes, 1 otherwise. See `docs/deployment.md` for the pre-demo checklist.

## Q2 load test of product identification (#68)

Times what the app does after a photo is taken, `POST /api/barcode` and then `GET /api/products/{barcode}`, with 20 requests at once, following Q2's verification method: the cold start on its own, Open Food Facts timed directly (4 s apart, within its 15 reads per minute), one round of the 20 photos in `tests/fixtures/barcode_photos/` (external lookups, unknown products, no barcode), then rounds the server answers from its product cache.

```
python -m scripts.load_test --out ../q2.json   # staging; also saves every request
python -m scripts.load_test --from ../q2.json  # the report again, sending nothing
```

Run it 15 minutes after the last request, so the backend is asleep and its cache empty; the report says if known products were already cached. It reports, per kind of identification, the share within target (5 s; 1 s for cached, provisional), p50, p95, max, the share with no answer within 10 s, and unexpected answers. Times are measured by the client, so they include the network and upload that Q2's server-side measure leaves out; the median `/api/health` round trip shows about how much. Exit status 0 when Q2's targets are met, 1 otherwise. The photo set is made by `python -m scripts.make_barcode_photos`; see its README.

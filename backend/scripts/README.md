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

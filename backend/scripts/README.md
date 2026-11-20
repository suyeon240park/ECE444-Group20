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

## Accuracy verification against Q1 (#18)

The same command is the Q1 check. Its report starts with a verdict, and its exit status says whether Q1 is met:

| Exit status | Meaning |
|---|---|
| 0 | Aggregate accuracy is at least **95%** and no critical value can be used before the user confirms it |
| 1 | The run is not usable: a setup error (no photos, no `GEMINI_API_KEY`, a mistake in `ground_truth.csv`), or **INCOMPLETE**: some photos failed with an API error such as a quota limit (HTTP 429) |
| 2 | Q1 not met |

What the report adds to the per-photo, mismatch and per-field tables:

- **Verdict line.** PASS, FAIL or INCOMPLETE. An API error says nothing about extraction accuracy, so photos that failed that way are left out of the score and listed ("error, not scored") instead of counting as misreads, and the run is INCOMPLETE: repeat it. Aggregate accuracy against the 95% target and the number of correct fields that would have been needed. The comparison uses the counts, so 94.99% fails even though it prints as 95.0%. Nothing scored counts as a fail.
- **Critical fields.** Accuracy of `serving.quantity` and `package.servings_per_package` on their own, a list of every wrong or missing critical value, and the **safe-use** result. Q1 asks for 100% safe use: for each reply with a table, the script builds the product the API would build (`to_contract`) and asks F2 (`calculate_package_nutrition`) for whole-package values with nothing confirmed. A photo fails if a critical value is not `uncertain`, if F2 calculates anything, or if the reply cannot be read. A wrong critical value is not a safe-use failure: the user catches it on the confirm screen (#39), and it is listed so the team can see how often that happens.
- **Reproducible runs.** `--out DIR` saves every reply and `--from DIR` scores them again with no API calls, so a number in a report can be re-checked, and a change to the scoring can be tried on old replies. The model is named in the report. Re-running live can differ a little because the model's replies do.

The target is the constant `TARGET_ACCURACY`. Q1 allows changing it only through a reviewed requirements revision, so there is no command-line flag for it.

**A PASS counts toward Q1 only once two teammates have checked the ground truth.** Photos 011 to 054 are still a draft (`tests/fixtures/nutrition_labels/README.md`); the report says so under its verdict.

### In CI

`.github/workflows/extraction-benchmark.yml` runs the benchmark on pull requests that change the extraction code (`label_extraction.py`, `label_reading.py`, `package_nutrition.py`, the product model), the benchmark script or the fixtures, and on demand from the Actions tab. It prints the report into the job summary, keeps the saved replies as a build artifact for 30 days, and fails the check on exit status 1 (setup error or INCOMPLETE run) or 2 (below target).

It needs the repository secret `GEMINI_API_KEY` (Settings, Secrets and variables, Actions, New repository secret). Add it in GitHub's page, never in a file or a chat. Optionally add the repository variable `VISION_MODEL`. Without the secret the job passes with a warning and the benchmark did not run, so do not read a green check as "benchmark passed" until the secret exists. A full run makes 54 requests and can take several minutes. If the key is the one the staging server uses, a run can use up the day's free quota and break the Nutrition Facts photo path on staging, so use a **separate key** for the CI secret (and avoid running it just before a demo). on the free tier a rate limit adds 30-second waits.

Known limits of the prototype:

- Vision models give no per-field confidence. The model is told to return `null` for anything it cannot read with certainty and to list it in `unreadable_fields`; Q1's confidence rule is not implemented: every photo value is treated as uncertain until the user confirms it (#39).
- The benchmark measures `VISION_MODEL` alone: the app falls back to two other models when the first is busy, and the benchmark does not, so a live reading can come from a different model than the one scored here.
- The benchmark sends each original photo to the model. The API (`label_reading.prepare_photo`) first shrinks it to 2000 px on the longest side, so a live user's photo can read slightly differently from the benchmark's.
- Free-tier requests may be used by Google to improve its models. The fixtures contain only package photos, so this is acceptable for the benchmark but must be revisited before user photos are sent.

## Recording replies for the end-to-end tests (#44)

`tests/test_end_to_end.py` replays real Gemini replies so CI makes no API calls. To record one (needs `GEMINI_API_KEY`):

```
python -m scripts.record_gemini_reply ../tests/fixtures/nutrition_labels/images/010_dark-sauce.jpg tests/fixtures/e2e/gemini_010_dark-sauce.json
```

The photo is prepared as the server prepares it, and `VISION_MODEL` then each fallback model is tried. Only the reply and the model that gave it are saved, never the request or the key. List new recordings in `tests/fixtures/e2e/README.md`.

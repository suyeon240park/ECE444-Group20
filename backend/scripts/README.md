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

## Q3 readability check (#70)

Flesch-Kincaid grade of the explanation text the results page shows: the %DV definition, each nutrient's "what it is" and "how to read" text, and each matched ingredient's explanations, flag reason and authority statements. It runs the app's own services on each product, so re-run it after any change to `content/`.

```
python -m scripts.readability                   # the three default products, Markdown report
python -m scripts.readability --json            # the same as JSON
python -m scripts.readability --product ../my-products/cheerios.json=cereal --product ...
```

A product file is an Open Food Facts v3 response, saved for example with
`curl -A "<your app name>" "https://world.openfoodfacts.org/api/v3/product/<barcode>" -o <file>`.
Append `=category` to label it. Use the usability-test products (#69) once they are chosen.

Preprocessing follows Q3: product names and brands, ingredient names, aliases and E/INS numbers, source citations and URLs are removed. "%DV" is removed too, since the results page defines it in its glossary box; `--keep-defined-terms` scores it.

Each product's text is joined into one passage and graded; the result is the mean over products, passing at grade 8 or below (exit status 0, or 1 on a fail). The report also lists the five hardest single texts to rewrite first. One-sentence texts are not reliable passages on their own (Q3), so they are not pass/fail.

Syllables are counted with the usual vowel-group rules, not a dictionary, so grades can differ slightly from other tools; the count is deterministic, so a grade changes only when the text does.

## Smoke test of staging (#72)

Checks the deployed app end to end: health and commit, CORS, a barcode photo, a complete product, an incomplete product with a label photo and confirmation, an unknown barcode with a label photo, and bad input. It waits up to 120 s for a sleeping Render backend (`--wake-seconds`).

```
python -m scripts.smoke_test                  # staging
python -m scripts.smoke_test --skip-photos    # no vision-model calls
```

`--api` and `--app` point it at another deployment; the commit check needs a web build (`npm run build:web`), not the Expo dev server. Exit status 0 when every check passes, 1 otherwise. See `docs/deployment.md` for the pre-demo checklist.

## Usability test scoring (#69)

`python -m scripts.usability_report ../docs/usability/session-1` reads the three anonymized CSV files of a usability session (`participants.csv`, `attempts.csv`, `sus.csv`; blank templates and the rules are in `docs/usability/`), checks Q3's conditions (5 or more outside participants, 3 or more on a phone and 2 or more on a desktop, 3 or more product categories, nobody with nutrition training), and prints overall and per-task success, mean SUS and the T3/T4 scorer disagreements against Q3's targets (80%, 3 of 5 per task, SUS 68).

Exit status: 0 when every target is met, 1 when the files or conditions are not valid (the run must not be reported), 2 when a target is missed. `--pilot` scores a run that does not meet Q3's conditions (for example one team member trying the tasks): the report is stamped as a pilot with no Q3 verdict, and the exit status is 0 for valid files. A target is changed only through a reviewed requirements revision, so none is a command-line option.

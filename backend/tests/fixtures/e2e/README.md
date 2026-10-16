# Recorded vision-model replies (#44)

Used by `tests/test_end_to_end.py`, which replays them instead of calling Gemini, so CI
needs no API key. Each file is `{"model": ..., "reply": ...}`: the model that answered
and its unedited `generateContent` response body. Requests, and so the API key, are
never stored.

Recorded on 2026-10-16 with `scripts/record_gemini_reply.py` (see `scripts/README.md`),
using the server's own photo preparation and model order. `gemini-3.5-flash` was
rate limited for the label photos, so those came from the first fallback model.

| File | Photo | Model | Matches `ground_truth.csv` |
|---|---|---|---|
| `gemini_005_crackers.json` | `005_crackers.jpg` | `gemini-3-flash-preview` | yes |
| `gemini_008_ketchup.json` | `008_ketchup.jpg` (Heinz Ketchup Zero, `0057000002916`) | `gemini-3-flash-preview` | yes |
| `gemini_010_dark-sauce.json` | `010_dark-sauce.jpg` (Premium Oyster Sauce, `4891130005418`) | `gemini-3-flash-preview` | one extra value: carbohydrate %DV `0`, which the label does not print |
| `gemini_no_table.json` | `no_table.png` (the app icon: no Nutrition Facts table) | `gemini-3.5-flash` | `table_found: false` |

The label photos are in `tests/fixtures/nutrition_labels/images/` at the repository
root. The model's mistake on 010 is kept as recorded: the end-to-end tests check the
flow, not extraction accuracy, which the Q1 benchmark (#17) measures.

To re-record after changing the prompt or the photo preparation, run the script
again for each photo and re-run `pytest tests/test_end_to_end.py`.

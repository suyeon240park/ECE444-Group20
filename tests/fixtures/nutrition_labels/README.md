# Nutrition Facts label photos (benchmark fixtures)

This folder holds the benchmark set required by requirement **Q1** (issue #4) and built in issue #17: at least 50 phone photos of Canadian Nutrition Facts tables plus a manually transcribed ground truth. The first 10 photos were added for the vision-model prototype (#16).

Layout:

```
tests/fixtures/nutrition_labels/
├── README.md
├── ground_truth.csv      one row per field: image, field, expected value, unit
└── images/
    ├── 001_herbal-tea.jpg
    └── ...
```

Rules:

- Photos must not contain personal information. Crop to the package.
- Name files `NNN_short-description.jpg`. Keep images under 2 MB, upright, without EXIF metadata.
- Every value in `ground_truth.csv` is transcribed by one teammate and checked by a second, as Q1 requires.
- Transcribe from the package itself, not from the photo and not with an AI tool: the ground truth is what the extraction is checked against, so it must not share the extractor's mistakes.
- Do not put user-uploaded photos here. Only photos taken by the team for this purpose.

## `ground_truth.csv`

| Column | Meaning |
|---|---|
| `image` | file name in `images/` |
| `field` | one of Q1's atomic fields, named as in the product contract (#20): `serving.household`, `serving.quantity`, `package.servings_per_package`, `nutrition.nutrients.<name>.amount`, `nutrition.nutrients.<name>.daily_value_percent` |
| `expected` | the value as printed: a number (`1.5`, `310`) or, for `serving.household`, the text (`6 crackers`). `-` when the label does not print the field. Never leave it blank |
| `unit` | for amounts and `serving.quantity`: `g`, `mg`, `mL` or `kcal`; checked against the extracted unit |

Nutrient names: `calories`, `total_fat`, `saturated_fat`, `trans_fat`, `carbohydrate`, `fibre`, `sugars`, `protein`, `cholesterol`, `sodium`.

Labelling conventions:

- The single %DV printed for "Saturated + Trans" goes on `saturated_fat.daily_value_percent`; `trans_fat.daily_value_percent` is always `-`.
- Calories have no %DV row.
- English serving statement only: `Per 1 tbsp (15 mL)` gives `serving.household` = `1 tbsp`, `serving.quantity` = `15`, unit `mL`.
- A photo without a Nutrition Facts table has a single row: `NNN_x.jpg,status,not_found,`.

Scoring (`backend/scripts/label_benchmark.py`) ignores case, whitespace and abbreviation dots (`1 tsp.` equals `1tsp`), and leaves `-` fields out of the accuracy denominator, as Q1 specifies.

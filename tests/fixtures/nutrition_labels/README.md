# Nutrition Facts label photos (benchmark fixtures)

This folder holds the benchmark set required by requirement **Q1** (issue #4) and built in issue #17: phone photos of Nutrition Facts tables from 52 distinct products sold in Canada, plus a transcribed ground truth. The first 10 photos were taken by the team for the vision-model prototype (#16). Photos 011 to 054 are shoppers' phone photos from [Open Food Facts](https://world.openfoodfacts.org), licensed [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/); `images.csv` credits each one.

Layout:

```
tests/fixtures/nutrition_labels/
├── README.md
├── ground_truth.csv      one row per field: image, field, expected value, unit
├── images.csv            one row per photo: category, difficulty, source and licence
└── images/
    ├── 001_herbal-tea.jpg
    └── ...
```

Rules:

- Photos must not contain personal information. Crop to the package.
- Name files `NNN_short-description.jpg`. Keep images under 2 MB, upright, without EXIF metadata.
- Only photos taken by the team, or openly licensed photos whose source and licence are recorded in `images.csv`. Never user-uploaded photos.
- A value in `ground_truth.csv` is final only once two teammates have each checked it against the photo at full size ([Q1](../../../docs/requirements.md#q1--nutrition-values-extracted-from-a-label-photo-must-match-the-printed-label), verification steps 2 and 3). The ground truth is what the extraction is checked against, so it must not share the extractor's mistakes: never copy a value from the extractor's output.
- `tests/test_benchmark_dataset.py` fails if the set stops meeting #17 (50 scored products, 5 categories, 10 hard photos) or a photo breaks these rules. It cannot tell whether a value is right; only the teammates' check can.

### Status of the values

| Photos | How they were transcribed | Checked by two teammates |
|---|---|---|
| 001 to 010 | by hand from the package, by the team (#16) | under the rule at the time: one teammate transcribes, a second checks |
| 011 to 054 | see below | **not yet**: the check sheet is on PR #57 |

Until 011 to 054 are checked, they are a draft: an accuracy number from this set must not be reported as meeting Q1.

How photos 011 to 054 were transcribed (October 18, 2026): the packages were not available, so an AI assistant made the first transcription from each photo at full resolution. It is a different model from the one the benchmark scores (`VISION_MODEL` and its fallbacks), so the two do not share the same reading of a photo. The values were then cross-checked two ways: against the per-serving values Open Food Facts contributors typed in by hand (241 values agreed and 49 did not; each disagreement was either re-read on the photo, which matched the transcription, or came from an Open Food Facts record for a different serving size or converted from per-100 g values), and by recomputing every printed %DV from its amount and every calorie count from fat, carbohydrate and protein. Q1 asks for a manual transcription, so the teammates' check replaces it: each of them reads every value on the photo, not on the sheet.

Special photos:

- **053** is a degraded copy of a real label, shrunk to 1/16 of its size, scaled back up and blurred, so a reviewer can make out the table's layout but not one of its numbers. (An earlier, lighter version only hid the decimal points, and the values could still be worked out from each other.) It tests the `unreadable` path; Q1 leaves such photos out of the accuracy and counts them as unsupported input ([Q1](../../../docs/requirements.md#q1--nutrition-values-extracted-from-a-label-photo-must-match-the-printed-label), conditions).
- **054** is the front of the same Weetabix box as 012. It tests the `not_found` path and is not scored, so the product is not counted twice.

Licence: photos 011 to 054 are CC BY-SA 3.0. We comply by crediting each photo in `images.csv` (product page and original image URL) and keeping this licence on them; crops and the degraded 053 are shared under the same licence.

## `ground_truth.csv`

| Column | Meaning |
|---|---|
| `image` | file name in `images/` |
| `field` | one of Q1's atomic fields, named as in the product contract (#20): `serving.household`, `serving.quantity`, `package.servings_per_package`, `nutrition.nutrients.<name>.amount`, `nutrition.nutrients.<name>.daily_value_percent` |
| `expected` | the value as printed: a number (`1.5`, `310`) or, for `serving.household`, the text (`6 crackers`). `-` when the label does not print the field. Never leave it blank |
| `unit` | for amounts and `serving.quantity`: `g`, `mg`, `mL` or `kcal`; checked against the extracted unit |

Nutrient names: `calories`, `total_fat`, `saturated_fat`, `trans_fat`, `carbohydrate`, `fibre`, `sugars`, `protein`, `cholesterol`, `sodium`.

## `images.csv`

| Column | Meaning |
|---|---|
| `image` | file name in `images/` |
| `category` | `beverages`, `cereal_bread`, `condiments`, `dairy`, `deli_meat`, `frozen_packaged_meals` or `snacks` (Q1 needs at least five) |
| `difficulty` | `curved`, `glare`, `blur` or `none` (Q1 needs at least 10 `curved` or `glare`); see the definitions below |
| `source`, `barcode`, `product`, `product_url`, `image_url`, `license` | where the photo comes from; empty for the team's own photos |
| `notes` | anything a reviewer should know, such as which column was transcribed |

Difficulty: one label per photo, for the effect that most gets in the way of reading it.

- `glare`: a reflection hides or washes out part of the table's text.
- `curved`: the table is printed on a bent or crinkled surface (a tub, can, bottle or bag), so in the photo its rows or columns visibly curve or its edges recede.
- `blur`: the text is out of focus or too low-resolution to read easily.
- `none`: a flat, sharp, evenly lit table.

Labelling conventions:

- The single %DV printed for "Saturated + Trans" goes on `saturated_fat.daily_value_percent`; `trans_fat.daily_value_percent` is always `-`.
- Calories have no %DV row.
- English serving statement only: `Per 1 tbsp (15 mL)` gives `serving.household` = `1 tbsp`, `serving.quantity` = `15`, unit `mL`.
- If the table has several columns ("as sold" and "prepared", or "cereal" and "with milk"), only the first is transcribed, as the extractor is told to do.
- A photo without a Nutrition Facts table has a single row: `NNN_x.jpg,status,not_found,`.
- A photo whose table a human reviewer cannot read has a single row: `NNN_x.jpg,status,unreadable,`. Q1 leaves it out of the accuracy and the report counts it as unsupported input.

Scoring (`backend/scripts/label_benchmark.py`) ignores case, whitespace and abbreviation dots (`1 tsp.` equals `1tsp`), and leaves `-` fields out of the accuracy denominator, as Q1 specifies.

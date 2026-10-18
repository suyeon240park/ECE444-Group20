# Product-analysis pipeline (#43)

One call returns everything the results page (#41) shows. The JSON shape is
`AnalysisResult` in [`openapi.yaml`](openapi.yaml); this page explains how to use it.

```
GET  /api/analysis/{barcode}          barcode scan (F1 paths 1 and 2)
POST /api/analysis/label-photo        Nutrition Facts photo (F1 paths 2 and 3)
     multipart/form-data: image (required), barcode (optional)
```

## Response

The first four keys are the product contract ([README.md](README.md)), unchanged.
Four sections follow:

| Key | What it is | `null` when |
|---|---|---|
| `result`, `completeness`, `missing_fields`, `product` | The product (#20) | never |
| `next_step` | What to do after a barcode lookup (#15) | the result came from a photo |
| `package_nutrition` | Per-serving and whole-package nutrition (#36, F2). See [package-nutrition.md](package-nutrition.md) | the calculation failed |
| `explanations` | Per-serving %DV, its 5% / 15% reading and nutrient explanations (#37, F3). See [nutrient-explanations.md](nutrient-explanations.md) | the nutrient content did not load or the section failed |
| `ingredients` | Ingredient analysis (#33, F4). See [ingredient-analysis.md](ingredient-analysis.md) | the knowledge base did not load or the analysis failed |

**Each section stands alone.** A product with no ingredient list still has its
nutrition, and the reverse. A section that fails is logged and returned as `null`,
and the others are still returned. When a section is `null`, the results page shows
that section's "not available" message:
- nutrition: "Not available";
- explanations: "No verified explanation available yet.";
- ingredients: "Ingredient information not available".

## Flow

```
scan barcode ── GET /api/analysis/{barcode}
   ├─ 200, next_step.action = use_database             → show results
   ├─ 200, next_step.action = request_nutrition_photo  → show results, offer a label photo
   │        └─ POST /api/analysis/label-photo  (image + barcode)  → result: product
   ├─ 404 product_not_found                            → offer a label photo
   │        └─ POST /api/analysis/label-photo  (image)            → result: nutrition_only
   └─ 400 / 502 / 504                                  → retry or offer a label photo

photo result ── user confirms or corrects the values (#39)
   └─ POST /api/analysis/confirm  (the result, checked values user_confirmed) → re-analyzed
```

- **Barcode path.** Errors are those of `GET /api/products/{barcode}`. On 200,
  `next_step` is #15's routing: `request_nutrition_photo` lists the
  `photo_fields` a label photo would fill.
- **Photo path with a barcode** the database finds (path 2). The label's serving
  and nutrients are merged into that product (`merge_label_nutrition`, #15).
  The label's servings per package is used when the database has none.
  Identity and ingredients stay from the database.
- **Photo path otherwise** (path 3: no barcode, not found, or the database failed).
  The result is `nutrition_only`: no barcode, name, brand or ingredients, and it
  must be labelled "Nutrition-only result" (F1). `ingredients.status` is
  `unavailable`.
- **Photo errors** are those of `POST /api/nutrition-label`. A malformed `barcode`
  gives 400 `invalid_barcode` before the photo is read.

## Photo values and confirmation (Q1)

Every value read from a photo is `uncertain`. `package_nutrition` does not scale
those values; it lists them in `pending_confirmation`. `explanations` shows them as
`needs_confirmation`, with no %DV reading or explanation. A value counts as confirmed
when its `certainty` is `user_confirmed`; the pipeline then scales and explains it
(`confirmed_paths` in `app/services/analysis.py`).

The client's confirm screen (#39) sends the photo result back to
`POST /api/analysis/confirm` with the checked values marked `user_confirmed`:

- Only label-photo values are read from the request. A `product` result is looked
  up again by barcode, and its database values come from that lookup, so a client
  cannot change or confirm database data (`app/services/confirmation.py`).
- A photo serving replaces the database's serving and nutrition, as in
  `merge_label_nutrition`; without one, photo nutrients only fill gaps, and one
  that would replace a database value is refused with 400 `invalid_confirmation`.
- A photo value may only be `uncertain` or `user_confirmed`. A user correction is
  sent as the edited amount with `user_confirmed`.

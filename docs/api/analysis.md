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
| `explanations` | %DV interpretation and nutrient explanations (#37, F3) | always, until #37 is merged |
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
those values; it lists them in `pending_confirmation`. A value counts as confirmed
when its `certainty` is `user_confirmed`. Confirming values on the client and
sending them back is #39's work. The pipeline already scales `user_confirmed`
values (`confirmed_paths` in `app/services/analysis.py`).

## Not done yet

- **`explanations` (#37).** The section will be filled when #37 is merged.
  Its shape is agreed with #37's author then.
- **Confirmation round trip (#39).** There is no endpoint yet that takes
  user-confirmed values back.

# Product API contract (#20)

This is the agreed shape of the product data the backend returns, so the barcode (#13), product lookup (#14), Nutrition Facts OCR (#15) and vision (#16) work, and the analysis features built on them (F2–F4), can be developed in parallel.

| File | What it is |
|---|---|
| [`openapi.yaml`](openapi.yaml) | The machine-readable contract: endpoint, schemas, and an example of every response. |
| [`backend/app/models/product.py`](../../backend/app/models/product.py) | The Python model. Every producer builds these objects and serializes them with `to_dict()`. |
| [`backend/tests/test_contract_examples.py`](../../backend/tests/test_contract_examples.py) | Fails if the examples in `openapi.yaml` and the model's output ever differ. |

Requirements references (F1, F2, Q1, …) point to [`docs/requirements.md`](../requirements.md).

## Endpoint

```
GET /api/products/{barcode}
```

`barcode` is 8 to 14 digits (EAN-8, UPC-A, EAN-13, GTIN-14). Implemented by #14.

## Response states

Each state is distinct, so the client never has to guess what happened.

| Situation | HTTP | Body | What the client does |
|---|---|---|---|
| Found, everything a full analysis needs | 200 | `ProductResult`, `completeness: "complete"` | Show the product and analysis. |
| Found, some required data missing | 200 | `ProductResult`, `completeness: "incomplete"`, `missing_fields` lists it | Show what is there. If nutrition is missing, ask for a Nutrition Facts photo (F1). |
| Barcode malformed | 400 | `error.code: "invalid_barcode"` | Ask for a clearer barcode photo. |
| Not in the product database | 404 | `error.code: "product_not_found"` | Offer the Nutrition Facts photo fallback (F1). |
| Database failed or sent an unusable response | 502 | `error.code: "upstream_unavailable"` | Say the lookup failed and offer a retry. **Do not** say the product was not found. |
| Database did not answer in time | 504 | `error.code: "upstream_timeout"` | Same as 502. Returned within Q2's 10-second limit. |

"Not found" and "failed" are deliberately separate: 404 means the database answered and has no usable record, while 502/504 mean we don't know.

A database record with no name, brand, ingredients or nutrition at all (Open Food Facts has some empty shells) counts as **not found**, not as an incomplete product.

### Nutrition-only result

When barcode lookup fails and the user photographs the Nutrition Facts table, #15 returns a 200 `ProductResult` with `result: "nutrition_only"`. In that result:

- `barcode`, `name`, `brand` and `ingredients_text` are always `null`, because the exact product has not been identified;
- the client labels it **"Nutrition-only result"** and shows ingredients as **"Not available"** (F1);
- `completeness` describes the nutrition only.

## Rules

### Missing data is explicit

- **Every key is always present.** The client never has to check whether a key exists.
- **Missing is `null`.** It is never `0`, `""` or a guessed value. Show it as "Not available".
- `0` is a real value: the source states zero (e.g. "Trans fat 0 g").
- `missing_fields` lists dotted paths into `product` of required data that is missing or uncertain. It is empty exactly when `completeness` is `"complete"`.

### Completeness (from F1)

A `product` result is `complete` when all of these are usable:

| Path in `missing_fields` | Requirement |
|---|---|
| `name` | Product name known |
| `ingredients_text` | Ingredient list known |
| `serving.size_text` | Serving size known |
| `nutrition.basis` | Nutrition is per serving (a per-100 g basis doesn't match the Canadian label) |
| `nutrition.nutrients.<key>` | Each of `calories`, `total_fat`, `saturated_fat`, `sodium`, `carbohydrate`, `sugars`, `fibre`, `protein` |

- `trans_fat` and `cholesterol` are optional. They are shown when present, and their absence never makes a result incomplete.
- An `uncertain` value counts as missing, because it cannot be used.
- A `nutrition_only` result is judged on the serving and nutrition rows only.

Producers do not set `completeness` themselves. The model derives it with `compute_missing_fields()`, so it can't disagree with the data.

### Source and certainty

Every value says where it came from, so the UI can label database values versus label-photo values (F1).

- `source` is either `"open_food_facts"` or `"nutrition_label_photo"`. It is set:
  - on every nutrient;
  - on `serving`;
  - on `package`;
  - on the record as a whole (`product.source`).
- `serving.source` and `package.source` are `null` exactly when every other value in that object is `null`.
- `product.source.url` links to the public record for a "View source" link. `retrieved_at` and `last_modified_at` are UTC ISO-8601 (`2026-10-08T14:00:00Z`).
- `certainty` is set per nutrient:
  - **`reported`**: from the product database. Database values are always `reported`.
  - **`confident`**: from a label photo, passing Q1's confidence rule.
  - **`uncertain`**: from a label photo, failing Q1's rule. **Do not** explain it (F3) or use it in whole-package totals (F2). Offer "Retake photo".

### Nutrition basis

- `nutrition.basis` is `"serving"`, `"100g"` or `"100ml"`. Every nutrient in one result is on that one basis. **Values from different bases are never mixed** (F1).
- The backend never derives per-serving values from per-100 g values. If Open Food Facts only has per-100 g data, the result is per-100 g and incomplete, and the photo fallback applies.
- `basis` is `null` only when no nutrient is known.
- Units are fixed per nutrient and match the Canadian Nutrition Facts table: `calories` in **kcal**, `sodium` and `cholesterol` in **mg**, everything else in **g**.

### %DV

- `daily_value_percent` is the %DV **printed on the label**.
- Open Food Facts doesn't store it, so it is always `null` for database values.
- #15 fills it from the photo when it is printed.
- A %DV calculated by F3 is a separate, calculated value, and is not carried in this field.

### Package and servings (F2)

- `package.quantity` / `unit` is the net quantity, e.g. 400 g.
- `package.servings_per_package` is set only when a source states it. **The backend never estimates it.** F2 decides whether it can derive servings from the package quantity and serving size, and labels that "Approximate".

## Open Food Facts → model mapping (for #14)

Verified against the live API on 2026-10-08. Use **API v3**: `GET https://world.openfoodfacts.org/api/v3/product/{barcode}?fields=…`. v2 is deprecated, and it answers HTTP 200 for unknown codes.

| Model field | Open Food Facts field(s) | Notes |
|---|---|---|
| `barcode` | `code` | OFF normalizes codes (e.g. strips leading zeros); use the code it returns. |
| `name` | `product_name`, then `product_name_en`, then `product_name_fr` | Blank → `null`. |
| `brand` | `brands` | Blank → `null`. |
| `ingredients_text` | `ingredients_text_en`, then `ingredients_text`, then `ingredients_text_fr` | Often `""` for Canadian products → `null`. |
| `serving.size_text` / `quantity` / `unit` | `serving_size` / `serving_quantity` / `serving_quantity_unit` | |
| `package.quantity_text` / `quantity` / `unit` | `quantity` / `product_quantity` / `product_quantity_unit` | |
| `nutrition.basis` | `serving` if `serving_size` is set and `*_serving` values exist, else `100g`/`100ml` from `nutrition_data_per` | Never mix `*_serving` and `*_100g`. |
| `calories` | `energy-kcal_serving` / `energy-kcal_100g` | kcal |
| `total_fat`, `saturated_fat`, `trans_fat` | `fat_*`, `saturated-fat_*`, `trans-fat_*` | g |
| `sodium`, `cholesterol` | `sodium_*`, `cholesterol_*` | OFF stores **g**: multiply by 1000 for mg. |
| `carbohydrate`, `sugars`, `fibre`, `protein` | `carbohydrates_*`, `sugars_*`, `fiber_*`, `proteins_*` | g |
| `source.url` | `https://world.openfoodfacts.org/product/{code}` | |
| `source.last_modified_at` | `last_modified_t` | Unix seconds → UTC. |

OFF responses observed:

| OFF response | Maps to |
|---|---|
| HTTP 200, `"result": {"id": "product_found"}` | 200 `ProductResult`, or 404 if the record is an empty shell |
| HTTP 404, `"result": {"id": "product_not_found"}` | 404 `product_not_found` |
| HTML "Page temporarily unavailable" (HTTP 503) | 502 `upstream_unavailable` |
| HTTP 429 or other 5xx, or JSON that doesn't parse | 502 `upstream_unavailable` |
| No answer before the timeout | 504 `upstream_timeout` |

Constraints:
- OFF allows **15 product reads per minute per IP**, so #14 should cache found products.
- Every request must send `User-Agent: AppName/Version (ContactEmail)`.

## Review sign-off

#20 is done when the authors of the features that consume or produce this data have approved it. Review by commenting on the pull request, then tick your line:

- [ ] #13 barcode detection
- [ ] #14 Open Food Facts lookup
- [ ] #15 Nutrition Facts OCR
- [ ] #16 vision-model prototype

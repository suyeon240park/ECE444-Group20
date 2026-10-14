# Whole-package nutrition contract (#36)

The per-serving and whole-package nutrition (F2) is calculated by a pure backend
service. It is meant for #43 (product-analysis pipeline) and #41 (results page).
`GET /api/products/{barcode}` still returns its existing product contract. #36 adds
no endpoint.

```python
from app.services.package_nutrition import calculate_package_nutrition

result = calculate_package_nutrition(product, confirmed=user_confirmed_paths).to_dict()
```

The JSON shape is `PackageNutritionResult` in [OpenAPI](openapi.yaml). The client
types are in `client/src/packageNutrition.ts`, and `client/src/components/PackageNutritionTable.tsx`
renders them. Every key is always present.

## Serving multiplier

1. A stated **servings per package** is used as it is (`method: "servings_per_package"`).
2. Otherwise, the multiplier is **net package quantity / serving quantity**, when both are known and in the
   same unit (`method: "package_quantity"`). This result is labelled **"Approximate"**.

`servings` is never rounded in the calculation. The `display_*` fields are the only
rounded values. They round half up:

| Value | Display rounding |
|---|---|
| kcal, mg | whole number |
| g | 0.1 g below 10 g, whole grams from 10 g |
| %DV | whole percent |
| servings | 0.1 |

## When nothing is calculated

`status` is `"not_calculated"`, and `message` is F2's text:
**"Whole-package nutrition could not be calculated from the available serving and package information."**
`reason` gives the cause. The user sees the same message for every reason.

| `reason` | Cause |
|---|---|
| `no_per_serving_nutrition` | Nutrition is per 100 g / 100 mL, or missing. Per-100 g data is never scaled. |
| `no_package_information` | Neither a servings-per-package value nor a package quantity is known. |
| `no_serving_quantity` | The serving has no metric quantity, for example only "2 tbsp". |
| `incompatible_units` | One value is in g and the other in mL. Density is unknown, so the units are not converted. |
| `package_smaller_than_serving` | The package works out to fewer than 0.95 servings, which means the package or serving size is wrong (#28 found such records). |
| `unconfirmed_photo_values` | The calculation needs label-photo values the user has not confirmed yet. |

Per-serving values are still returned in `rows`, so the serving view is never replaced.

## Label-photo values need confirmation (#39)

Any value with source `nutrition_label_photo` is used only after the user confirms it.
`confirmed` takes dotted paths:

- `serving`
- `package.servings_per_package`
- `package.quantity`
- `nutrition.nutrients.<name>`

A confirmed value is used even when its certainty is `uncertain`, because the user has
checked it. Values that would be used once confirmed are listed in
`pending_confirmation`. A nutrient waiting for confirmation has
`whole_package_status: "needs_confirmation"`. Database values never need confirmation.

## %DV

- A whole-package %DV is calculated from the whole-package amount. It never scales a
  printed per-serving %DV. It carries `daily_value_label: "Calculated for whole package"`.
- The Daily Values come from Health Canada's
  [Table of Daily Values](https://www.canada.ca/en/health-canada/services/technical-documents-labelling-requirements/table-daily-values/nutrition-labelling.html)
  for adults and children 4 years of age or older, version 2022-10-20. They are kept in
  `backend/app/services/daily_values.py`, which #37 reuses.
- Calories, carbohydrate and protein have no Daily Value, so they never get a %DV.
- Saturated and trans fat share one Daily Value (20 g). Their %DV appears on
  `saturated_fat`, as on the label, and only when both amounts are known.
  `trans_fat` has no %DV of its own.
- Cholesterol has a Daily Value in the table (300 mg), so it gets a calculated %DV. It
  has no %DV on the printed Canadian label, so the reviewer should confirm this choice.

## Not done here

- **Asking the user for the package size**, as #28 suggested, is not built. It changes
  F2's "Source of package information" rule, so it is raised as a requirements change on
  #2 first.
- **Photo servings per package:** `merge_label_nutrition()` keeps the database package,
  and `build_nutrition_only()` sets no package. So a servings-per-package value read from
  a photo does not reach `Product` yet. #43 has to carry it into `product.package`
  (with source `nutrition_label_photo`) for this service to use it.

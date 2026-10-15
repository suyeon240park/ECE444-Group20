# Nutrient %DV and explanations contract (#37)

A pure backend service shows each nutrient with its per-serving %DV, Health Canada's
5% / 15% reading, and the reviewed explanation from #38 (F3). It is meant for #43
(analysis pipeline) and #41 (results page). #37 adds no endpoint.

```python
from app.services.nutrient_content import load_nutrient_content
from app.services.nutrient_explanations import explain_nutrients

content = load_nutrient_content()  # once, at startup; raises NutrientContentError if broken
result = explain_nutrients(product, content, confirmed=user_confirmed_paths).to_dict()
```

The JSON shape is `NutrientExplanationResult` in [OpenAPI](openapi.yaml). The client
types are in `client/src/nutrientExplanations.ts`, and
`client/src/components/NutrientExplanationList.tsx` renders them.

## Basis

Every amount is shown with `basis_label` ("per serving", "per 100 g" or "per 100 mL"),
so a per-100 g value is never read as a per-serving one. For per-100 g / 100 mL data,
`basis_note` explains that the amounts are not per serving and that no %DV is shown.

## %DV

- A %DV **printed on the label** (photo path) is used as printed (`origin: "label"`).
- Otherwise it is **calculated** from Health Canada's Table of Daily Values for adults
  and children 4+ (version 2022-10-20; the URL and version are in
  `daily_values_reference`). It is labelled **"Calculated"**.
- No %DV is invented. Calories, carbohydrate, protein and trans fat never get one.
  Saturated + trans fat share one %DV on `saturated_fat`, and it is shown only when both
  amounts are verified.
- A %DV is per serving. With per-100 g data, amounts are shown without a %DV.

## A little / a lot

On the displayed (whole-number) per-serving %DV, 5% DV or less is **"a little"** and
15% DV or more is **"a lot"**. Values in between show only the number. The rule is
never applied to the whole-package amounts from #36.

## Missing and unconfirmed values

| `status` | Meaning | Shown |
|---|---|---|
| `verified` | A database value, or a photo value the user confirmed | Amount, %DV, explanation |
| `not_available` | No value | "Not available" |
| `needs_confirmation` | A photo value not yet confirmed (#39) | Amount with the confirmation prompt; no %DV or explanation |

`confirmed` uses the same dotted paths as #36, for example `nutrition.nutrients.sodium`.

## Explanations

`what_it_is` and `how_to_read` each carry their text and source links. The row shows
**"No verified explanation available yet."** (`explanation_message`) when:

- the #38 content has not been reviewed (`reviewed_on` is `null`); or
- that nutrient has neither text; or
- the value is not verified.

A nutrient may have only one of the two texts. Cholesterol currently has a
`how_to_read` but no `what_it_is`, because no approved source explains dietary
cholesterol; only the sourced text is shown.

`guidance` (`limit`, `get_more`, `neutral`) says whether Health Canada suggests getting
less or more of a nutrient. The result has no overall score or good/bad verdict.

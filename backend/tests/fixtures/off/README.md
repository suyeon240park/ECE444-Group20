# Open Food Facts response fixtures

Used by the lookup tests. Files marked *real* are unedited v3 responses captured on
2026-10-08 with the `fields` list in `app/services/open_food_facts.py` (re-formatted
as indented JSON); the others are written by hand.

| File | Kind | Why it is here |
|---|---|---|
| `ketchup_found.json` | real | Heinz Tomato Ketchup `0013000006408`: per-serving data for every required nutrient, so a complete result. Note `nutrition_data_per` is `"100g"` even though serving values exist. |
| `nutella_found.json` | real | `3017624010701`: per-100 g data only, no `serving_size`, no fibre, so an incomplete result. |
| `kraft_no_ingredients.json` | real | `0068100058925`: identity and package size, empty `ingredients_text`, no nutrition. |
| `not_found.json` | real | v3 answer (HTTP 404) for an unknown barcode. |
| `empty_record.json` | synthetic | A record that exists but holds only its code. OFF returned one of these on 2026-10-08, but it has since been filled in, so this is a stand-in. |

Open Food Facts is edited by the public, so a live product may differ from its fixture today.

# Reviewed nutrient explanations (F3)

Issue #38 supplies the plain-language explanation shown next to each nutrient.
#37 displays it. Everything is in `nutrients.json`, and
`app/services/nutrient_content.py` loads and validates it.

## Shape

| Field | Rule |
|---|---|
| `schema_version` | `1` |
| `reviewed_on`, `reviewed_by` | Date and GitHub username of the reviewer who checked the content for accuracy. Both `null` until review. While they are `null`, #37 shows "No verified explanation available yet." for every nutrient. |
| `glossary.daily_value_percent` | The inline definition of %DV: `{term, text, source_ids}` |
| `sources` | `{id, publisher, title, url, published_on, accessed_on}`. HTTPS on a host in `../ingredients/source-policy.json`. |
| `nutrients` | One entry for each nutrient in `ALL_NUTRIENTS`, no more and no fewer |

Each nutrient has:

| Field | Rule |
|---|---|
| `id` | The model's nutrient key, for example `saturated_fat` |
| `name` | Display name |
| `guidance` | `limit`, `get_more` or `neutral`, as Health Canada describes the nutrient. `neutral` is used when no source says to get less or more. |
| `what_it_is` | `{text, source_ids}`: what the nutrient is or does |
| `how_to_read` | `{text, source_ids}`: how to read its amount and %DV |

A text is `null` when no approved source supports it yet. #37 then shows "No verified explanation available yet." Never write an unsourced text to fill the gap.

## Writing rules

- Keep each text to two or three short sentences, in plain language.
- Every claim must be supported by a page in its `source_ids`.
- No good/bad verdicts and no overall score. Say "a nutrient you may want to limit" or "more of", as Health Canada does.
- Daily Values quoted in `how_to_read` must match Health Canada's Table of Daily Values (2022-10-20). `tests/test_nutrient_content.py` checks them.

## Open points for review

- **Cholesterol has no text.** None of the approved pages checked explains dietary cholesterol. Health Canada's fats pages don't mention it, and the label example shows it without a %DV. It needs an approved source before a text is written.
- **The fibre page and the Daily Values table disagree.** Health Canada's Fibre page (2025-07-11) says the fibre %DV uses a reference of 25 g. The Table of Daily Values (2022-10-20) gives 28 g. The text follows the table, which is the reference F3 requires.
- **Health Canada's list of nutrients to limit** names sodium, sugars and saturated fat. Trans fat is marked `limit` because the fats page advises choosing unsaturated fats instead of saturated and trans fats.

# Issue #33: 500 real Open Food Facts ingredient records

**Conclusion: the parser runs on all 500 records without crashing, but has
confirmed ingredient-loss and segmentation defects. Do not treat this run as a
passing real-world accuracy benchmark or as evidence that #33 is ready to merge.**

This expands the [earlier 30-record investigation](issue33-off-field-check.md).
The new run adds frozen inputs, offline checks and evidence; it does not modify
the runtime parser or production knowledge base. The previously implemented
tomato-description and null-coverage fixes remain in place.

## Data and scope

- Retrieved six Open Food Facts search pages on 2026-10-13, from 23:25:04 to
  23:27:23 UTC. Examined 513 distinct records; excluded 13 with missing ingredient
  text; retained **500 distinct barcodes with nonblank ingredient text**.
- Selected Canada-tagged products in returned API page order, independent of
  parser results. Requested `sort_by=code`, but the server did not return lexical
  barcode order. This is a convenience sample, not a randomized or representative
  sample of Canadian groceries. Different barcodes can share a formulation.
- Source `lang` metadata: 306 English, 166 French, 28 other. This is product
  metadata, not verified language identification of the selected text. Imported
  foods and supplements are included. Canada tags do not verify current packages.
- Used the actual `normalize_off_product` field-selection logic and
  `IngredientAnalysisService`. The fixed 21-entry synthetic fixture KB exercises
  matching; the empty production KB was run separately. No aliases or reviewed
  content were added to increase matches. Synthetic flags are not health advice.
- OFF ingredient text is community-maintained and sometimes contains OCR errors,
  placeholders, missing delimiters or marketing copy. Nonblank does not mean a
  trustworthy ingredient list. OFF's computed ingredient tree is useful for
  triage but is another parser's output, **not ground truth**.

The [frozen source records](../../backend/tests/fixtures/ingredients/off_canada_500.json)
include request URLs, retrieval timestamps, selected fields, exclusions and
[Open Food Facts attribution/licensing](https://world.openfoodfacts.org/terms-of-use).
The [collector](../../backend/scripts/collect_ingredient_sample.py) uses the
[documented search API](https://openfoodfacts.github.io/openfoodfacts-server/api/),
caches responses, spaces requests and retries transient server failures.

## Checks actually performed

| Check | Tested | Failures |
|---|---:|---:|
| Original real records through normalization and analysis | 500 | 0 exceptions |
| Count consistency, flag references, unique canonical matches, coverage presence | 500 | 0 |
| Uppercasing preserves normalized analysis | 500 | 0 |
| Outer whitespace preserves normalized analysis | 500 | 0 |
| Repeating the list under another `Ingredients:` heading preserves deduplicated analysis | 500 | 1 |
| Appending a separate allergen advisory preserves ingredient analysis | 477 | 2 |
| Independent reference for a restricted comma-only grammar | 142 | 0 |
| Targeted assertions selected after inspecting source text and outputs | 15 | 10 |

The allergen check excludes 23 strings with unbalanced brackets, because a
malformed group can absorb the appended sentence. It compares normalized
matched IDs, unknown text, totals, flags and status. Warning wording/counts and
source occurrences are not part of these behavioral comparisons.

The independent reference only splits simple comma-delimited lists without
groups, conjunctions, advisory markers, percentages or other complex syntax.
It does not call the production splitter, but uses the same fixed KB and name
normalization. Thus 142 passes establish agreement for that restricted grammar,
not correct interpretation of every product. Initially 14 reference comparisons
flagged surrounding punctuation differences; inspection showed these were
harness false positives. Candidate comparisons now apply the documented name
normalization to both sides. No runtime code changed to obtain those passes.

Fifty original records produced warnings. Triage signals identified 32 records
whose OFF computed tree was much larger, 24 with certain nutrient parentheses,
seven with possible packaging prose and two with standalone conjunctions.
These overlapping signals are not defect counts. Absence of a warning does not
establish correct parsing.

The [15 targeted audits](../../backend/tests/fixtures/ingredients/off_canada_500_audit.json)
assert particular required/forbidden candidates and, where unambiguous, counts
and known matched IDs. They were authored by the coding agent after triage,
not by a blinded human annotator. They are partial checks, not exhaustive
annotations. Five ketchup records pass their full candidate/count assertions;
ten other records fail the selected structural assertions below. **Neither
5/15 nor 490/500 is an accuracy estimate.** Untested semantics can still be wrong.

## Confirmed failures in original source strings

| Defect | Records confirmed | Concrete effect |
|---|---:|---|
| Ingredient beginning `gluten-free` mistaken for an advisory | 5 | Drops oats or oat flour; at top level can discard all subsequent ingredients |
| `Contains 2% or less of` / `contains less than 2% of` mistaken for an allergen statement | 3 | Drops actual minor ingredients, including known fixture matches |
| Leading `and/or` split into bogus candidates | 2 | Emits `and` and `or soybean oil`; fails to match soybean oil and soy lecithin |

Traceable examples and complete affected barcode sets:

- **ALMOND FRUIT CRUNCH, `0677210091472`:** after `Coconut, Gluten free oats,
  Corn meal, Pumpkin seeds, ...`, the parser drops the oats and remaining real
  ingredients. Later malformed advisory text also becomes candidates. Other
  affected records: `0626027811025`, `0626027814026`, `0626027841022`,
  `0686207006153`. In the three oat drinks, nested oats/oat flour disappears
  while ingredients outside the group survive.
- **BARISTA EDITION OATMILK, `0190646640019`:** retains four candidates before
  `Contains 2% or less of:` and loses all nine ingredients after it. The count
  should be 13 under the current parent-plus-components policy. **Rice Pudding,
  `0073491510006`:** three instead of six; eggs, salt and natural flavor vanish.
  **PITA Sea Salt, `0030100784586`:** yeast, whey and soy lecithin vanish. The
  latter two records demonstrate missing known salt/soy-lecithin matches, not
  merely incomplete production content.
- **Tortilla Style Protein Chips, `0888849006656`:** both `and/or soybean oil`
  and `and/or soy lecithin` become malformed candidates. **Omega 3,
  `0196633965301`:** `and/or mackerel` becomes `and` and `or mackerel`.

The five passing tomato-description cases are `0057000002992`, `0057000012861`,
`0057000013165`, `0056200926466`, `0057000243760`. Phrases such as `from fresh,
ripe tomatoes` and `made from fresh ripe tomatoes` do not create extra candidates.

## Three failures exposed by transformed inputs

1. **Sauce Marinara, `0747479005470`: confirmed sentence-boundary defect.** The
   original list ends in `Oregano` and yields eight candidates. Appending
   `. Contains: milk, soy, peanuts.` increases the count to ten and produces
   `Oregano. Contains: milk` as an unknown. The abbreviation guard checks whether
   a preceding string *ends with* `no`; it accidentally treats `Oregano.` as
   `No.`. This is a synthetic transformation of a real list, not a claim that
   the original OFF record contained that allergen notice.
2. **Merenda, `7622201126131`: contaminated-input robustness failure.** The
   source contains a prose preamble, an embedded ingredient heading, and other
   packaging text. Repeating the full field under a new heading changes the
   preamble interpretation and increases the count from 21 to 23. This is not
   proof of a clean-list deduplication defect; the transformation's assumption
   is weaker for mixed prose than for a genuine list.
3. **Mesa Sunrise with Raisins, `0058449771616`: malformed-input robustness
   failure.** The field contains an ingredient heading inside a parenthetical.
   Although globally balanced, splitting at the heading creates broken spans.
   An appended allergen notice becomes part of an unknown span. Both runs have
   warnings. This exposes degraded-input behavior, not a validated ingredient
   count for the original field.

The complete original text, candidates, unknowns, warnings, failed transformed
inputs and actual results are in [the machine-readable report](issue33-off-500-results.json).

## Implications for this PR

Unit tests preserve known behavior; real records discover missing cases. This
run shows why both are necessary: the existing regression suite can pass while
normal labels lose ingredients. Convert confirmed real examples into focused
regressions before implementing these bounded #33 fixes:

1. Separate standalone dietary claims from actual ingredient names beginning
   `gluten-free`; do not discard following items merely because of that prefix.
2. Recognize quantitative ingredient introductions before applying allergen
   exclusion. Keep genuine `Contains:` / `May contain:` exclusion intact.
3. Handle conjunctions at list-item starts without inventing `and`/`or` names;
   retain existing compound-name, slash and oil-context behavior.
4. Match abbreviation tokens at word boundaries so `Oregano.` ends a sentence.

The earlier 30-record variety-pack failure also remains unresolved. Nutrient
synonyms, origin annotations, mixed-language unknown deduplication and corrupted
source text need explicit policy/content decisions; do not guess aliases or
claim semantic correctness from a no-crash check. These data do not justify
silently changing the agreed compound counting policy.

Structural parsing fixes and these tests fit #33. Reviewed ingredient content,
scientific explanations and source-backed flags remain #34/#35. HTTP integration
and UI rendering remain #43/#40. The empty production KB matches zero ingredients;
this run cannot establish production coverage or real health-flag correctness.

## Reproduce offline

From `backend/`:

```powershell
.venv/Scripts/python.exe -m scripts.validate_ingredient_corpus --output .label-results/off-500-replay.json
```

This executes all 500 frozen records plus transformations and targeted audits,
without network calls. The command currently exits **1**, correctly reporting
the unresolved failures. It is separate from the ordinary pytest suite; keeping
that suite green must not hide the failing real-data evaluation.

Verification after adding the corpus and harness: **518 pytest tests passed,
two live tests deselected, 99.32% coverage**; Ruff lint and format checks passed;
the production content validator accepted zero reviewed entries. Snapshot checks
confirmed 500 distinct Canada-tagged records, 13 documented exclusions and zero
production matches for all 500. The exploratory command separately exited 1
with the failures reported above.

To collect a fresh sample explicitly (network required):

```powershell
.venv/Scripts/python.exe -m scripts.collect_ingredient_sample --count 500 --cache .label-results/off-fresh-pages --output .label-results/off-fresh-500.json
```

Fresh API results can change. Use the checked-in snapshot to reproduce this
report; the targeted barcode assertions apply to that snapshot. A fresh corpus
needs its own audited cases, passed with `--audits PATH`.

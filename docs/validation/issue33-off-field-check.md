# Issue #33: exploratory check on 30 real product records

On 2026-10-13, the current ingredient engine was exercised against all 30
barcodes from [the issue #28 retailer-selected sample](https://github.com/suyeon240park/ECE444-Group20/issues/28#issuecomment-6090889655).
The six categories are cereal, chips, soup, pasta, yogurt and juice. The sample
was selected before this parser evaluation, not chosen to produce passing cases.

**Result: real data exposes additional problems. The small regression suite and
high code coverage do not establish reliable ingredient counts on this sample.**

## Method and limits

- Fetched the live Open Food Facts v3 records, six seconds apart, between
  23:10:16 and 23:13:13 UTC on 2026-10-13. Kept all records, including missing data
  and the 404 response. The API request restricted fields to identity and
  ingredients; this was not a repeat nutrition-completeness evaluation.
- Passed found records through the actual `normalize_off_product` and
  `IngredientAnalysisService`, including English/default/French fallback.
- Used the existing synthetic fixture KB for matcher diagnostics and the actual
  empty production KB separately. No content entries or aliases were added to
  improve the score. Synthetic flags were not evaluated as real health claims.
- Authored expectations from the raw text before the first parser run on this
  sample. Eighteen records have selected checks; some check names and counts,
  others only warning presence. These are agent-authored expectations, awaiting
  teammate review, not package-verified human ground truth. One expectation's
  display/lookup distinction for ascorbic acid was corrected after the run;
  the affected record still fails on the independently identified conjunction bug.
- OFF text is community-maintained. Correct parsing cannot prove correspondence
  to a current physical package. For example, the Quaker sample is labelled Honey
  Almond by the retailer but Original in OFF. Missing commas and marketing copy
  in ingredient fields are source-data problems, not evidence of real ingredients.

Frozen [API records](../../backend/tests/fixtures/ingredients/off_sample_issue28.json),
[expectations](../../backend/tests/fixtures/ingredients/off_sample_expectations.json),
and [complete machine-readable results](issue33-off-results.json) preserve the
inputs, selected checks, failures, actual candidates and warnings. OFF data is
attributed to Open Food Facts under the ODbL, as recorded in the snapshot.

## Results

| Measure | Result |
|---|---:|
| Barcodes attempted | 30 |
| Products found | 29 |
| Found products with nonblank ingredient text | 21 |
| Found products with no ingredient text | 8 |
| Products not found | 1 |
| Records with selected expectations | 18 |
| Records satisfying all their selected checks | 12 |
| Records failing at least one selected check | 6 |
| Records with explicit expected canonical-match lists | 13 |
| Canonical-match list mismatches on those 13 records | 0 |
| Count/coverage serialization invariant failures | 0 |
| Production KB entries | 0 |

**12/18 is not a parsing accuracy rate.** Four of the twelve records only passed
a warning-presence check, and unscored records can still have bad segmentation.
The 13 matching-list checks test a limited synthetic vocabulary, not production
coverage or clinical/scientific correctness. No production coverage target is
claimed: the empty production KB matches no ingredients.

All eight missing-list records correctly return `unavailable` and null coverage
text. The missing product never enters ingredient analysis. No runtime exceptions
occurred in the 29 found-record analyses.

## Failures and what they mean

| Product / barcode | Observed result | Expected or concern | Classification |
|---|---|---|---|
| Selection Orange Burst / `059749998130` | 8 candidates, including `and` and `or concentrated grape juice` | 7 under the documented counting rule; leading `and/or` continues the ingredient alternatives | Concrete parser defect for #33 |
| iOGO variety pack / `629025410009` | 13 unique candidates; only the first flavour's list survives | 18 named ingredients across the four lists; raspberries, strawberries, anthocyanins, paprika and locust bean gum disappear | Concrete parser defect for #33 |
| Cheerios Multi Grain / `065633132832` | 22 unique candidates | 19 under a semantic interpretation; vitamin B3/B5/B6 parentheticals repeat preceding nutrient descriptions | Annotation/equivalence policy and content-dependent counting limitation |
| Cream of Wheat / `072400011597` | 5 candidates | 4 under a semantic interpretation; `orthophosphate ferrique (fer)` is split into two | Nutrient-description policy limitation; do not equate all iron compounds as aliases |
| Lay's Classic / `060410047019` | 4 unique candidates | Three ingredients repeated in English and French; the two potato names lack stored aliases | Known bilingual-content dependency; reviewed aliases belong in #34/#35 |
| Allen's apple juice / `056412503011` | `Checked 0 of 1`, one long unknown and no warning | Input is marketing copy, not a trustworthy ingredient list | Source-quality detection/presentation limitation |

The iOGO failure comes from the advisory boundary: after `Made with vitamin D
fortified skim milk.,` the remaining flavour text is treated as part of the
advisory and discarded. A regression should preserve later ingredient sequences
without promoting the milk advisory itself into an ingredient.

For Orange Burst, the slash in leading `and/or` is processed as a delimiter.
Handle conjunction prefixes at a list-item boundary without breaking real
chemical names, slash-separated alternatives, or the existing embedded oil rule.

Source contamination can remain even when a warning exists. Selection chicken
and rice soup returns 43 candidates, including cooking instructions and address
fragments, with two `ambiguous_group` warnings. Activia returns 59 candidates
including marketing text, with one such warning. Their minimal warning checks
pass; **their ingredient totals are not validated**. Lipton's source has broken
comma boundaries; Astro's source appears to omit a comma. Those records were
exercised but have no complete segmentation expectation in this study. Barilla
also contains nutrient-description parentheticals and was not separately scored.

## Scope and next steps

Testing on real records, retaining failures, fixing structural parser defects,
and documenting ambiguous input are within #33's parsing/matching/result scope.
The Orange Burst and iOGO defects should get focused regression tests and fixes
before claiming this parser handles those real lists correctly.

Decide how nutrient-description parentheses and untrustworthy ingredient fields
affect the displayed denominator. Do not fix those by deleting every vitamin or
guessing ingredient identities. Human review of the expectations and counting
policy is still needed. Adding reviewed production explanations, sources, flags
and bilingual aliases remains #34/#35; UI/pipeline behavior remains #40/#43.

This study has not changed runtime parsing or loaded production content. It
records failures rather than changing expectations to make the current parser
pass. It does not replace the future representative, package-verified benchmark.

## Reproduce offline

From `backend/`:

```powershell
.venv/Scripts/python.exe -m scripts.check_ingredient_dataset --output .label-results/ingredient-field-check/results.json
```

The command reads the frozen records, runs normalization and both knowledge-base
configurations, writes detailed results, and exits **1** when selected checks
fail. The current frozen evaluation intentionally fails on six records. It is a
separate exploratory command, not a claim that the ordinary pytest suite covers
these failures. No network access is required to reproduce it.

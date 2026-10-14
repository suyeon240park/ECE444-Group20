# Issue #33: exploratory check on 30 real product records

This independently selected sample comes from
[issue #28](https://github.com/suyeon240park/ECE444-Group20/issues/28#issuecomment-6090889655)
and covers cereal, chips, soup, pasta, yogurt and juice. Live OFF responses were
frozen on 2026-10-13 between 23:10:16 and 23:13:13 UTC, including missing data.
The [snapshot](../../backend/tests/fixtures/ingredients/off_sample_issue28.json)
retains URLs, retrieval times, original names and OFF attribution/licensing.

The real normalizer and service use the unchanged synthetic KB and, separately,
the empty production KB. Expected checks for 18 records were authored from raw
text before the first run; they await teammate verification against packages.
They are partial checks, not an accuracy benchmark. A display/lookup distinction
in the Orange Burst expectation was corrected after the initial run; the actual
conjunction defect remained failing until the parser fix.

## Updated results

| Measure | Result |
|---|---:|
| Barcodes attempted | 30 |
| Products found | 29 |
| Nonblank ingredient text | 21 |
| Found records missing ingredient text | 8 |
| Selected audits | 18 |
| Audits passing before / after fixes | 12 / 14 |
| Audits failing before / after fixes | 6 / 4 |
| Explicit canonical-match lists checked | 13 |
| Canonical-match mismatches | 0 |
| Count/serialization invariant failures | 0 |
| Production entries | 0 |

All eight missing-list records correctly return unavailable with null coverage.
No analysis exceptions occurred. Warning-only checks do not validate ingredient
segmentation, and 14/18 is not an accuracy estimate.

## Fixed and remaining cases

- **Fixed: Selection Orange Burst, `059749998130`.** Leading `and/or` no longer
  creates fake connector names. The documented seven-candidate expectation passes.
- **Fixed: iOGO variety pack, `629025410009`.** The parser now recognizes the
  sentence boundary in `Made with vitamin D fortified skim milk.,` and retains
  later flavours. The total is 18 rather than 13. A normal pytest regression
  checks the count and the previously missing raspberries, strawberries,
  anthocyanins, paprika and locust bean gum.
- **Remaining: Cheerios, `065633132832`.** Returns 22 rather than the semantic
  expectation of 19; nutrient parentheticals name the same nutrients twice.
- **Remaining: Cream of Wheat, `072400011597`.** Returns five rather than four;
  `(fer)` describes the nutrient supplied by the preceding iron compound.
- **Remaining: Lay's Classic, `060410047019`.** Four unknown/matched candidates
  rather than three physical ingredients; English and French potato descriptions
  lack a reviewed alias. Unknown translations are not inferred.
- **Remaining: Allen's apple juice, `056412503011`.** Marketing text is treated
  as one unknown without a warning. Reliable classification of contaminated
  source text is not established by the current parser.

Other source problems remain: Selection soup and Activia contain cooking,
address or marketing prose even when warnings are emitted. Lipton has broken
comma boundaries, Astro appears to omit a comma, and Barilla has nutrient
parentheticals. These rows have no complete validated segmentation. The Quaker
retailer name also differs from the OFF product name. Correct parsing alone
cannot verify the physical product.

## Reproduce offline

From `backend/`:

```powershell
.venv/Scripts/python.exe -m scripts.check_ingredient_dataset --output .label-results/ingredient-field-check/results.json
```

The generated report contains selected expectations, actual names, counts and
warnings. It is kept outside Git. The command still exits 1 on four unchanged
semantic/source-quality expectations; they were not weakened to make it pass.
The two confirmed structural defects are repaired, and their regressions are
covered by normal pytest. Reviewed aliases and content remain #34/#35. These
exploratory inputs do not replace the representative, human-verified benchmark.

See also the [500-record evaluation](issue33-off-500-field-check.md).

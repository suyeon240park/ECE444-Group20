# Issue #33: 500 real Open Food Facts ingredient records

The confirmed structural defects are fixed: all 15 targeted real-label audits
now pass, including the ten that originally failed. The original Marinara
advisory transformation also passes. These regressions run under ordinary pytest
and therefore in CI. This does not establish an overall parsing accuracy rate.

## Source and reproducibility

On 2026-10-13, six Open Food Facts search pages were collected between 23:25:04
and 23:27:23 UTC. Of 513 distinct records examined, 13 had missing ingredient
text; the snapshot retains 500 distinct barcodes with nonblank selected text.
Selection followed returned API page order, independent of parser outcomes.
`sort_by=code` was requested but the server did not return lexical barcode order.
Canada tags do not verify a current Canadian package. Different barcodes can
share formulations. This is a convenience sample, not a representative survey.

The [snapshot](../../backend/tests/fixtures/ingredients/off_canada_500.json)
retains request URLs, retrieval times, exclusions, original English/default/French
ingredient fields, and identity/country/language metadata. Unused API fields and
numeric metadata in OFF's computed ingredient tree were removed; its text and
children remain for diagnostics. This reduces the fixture from 2.9 MB to 0.97 MB
without changing the evaluated ingredient text. Attribution and the ODbL link
are retained. Source `lang` metadata is English for 306, French for 166, and
other languages for 28; this is not a verified classification of selected text.

The real normalizer and analysis service run with the unchanged 21-entry
synthetic test KB and separately with the empty production KB. No aliases,
health claims or production entries were added to improve these results.
OFF's computed ingredient tree is another parser's output, never ground truth.

## Before and after

| Check | Tested | Before failures | After failures |
|---|---:|---:|---:|
| Original records through normalization and analysis | 500 | 0 exceptions | 0 exceptions |
| Count, flag-reference, match-uniqueness and coverage invariants | 500 | 0 | 0 |
| Uppercasing preserves normalized analysis | 500 | 0 | 0 |
| Outer whitespace preserves normalized analysis | 500 | 0 | 0 |
| Repeat the field under another ingredient heading | 500 | 1 | 1 |
| Append a separate allergen advisory | 477 | 2 | 1 |
| Independent reference for restricted comma-only grammar | 142 | 0 | 0 |
| Targeted source-text audits | 15 | 10 | 0 |

The advisory check excludes 23 records with unbalanced brackets. Transformation
checks compare normalized names, IDs, totals, flags and status, not occurrence
paths or warning counts. The independent reference uses comma-only splitting
with no production splitting helper; it still shares the KB and normalizer.
Fourteen initial reference alerts were punctuation comparison errors in the
harness, corrected before this baseline. No runtime fix was made for them.

The [audit assertions](../../backend/tests/fixtures/ingredients/off_canada_500_audit.json)
were authored by the coding agent after triage, from the frozen source text.
They are partial assertions, not blind or package-verified human annotations.
Neither 15/15 nor the absence of exceptions is an overall accuracy estimate.

## Fixed defects

- Five records lost ingredients beginning `gluten-free`. Standalone dietary
  claims are now distinguished from ingredient names, preserving oats/oat flour
  and following ingredients. Barcodes: `0677210091472`, `0626027811025`,
  `0626027814026`, `0626027841022`, `0686207006153`.
- Three records lost ingredients introduced by `Contains 2% or less of` or
  `contains less than 2% of`. These quantitative introductions now precede
  allergen filtering. Barcodes: `0190646640019`, `0030100784586`, `0073491510006`.
  Oatmilk now counts 13 rather than four; rice pudding six rather than three.
  The existing salt and soy-lecithin entries are no longer missed in those cases.
- Leading `and/or` now preserves soybean oil, soy lecithin and mackerel instead
  of emitting `and` and `or ...`. Barcodes: `0888849006656`, `0196633965301`.
- The abbreviation check now recognizes whole `No`/`Vit` tokens. Appending an
  advisory after `Oregano.` in Marinara (`0747479005470`) preserves its eight
  candidates. Existing `FD&C Red No. 3` handling is covered by regression tests.
- A period followed by a comma ends a sentence. This also repairs the earlier
  iOGO variety-pack record (`629025410009`), preserving ingredients in later
  flavours. See the [30-record report](issue33-off-field-check.md).

The five ketchup description checks continue to pass: `0057000002992`,
`0057000012861`, `0057000013165`, `0056200926466`, `0057000243760`.

## Remaining exploratory limitations

Two transformation checks remain failing and visible:

1. Merenda (`7622201126131`) mixes a prose preamble, an embedded ingredient
   heading and packaging text. Repeating the entire field changes preamble
   interpretation and its count from 21 to 23. The assumption that the entire
   field is an ingredient list is not established for this source.
2. Mesa Sunrise with Raisins (`0058449771616`) contains a heading inside a
   parenthesis. Splitting at that heading creates malformed spans; an appended
   advisory joins an unknown span. Both runs contain warnings. Its original
   ingredient count is not validated.

The 500-record command therefore still exits 1. These cases have not been
removed or rewritten into passing expectations. Fifty original records produce
warnings. Nutrient equivalence, origin annotations, unknown translations and
corrupted packaging prose still limit semantic counts. Production matches are
zero because reviewed content remains in #34/#35. HTTP and UI integration remain
in #43/#40. This check does not validate health claims or physical labels.

## Replay and CI

From `backend/`:

```powershell
.venv/Scripts/python.exe -m scripts.validate_ingredient_corpus --output .label-results/off-500-replay.json
.venv/Scripts/python.exe -m pytest tests/test_ingredient_corpus_regressions.py --no-cov -q
```

The first command exercises all 500 records and writes complete actual inputs,
outputs, warnings and failure details to an ignored local report. Generated
reports are not checked in. The second enforces the 15 audited real records,
variety-pack and Marinara cases, and focused boundary regressions in normal CI.
The broader exploratory assertions remain stricter than the established input
contract and are reported separately rather than silently relaxed.

Validation after the fixes: 549 backend tests passed, two live tests deselected,
99.33% coverage; Ruff lint/format passed; production content validation accepted
zero entries. Source text and expectations still need teammate review.

To fetch a new sample explicitly (network required):

```powershell
.venv/Scripts/python.exe -m scripts.collect_ingredient_sample --count 500 --cache .label-results/off-fresh-pages --output .label-results/off-fresh-500.json
```

API results may change. Reproduce this report with the checked-in snapshot;
a fresh corpus needs its own audit cases passed with `--audits PATH`.

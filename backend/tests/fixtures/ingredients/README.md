# Ingredient fixtures

`entries.json` contains **synthetic test content**, not reviewed food guidance.
The source URLs are placeholders on allowed hosts. Statements, flags, and dates
exist to exercise validation and must never be copied into production content.

Production content lives in `backend/content/ingredients/entries/`; its loader
never reads this directory. Issues #34 and #35 supply reviewed entries.

The parser scenarios in `test_ingredient_analysis.py` are hand-authored expected
cases informed by Canadian ingredient-list structures and the #28 investigation.
They are not a measured 30-product benchmark. A frozen, manually annotated
30-product corpus and content coverage reports belong to #34/#35.

## Real-label regression inputs (#33)

`real_labels.json` freezes ingredient text from five Canadian-market products
(Heinz Zero, Ritz Original, partly skimmed milk, Robin Hood flour, Kraft Only
Peanuts), plus an existing missing-ingredients OFF response. English and French
ketchup sections are separate cases. Each case has a source, access date,
transcription notes, explicit expected candidates, matched IDs, unknowns, and Y.
Photo dates are not inferred: `accessed_on` records when the existing photo was
inspected. Web pages can change; tests use only the frozen text, never live calls.
The flour text came from the indexed retailer page; direct access returned 403.

Inputs and expectations were authored by the coding agent from the referenced
sources, independently of running the parser. **They are not yet verified by a
teammate.** A reviewer should compare each transcription and expected name with
its source and confirm the parent-plus-components counting rule. Do not mark
human review complete merely because the tests pass. These fixtures do not alter
the Q1 Nutrition Facts ground truth or add ingredient OCR to the application.
Photo transcriptions are injected as database text only to exercise the service.

Run from `backend/`:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_ingredient_real_labels.py tests/test_ingredient_analysis.py tests/test_ingredient_contract.py --no-cov -q
```

Assertions compare names as well as counts, so a dropped ingredient cannot be
masked by an invented replacement. The milk case records the existing unknown
translation limitation: `Vitamin` and `Vitamine`, like the other untranslated
pairs, remain separate unknown candidates. Six unmatched candidates do not mean
six distinct physical ingredients. Known bilingual aliases have separate unit
tests; reviewed content in #34/#35 must supply any new aliases.

The engine still uses `entries.json`'s **synthetic** explanations and flags for
these tests. In particular, the flour's ascorbic-acid match is not evidence for a
real-world flag. Product labels and retailer pages are provenance for ingredient
names only, never sources for health-related claims. Production `entries/` stays
empty. This small regression set is not the 30-product benchmark, a measurement
of production coverage, or a reviewed food-safety assessment.

## Exploratory issue #28 sample

`off_sample_issue28.json` freezes the live OFF identity/ingredient responses for
all 30 barcodes in the independently selected issue #28 sample. Provenance,
request URLs, retrieval times, original sample names, and OFF licensing are
included. Missing products and missing ingredient fields remain in the sample.

`off_sample_expectations.json` contains agent-authored checks for 18 records,
including deliberately failing semantic-count and input-quality checks. It is
not a package-verified human benchmark. Do not update these expectations from
parser output to make them pass. See the
[field-check report](../../../../docs/validation/issue33-off-field-check.md)
for the six failing records, limited warning-only checks, and scope decisions.

Run `python -m scripts.check_ingredient_dataset --output PATH` from `backend/`
to replay the frozen sample offline. The exploratory command exits 1 on selected
check failures, separately from the ordinary regression suite. Production
content and health claims remain outside this study.

## 500-record exploratory Canada-tagged sample

`off_canada_500.json` freezes 500 distinct OFF records with nonblank selected
ingredient text. Selection follows API page order, independent of parser output;
513 distinct records were examined and 13 missing-list records excluded. Canada
tags and source text have not been checked against physical packages.

`off_canada_500_audit.json` contains 15 targeted source-text checks authored after
triage, not complete human annotations or a blind accuracy benchmark. Ten fail
on dropped ingredients or malformed conjunctions; five ketchup checks pass.
The offline harness also runs behavioral transformations on all eligible records
and an independent reference restricted to simple comma-only lists.

Run `python -m scripts.validate_ingredient_corpus --output PATH` from `backend/`.
It currently exits 1 on the unresolved failures. See the
[500-record report](../../../../docs/validation/issue33-off-500-field-check.md)
for results, limitations and exact reproduction steps. No synthetic explanations,
flags or new aliases were promoted into production content.

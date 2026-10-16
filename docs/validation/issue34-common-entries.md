# Common-ingredient production replay (#34)

Date: 2026-10-14. Base: merged #33, `3fd058a`. Content: 25 common entries.
Author research and test expectations are agent-authored. **Alex's source and
wording review is pending and required before merge.** See the
[selection and evidence matrix](../../backend/content/ingredients/evidence-common.md).

## What this validates

The production loader checks schema, required fields, source references, dates,
approved hosts, identifiers and alias collisions. The production tests specify
expected IDs independently of the content files, covering English/French
deduplication, mixed known/unknown text, the real bilingual Lay's record, and
source/processing/grade distinctions. Future #35 entries can coexist.

The existing offline scripts now record production matched IDs, unknown strings,
X/Y, coverage text and warnings per product. Their summaries count each ID once
per product and separate unavailable data from warning types. Synthetic-fixture
expectations, snapshots, parser code, counting policy and API are unchanged.
Reported counts are observations of this parser and content, not manual truth.

## Results

| Observation | Frozen #28 sample | Frozen Canada-tagged sample |
| --- | ---: | ---: |
| Records | 30 | 500 distinct barcodes |
| Found records with selected nonblank ingredient text | 21 | 500 |
| Found records missing ingredient text | 8 | 0 (excluded during original collection) |
| Not-found records | 1 | 0 |
| Products with at least one production match | 19 | 328 |
| Sum of per-product checked counts | 69 | 906 |
| Sum of per-product total candidate counts | 270 | 5,318 |
| Sum of per-product unknown counts | 201 | 4,412 |
| Products with production warnings | 4 | 50 |
| Production count/coverage invariant failures | 0 | 0 |

These sums are not unique ingredients across the dataset, ingredient quantities,
or accuracy scores. Y includes named parents and components, and may include
unrecognized duplicate translations or source prose. No coverage threshold is
claimed. The 500-record collection originally excluded 13 missing-list records
from 513 examined; the 30-record study retains missing data instead.

Production warning breakdown (products per code):

| Warning | 30 records | 500 records |
| --- | ---: | ---: |
| `unbalanced_brackets` | 1 | 24 |
| `ambiguous_group` | 3 | 16 |
| `ambiguous_oil_component` | 0 | 9 |
| `ignored_preamble` | 0 | 1 |

Warnings are triage signals, not a complete count of bad inputs or parser bugs.
Malformed/contaminated text can also lack warnings. Missing text is a separate
`unavailable` state, with no coverage claim.

Lay's `060410047019` matches exactly `potatoes`, `vegetable_oil`, `salt`: **3 of 3**,
no unknowns or warnings. Its English and French potato names resolve to the same
ID. This verifies the frozen OFF text, not a fresh inspection of the package.

## Historical failures remain visible

Both exploratory commands still exit **1** because their historical synthetic
checks intentionally retain unresolved cases. Do not interpret those exits as
a production schema failure, and do not rewrite expectations to hide them.

- **30 records:** 14 of 18 selected rows pass; 4 retain failures. Cheerios
  `065633132832` and Cream of Wheat `072400011597` double-count unreviewed nutrient
  synonyms in parentheses. Lay's retains its synthetic-KB potato deduplication
  failure while the new production test passes. Allen's `056412503011` contains
  packaging prose and is still treated as one unknown without a warning.
  All 13 selected canonical-match checks pass; zero invariant failures.
- **500 records:** zero exceptions or invariant failures; 15/15 targeted audits
  and 142/142 restricted comma-list reference checks pass. Uppercase and outer
  whitespace checks pass on all 500. Repeat-list testing fails on Merenda
  `7622201126131` (mixed prose/preamble); appended-advisory testing fails on Mesa
  Sunrise `0058449771616` (an ingredient heading inside parentheses). These
  transformation checks still use the synthetic KB, not production content.

The 500 records contain multiple source languages despite their Canada tags;
only English explanations and explicit English/French aliases are supplied.
Unknowns include valid ingredients outside this 25-entry scope, qualified forms
deliberately kept separate, unsupported languages, and malformed source strings.
Unmatched does not mean unsafe. No flagged matches does not establish safety.

Historical #33 reports remain unchanged:
[30-record study](issue33-off-field-check.md) and
[500-record study](issue33-off-500-field-check.md).

## Checks and reproduction

Local verification: **613 passed, 2 live tests deselected**, app coverage 99.33%;
Ruff lint and format checks pass; content CLI validates 25 entries. Client
TypeScript checking and Expo web export pass. Local Python is 3.14.8; repository
CI independently runs Python 3.12 and the client jobs. Coverage is code coverage,
not ingredient or evidence accuracy.

From `backend/` with development dependencies installed:

```text
python -m scripts.validate_ingredients
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m scripts.check_ingredient_dataset --output .label-results/issue34-30.json
python -m scripts.validate_ingredient_corpus --output .label-results/issue34-500.json
```

From `client/`, run `npm ci`, `npm run typecheck`, and `npm run build:web`, as CI
does. The local run reused installed dependencies. On Windows, a workspace-local
pytest `--basetemp` and `COVERAGE_FILE` may be needed in a restricted environment.

Generated JSON, coverage data, build output and temporary test directories stay
outside Git. The frozen inputs, independent assertions, source-backed entries,
and this concise summary are the reproducible review artifacts.

## Merge gate and integration

Alex must review source relevance, wording, dates and aliases before merge.
The additional exact source host `mdpi-res.com` supports one individually
researched pasta paper; it does not add a flagging authority. No teammate
approval is recorded automatically. There is no database migration, runtime
network dependency, personalized allergen feature or health score. #35 remains
responsible for flag-focused content; #40/#43 supply UI/API integration.

# Reviewed ingredient content (F4)

Issue #33 supplies the format, validation, and matching engine. Issue #34 adds
25 sourced common-ingredient entries to `entries/`. See the
[evidence matrix](evidence-common.md) for selection, aliases, source sections,
and review status. Alex's source and wording review is required before merge
and remains pending; passing validation does not complete that review.
An empty collection remains valid and checks zero ingredients, without proving
a product safe. Authority assessments and flag-focused content belong to #35.

## Add an entry

Add `entries/<canonical_id>.json` containing an object with exactly two fields:
`schema_version: 1` and `ingredient`. Use the `IngredientContentDocument` and
`IngredientEntry` schemas in [OpenAPI](../../../docs/api/openapi.yaml).
Every property is required. Use `null` for absent dates/flags and `[]` for absent
aliases, identifiers, or authority positions. No field may be silently omitted.

The `ingredient` object has:

| Field | Authoring rule |
| --- | --- |
| `id` | Stable lowercase snake_case ID; never repurpose an existing ID |
| `name` | English display/common name |
| `aliases` | Explicit synonymous English/French names; preserve accents |
| `e_numbers` | Explicit identifiers such as `E171`, `E160b`, `E150(i)` |
| `ins_numbers` | Explicit identifiers such as `INS 171`; not inferred from E-numbers |
| `what_it_is`, `why_used`, `explanation` | Each is `{text, source_ids}` with non-blank text and at least one source |
| `sources` | `{id, publisher, title, url, published_on, accessed_on}` records |
| `last_reviewed` | Date the content was actually reviewed, `YYYY-MM-DD` |
| `authority_positions` | `{id, authority, statement, scope, source_ids, assessed_on, effective_on}` records |
| `flag` | `null` or `{flag_reason, category, source_ids, position_ids}` |

`flag != null` means flagged; there is no second flag-status field to contradict it.
Dates without evidence remain `null` where the schema allows it. Publication,
assessment, review, and effective dates have different meanings. A future effective
date must not be described as an already-effective prohibition.

For #34, `last_reviewed` records the author's content/evidence check; it does not
record Alex's approval. Source access and author review occurred on 2026-10-14.
Publication dates are null unless explicitly supported by the source; they are
not inferred from a page's modification date.
An empty `authority_positions` array records no authority position and is not an
affirmative safety assessment. `flag: null` carries no universal safety verdict.

Keep explanations concise and neutral. What it is and why it is used should fit
within three sentences together. Each substantive claim must be supported by the
cited page. `source_ids` and `position_ids` refer only to records in that entry.

Names are exact after Unicode normalization, case folding, whitespace collapse,
and surrounding punctuation removal. Accents are not removed. Add genuinely
equivalent unaccented spellings explicitly when reviewed. Aliases and identifiers
cannot resolve to different entries, including across languages.

Do not add an entire compound ingredient list as an alias to bypass parsing.
Specific compounds, sources, or grades are not interchangeable: E322 does not
prove soy origin, generic caramel does not identify a caramel class, and generic
sulphites do not identify a particular salt. Broader entries need broader wording.

## Evidence and flagging policy

Flagging authorities are `health_canada`, `efsa`, `fda`, and `who_jecfa`.
Each position must cite a source hosted by that authority. Explain the relevant
food use, population, or preparation condition in `scope`; do not infer whether
an individual shopper belongs to that population.

The two flag categories are:

- `authority_action`: a formal food-safety warning, safety-specific restriction,
  prohibition, or withdrawal concerning the relevant food use.
- `conflicting_assessments`: materially conflicting current safety assessments
  by at least two distinct recognized authorities. Store and cite each separately.

Routine permitted-use limits or acceptable daily intakes alone do not warrant a
flag. Technical-sounding names do not warrant a flag. A hazard classification and
an exposure-based risk assessment are not automatically contradictory. Prefer
`conflicting_assessments` when disagreement is the primary reason; retain other
relevant positions as well. The human reviewer decides evidence relevance and
material disagreement; structural validation cannot establish scientific truth.

A flag must have a non-empty reason, category, directly supporting source IDs,
and supporting position IDs. Flag sources must occur in those positions. A
disagreement flag requires two distinct authorities, not two pages from one.

Non-flag explanations may cite Health Canada, Canada's Food Guide, CFIA for
terminology, EFSA, FDA, WHO/JECFA, or individually reviewed papers. The exact
HTTPS source hosts are in `source-policy.json`; subdomains are not implicitly
approved. Add a new host through the same reviewed PR as the source. Adding a
host does not add a flagging authority. Peer-reviewed sources can support general
explanations, but cannot substitute for an authority's own position.

For #35, record the four-authority search/review matrix in the content PR. A
missing position means no relevant position was located, not an affirmative
finding of safety. Reviewers must check the linked evidence, currentness, scope,
synonyms, and wording. Check live links during review; CI does not call them.

## Validate and use

From `backend/`:

```text
python -m scripts.validate_ingredients
pytest
ruff check .
ruff format --check .
```

`--directory PATH` validates an alternate directory with its own `entries/` and
`source-policy.json`. Validation fails on missing directories/files, invalid JSON,
duplicate JSON keys, unsupported schema versions, malformed entries, collisions,
bad evidence references, and incomplete flags. Errors include filenames/fields.
An existing, empty `entries/` directory is valid.

The application loads validated immutable content once per service construction.
File changes become active on restart/redeployment, not through runtime fetches.
Deploy the backend's `content/` directory with its code. No database, secrets, or
external service is required. Revert and redeploy to roll back content.

See [the service contract](../../../docs/api/ingredient-analysis.md) for wiring,
coverage semantics, parser limits, and the #40/#43 integration boundary.

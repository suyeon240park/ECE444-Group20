# Ingredient analysis contract (#33)

This is a reusable backend service and response contract for #40 and #43.
`GET /api/products/{barcode}` still returns its existing product contract.
No ingredient HTTP endpoint or UI is introduced by #33.

```python
from app.services.ingredient_knowledge import load_ingredient_knowledge
from app.services.ingredient_analysis import IngredientAnalysisService

# Construct once when #43 wires its analysis services.
ingredients = IngredientAnalysisService(load_ingredient_knowledge())
result = ingredients.analyze(product).to_dict()
```

The default content path is relative to the backend package, not the process's
working directory. The loader raises `IngredientKnowledgeError` for broken
content/configuration. #43 should surface ingredient analysis as unavailable on
that failure while preserving independent nutrition results; it must not convert
the error to a successful zero-match analysis. #33 does not wire the loader into
Flask startup, so it cannot break existing lookup/health routes.

## Input and result

Input is the existing `Product`. Only `open_food_facts` provenance with non-blank
`ingredients_text` is analyzed. The existing normalizer chooses English, generic,
then French. Nutrition-photo input always returns `unavailable`, even if someone
passes ingredient text alongside that source. Ingredient-list OCR is out of scope.

Use `IngredientAnalysisResult` in [OpenAPI](openapi.yaml) and the corresponding
types in `client/src/ingredients.ts`. Every response key is present. Arrays are
empty when there are no items; absent flags, messages, and dates use `null`.

| Status | Meaning and message |
| --- | --- |
| `unavailable` | No eligible list. `Ingredient information not available`; counts zero |
| `no_matches` | Text is present but nothing was checked. `No verified ingredient analysis available.` |
| `analyzed` | At least one match. Without flags: `No flagged ingredients found among the ingredients checked.` Otherwise `message` is null and flags supply reasons |

`matched` contains full entry details and original occurrences. `unmatched`
contains the first spelling and all occurrences of each unknown candidate.
An occurrence's `path` is its zero-based section/token/nesting traversal path,
not an offset into the input. Annotation-only parentheses stay in the occurrence
text. Compound parents and components have separate occurrences.

`flagged_ids` references matched entries, in first-appearance order. It contains
every flag, including more than three; #40 owns the collapsed three-item view.
`flagged_count` is its length. Render each authority position separately with its
scope, source, and dates. Do not infer a universal safe/unsafe verdict.

## Coverage

- X (`checked_count`) is the number of unique canonical matched IDs.
- Y (`total_count`) is X plus the number of distinct normalized unmatched candidates.
- Recognized bilingual/synonymous forms count once. Unknown translations are not
  guessed to be equivalent; only identical normalized unknown text is deduplicated.
- The supplied `coverage_text` reads `Checked X of Y ingredients against our
  reviewed ingredient database.` Keep it visible with flags/no-flags messages
  when non-null. It is `null` for `unavailable`, and also when no ingredient
  candidates can be recovered (Y = 0). Never substitute a "Checked 0 of 0"
  message. A genuine list with zero matches still shows "Checked 0 of Y".
- Named compound ingredients and named components both count. Functional/group
  headings such as `Sugars (...)` and `colour (...)` do not add an ingredient.
  For example, `Shortening (vegetable oil, modified palm oil)` counts three
  candidates. A later repeated `vegetable oil` does not add a fourth. This is
  the existing #33 counting policy, not a count of only top-level label items;
  reviewers should explicitly confirm this implementation counting policy.
- For `Sugar, corn syrup, modified corn starch, colour (titanium dioxide), carnauba
  wax`, a database containing the first four produces 4 of 5, not 4 of 6.
- Preserve warnings alongside coverage: on malformed input, Y describes the
  candidates that could be segmented, not a verified count of the printed label.
- Show unknowns under `Not in our database yet`. Neither unknown nor unflagged
  means safe. If no candidates can be recovered, use `no_matches`, not unavailable.
  Keep the `no_ingredient_candidates` warning and the no-verified-analysis message,
  with null coverage text.

## Parsing and limits

Matching uses complete names, reviewed aliases, E-numbers, and explicitly stored
INS numbers. Normalization uses NFKC, case folding, surrounding punctuation and
whitespace. It preserves accents and internal punctuation/identifier suffixes.
There is no substring/fuzzy matching, translation, stemming, or runtime AI.

Parsing supports comma/semicolon/bullet/newline separators, sentence boundaries,
balanced nested parentheses/brackets, explicit ingredient headings, and declared
alternatives. Known complete aliases take precedence over splitting. Chemical
numeric locants are protected. Trailing ingredient percentages and an explicit
list of purpose annotations do not add ingredients; leading qualifiers such as
`2% milk` remain meaningful. Unknown E/INS suffixes remain unmatched identifiers.

Whole source descriptions in the bounded `_SOURCE_ANNOTATIONS` list (for example,
`from fresh, ripe tomatoes`, `from concentrate`, and the ketchup label's French
`faite de tomates mûres et fraîches`) annotate the parent. They are recognized
before commas or conjunctions split children. Original label text stays in the
occurrence. This is deliberately not a rule that deletes every child beginning
with `from` or `made with`: a composition such as `chocolate (made with sugar,
milk)` retains its components. Unrecognized source/composition introductions are
stripped inside components and their remaining names stay subject to ordinary
exact matching; arbitrary prose is not guaranteed to be understood.

`vegetable oil (corn, canola and/or soybean)` uses a narrow oil-component table;
`corn` in that context is looked up as `corn oil`. Named oil mixtures still count
their parent and individual declared components. Unknown oil components stay
unmatched rather than matching unrelated foods. No arbitrary adjective removal
or contextual chemical inference is performed.

Standalone `Contains:` / `May contain` / `Contient:` / `Peut contenir` statements
and recognized packaging claims are excluded. Embedded `grape juice (contains
sulphites)` includes sulphites. Explicit bilingual headings create separate
sections; a malformed earlier section does not consume the next one.

Warning codes are `unbalanced_brackets`, `ambiguous_group`,
`ambiguous_oil_component`, `ignored_preamble`, `no_ingredient_candidates`,
`nesting_limit`, and `text_limit`. Unsupported syntax remains unmatched. Lists
over 50,000 characters or 32 bracket levels return one unmatched span with a
warning; they are not truncated into verified-looking matches.

This is a conservative parser, not a general grammar or damaged-OCR repair tool.
For example, missing commas, unlabeled multi-variety prose, inferred oil sources,
and unreviewed synonyms may reduce coverage. Record such cases for later review;
do not change names or suppress unknowns merely to raise a benchmark score.

## Examples and review

[ingredient-examples.json](ingredient-examples.json) provides synthetic fixtures
for unavailable, zero matches, no flags, partial coverage, authority disagreement,
multiple flags, and malformed text. They are generated from test-only entries,
contain no reviewed health advice, and are never loaded in production. Contract
tests compare their complete JSON to the service and validate against OpenAPI.

Production entries and a real 30-product coverage benchmark arrive in #34/#35.
See [the authoring guide](../../backend/content/ingredients/README.md) for content
fields, source policy, review requirements, and the offline validator.

The smaller [real-label regression set](../../backend/tests/fixtures/ingredients/real_labels.json)
contains source-traceable text from five Canadian-market products plus a missing
OFF record. Tests assert ordered candidate names, canonical matches, unknowns,
and coverage against expectations authored independently of parser output. They
run offline with the synthetic database and do not measure production coverage
or validate health claims. The transcriptions and counting decisions await a
teammate's verification; see the [fixture review instructions](../../backend/tests/fixtures/ingredients/README.md).

The milk fixture explicitly preserves a known limitation: unknown English and
French names are not translated or deduplicated by inference. Its three printed
ingredients yield six unmatched candidates until reviewed aliases are supplied.
Do not describe this as six distinct physical ingredients or a passed bilingual
semantic-deduplication benchmark. Known aliases are tested separately.

# Issue #33 PR description and review notes

## Suggested PR description

Implements the reusable ingredient knowledge-base loader, bounded label parser,
exact alias/E-number/INS matching, and F4 result contract. Source and authority
references are validated before loading. Matched ingredients retain source
occurrences; unknowns, warnings, flags, and coverage are returned explicitly.

Fixes descriptive parentheses being counted as ingredients: Heinz Zero's
`from fresh, ripe tomatoes` annotates tomato paste, so its English label produces
seven candidates rather than nine. Missing ingredient data returns null coverage
text. Text containing only advisories also omits coverage, retaining the
no-verified-analysis message and parsing warning.

Adds frozen, source-traceable regression inputs for five Canadian-market
products and a missing OFF record. Candidate names, matched IDs, unknowns, and
counts are compared with independently authored expectations. These cases use
synthetic test entries; the transcriptions and expectations await teammate
verification. They do not establish production coverage or health-claim accuracy.

Production ingredient content and the representative 30-product benchmark remain
in #34/#35. API integration remains in #43 and UI rendering in #40. Production
`entries/` is intentionally empty; no synthetic fixture content is loaded there.

Validation on 2026-10-13: 518 backend tests passed (2 live tests deselected),
99.32% backend coverage, Ruff lint/format checks passed, TypeScript type checking
and the Expo web build passed, and `validate_ingredients` accepted the empty production
database. Source transcriptions and policy approval remain human review tasks.

A subsequent [30-record exploratory OFF check](validation/issue33-off-field-check.md)
found six records failing selected expectations, including two concrete parser
defects (leading `and/or` and concatenated variety-pack lists). These failures
remain recorded and unresolved; the 518 passing regression tests do not cover
them. This evidence should accompany review rather than presenting #33 as fully
validated on real datasets.

An additional [500-record Canada-tagged OFF evaluation](validation/issue33-off-500-field-check.md)
ran all records through the real normalizer and service. No exceptions occurred,
but targeted source-text checks expose ingredient loss or malformed conjunctions
in ten original records. An appended-advisory check also exposes an `Oregano.`
sentence-boundary bug; two other transformed-input failures involve contaminated
source fields. These defects remain unresolved. Five real ketchup records pass
the existing descriptive-parenthesis fix. The frozen corpus, explicit assertions
and offline command are included; the command exits 1 on the known failures.
This is broader robustness testing within #33, not a production-content or
health-accuracy benchmark.

## Explicit requirements review

This PR changes `docs/requirements.md`: it clarifies F4's operative authorities,
safety-specific flag criteria, review of material disagreement, source scope and
dates, JSON content storage, exact alias matching, and coverage/deduplication.
The parser counts named compound parents and their named components; functional
group headings do not count. Please explicitly confirm this policy rather than
interpreting Y as only the number of top-level items on the package.

The contribution process also requires documenting the clarification on story
#9, updating its description, and obtaining the story reviewer's confirmation.
This file prepares that material; it does not claim those GitHub actions or
reviewer approval have happened.

Suggested story clarification:

> For #33, retain the four authorities specified in F4. A flag requires a
> safety-specific action/formal warning or a material disagreement reviewed by a
> person; routine permitted-use limits and ADIs alone do not trigger a flag.
> Preserve food/population scope and dates. Use reviewed JSON entries and exact
> aliases/E/INS identifiers. Count named compound parents and components, omit
> functional headings and recognized descriptive annotations, and deduplicate
> canonical matches and identical normalized unknowns. Unknown translations are
> not inferred. Omit coverage text when ingredients are unavailable or no
> candidates can be recovered. Reviewed content and the coverage benchmark follow
> in #34/#35.

## Reviewer checks

- Compare the frozen ingredient text and expected names with each linked source.
- Confirm the compound counting policy and the unknown-translation limitation
  demonstrated by the milk fixture (six candidates, three physical ingredients).
- Review English/French descriptions and confirm genuine components still match.
- Confirm #40 renders coverage only when non-null, with warnings retained.
- Record story-reviewer confirmation of the F4 clarification through the process
  in `CONTRIBUTING.md`; automated tests cannot supply human approval.

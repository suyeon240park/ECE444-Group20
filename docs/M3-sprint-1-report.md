# Milestone 3.1 — First Sprint: Task Planning and Estimation

**ECE444 Software Engineering · Project 1: Web Application Development**
**Team Nexus (Group 20) · What's in My Food?**
**Members:** Suyeon Park, Frank Liu, Eyad Ahmed, Alex An
**Submitted:** [date]

> DRAFT, state as of October 8. Filled in by everyone in the team's shared Google Doc, using this file's format. Items in [square brackets] must be filled in before submission; each member fills in their own two tables in Section 3. Then export the Google Doc to PDF, submit it on Quercus under "Milestone 3.1 - First Sprint - Task Planning" (due October 9), and add the PDF to `docs/` through a pull request.

---

## 1. Work backlog (2 pts)

**Project-management tool:** GitHub Projects, with GitHub Issues for stories and tasks and GitHub Pull Requests for code review.

- Board: https://github.com/users/suyeon240park/projects/2
- Issues: https://github.com/suyeon240park/ECE444-Group20/issues
- Requirements document: https://github.com/suyeon240park/ECE444-Group20/blob/main/docs/requirements.md

How the backlog is organised:

- Every selected user story from Milestone 2 is an issue labelled `candidate-story` plus `functional` or `quality`. The seven selected stories are #10 (F1), #2 (F2), #3 (F3), #9 (F4), #4 (Q1), #5 (Q2) and #11 (Q3).
- Each story is broken into implementation issues that link back to the story and to its section of `docs/requirements.md`.
- The board has a **Priority** field (High / Medium / Low, taken from the requirements document) and a **Sprint** field (Sprint 1 / Sprint 2 / Backlog). Stories are sorted by priority; tasks sit under their story's sprint.
- Tasks move through Todo → In Progress → Done.

**Screenshot of the sorted backlog:**

[Insert screenshot here. Take it from the board's table view: filter `label:candidate-story`, show the Priority and Sprint columns, sort by Priority descending. Alternatively a board-layout screenshot grouped by Sprint.]

---

## 2. Sprint 1 summary and Sprint 2 plan (5 pts)

### 2.1 Sprint overview

The team plans three sprints:

| Sprint | Dates | Goal |
|---|---|---|
| 1 | October 5 – [end; the team aimed to finish sprint-1 tasks by October 8] | Foundation and product retrieval: a deployed skeleton where a user can submit a product image, detect its barcode, retrieve normalised Open Food Facts data, and get sensible complete / partial / not-found states. |
| 2 | [start] – [end] | Core product functionality: whole-package nutrition, nutrient explanations, ingredient analysis, and one integrated results page. |
| 3 | [start] – [end] | Quality validation and release: performance, usability, end-to-end tests, defect fixes, final deployment. |

### 2.2 Sprint 1 summary

**Goal.** Build the foundation so that every later feature has something to run on, and prove the primary data path (barcode → Open Food Facts) works before investing in the fallback.

**Decisions made during the sprint**

- **Three sprints**, with the breakdown above, agreed on October 5.
- **Tech stack:** React Native with Expo (TypeScript) for one client codebase covering web, iOS and Android; Python with Flask for the backend; PostgreSQL; Open Food Facts as the product-data source; GitHub Actions for CI.
- **Photo fallback:** the OCR-library approach was dropped. Nutrition Facts extraction from a photo will be prototyped with a vision-model API instead (#16, which originally described OCR), time-boxed to 5 hours. The team decides at the end of sprint 1, using the Open Food Facts lookup results (#14), the coverage check and the prototype result, whether the photo fallback stays in scope. If it is deferred, requirement Q1 is revised through the normal review process. The OCR benchmark (#17) and the accuracy check (#18) wait for that decision. The prototype result (October 8): `gemini-3.5-flash` read all 166 printed fields on 10 test photos correctly, in about 7 seconds per photo, on Google's free tier; the recommendation posted in #16 is to keep the photo fallback, with user confirmation of photo values and the 50-photo benchmark (#17) as conditions.
- **Product API contract:** the client–backend contract for `GET /api/products/{barcode}` was agreed in #20 (PR #25), so the barcode, lookup and photo tasks can be built in parallel against one response shape. Missing data is always `null`, never zero or a guess, and "not found" is kept separate from "lookup failed".
- **Sprint 2 assignment:** owners for sprint 2 tasks are assigned after sprint 1 closes (agreed October 7), once it is clear what carries over.
- **Process:** tasks are tracked on GitHub Projects instead of the Jira named in the original workflow document. README, CONTRIBUTING and Code of Conduct were added to the repository. A repository ruleset (added October 6, limited to `main` on October 8) requires a pull request with one approval and resolved review conversations before merging.

**Sprint 1 tasks and status** (as of October 8; owners update their rows before submission)

| Issue | Task | Owner | Est. hours | Status |
|---|---|---|---|---|
| #19 | Set up project skeleton, CI pipeline and development environment | Frank | 6–8 | Done (PR #24, merged October 8) |
| #23 | Add README, CONTRIBUTING, Code of Conduct and project-management links | Frank | 3–5 | Done (PR #21, merged October 6) |
| #16 | Prototype Nutrition Facts extraction with a vision-model API (time-boxed) | Frank | 5 | In review: PR #27 opened October 8; results and recommendation posted in #16 |
| #22 | Set up staging deployment and environment configuration | Frank | 5–8 | Not started; unblocked since #19 merged, needs a hosting choice [update] |
| #20 | Define product data model and client–backend API contract | Suyeon | 4–6 | Done (PR #25, merged October 8) |
| #14 | Integrate Open Food Facts product lookup | Suyeon | 6–8 | In review: PR #26 opened October 8 [update] |
| #13 | Implement product image upload and barcode detection | Eyad | 6–10 | Not started as of October 8 [update] |
| — | Validate Open Food Facts coverage and field completeness for Canadian products (no issue created yet) | Alex | 5–8 | Not started [update] |
| #15 | Database completeness and fallback routing (complete / incomplete / missing results) | Alex | 5–8 | Not started; depends on #14 [update] |

**What was delivered**

- Repository documents: README with a project-management section, CONTRIBUTING, Code of Conduct (PR #21).
- Project skeleton (PR #24, merged October 8): Flask backend with a health endpoint and tests, Expo client for web, iOS and Android whose home screen calls the backend, CI running lint, tests, typecheck and a web build on every pull request, Docker Compose for a local PostgreSQL, fixtures folder for the Q1 benchmark, setup instructions for web and phone (Expo Go). Review feedback fixed before merge: comma-separated CORS origins, npm lockfile regenerated against the official registry.
- Product data model and client–backend API contract (PR #25, merged October 8): `GET /api/products/{barcode}` with distinct states for found, incomplete, invalid barcode, not found, upstream failure and timeout; OpenAPI spec; Python model with tests that keep the spec and the model in sync; Open Food Facts field mapping verified against the live API.
- Vision-model label extraction prototype (PR #27, in review): a photo of a Nutrition Facts table goes to Google's Gemini API and comes back in the contract's field names, with unreadable values left empty rather than guessed. A benchmark script scores it against hand-transcribed labels under Q1's rules. First 10 benchmark photos and their ground truth added (the start of #17's 50-photo set). Result: `gemini-3.5-flash` 100% (166/166 fields), 6.9 s mean, free tier ($0.017 per photo on the paid tier); the smaller `gemini-3.5-flash-lite` scored 98.2% and misread a sodium %DV.
- Backlog: all seven selected stories and the sprint-1 tasks on the board, with Priority and Sprint fields and owners.
- [Suyeon: #14 outcome]
- [Eyad: #13 outcome]
- [Alex: coverage result, #15 outcome]

**What did not go as planned** [team: edit and add your own]

- **The work was more sequential than the plan suggested.** #13, #14 and #15 all depended on the skeleton (#19), which merged on October 8, so the dependent tasks had about one day of sprint 1 left. Next time the skeleton should land in the first two days, and dependent work should start against mocks.
- **Review caught two real defects before merge.** The CORS setting ignored comma-separated origin lists, and the npm lockfile pointed at a personal mirror registry from one member's global npm configuration. Both were fixed in PR #24; the client now pins the official registry in `client/.npmrc`.
- **Issue numbers were planned before the issues existed.** The planning table used predicted numbers that collided with pull requests (#21, #24, #25), and one extra issue had to be repurposed. Issues are now created first and referenced by their real numbers.
- **The coverage check was planned but never created as an issue**, so it has not started and the photo-fallback decision lacks its data.
- **Expo Go now requires an Expo account** on both the computer and the phone, which added setup steps for phone testing. The steps are in `client/README.md`.
- **The repository ruleset first applied to every branch**, so nobody could push follow-up commits to their own working branch and merges waited on a code-scanning check that was never set up. It was limited to `main` on October 8.
- **Vision-model availability changed under us.** The planned `gemini-2.5-flash` is closed to new API keys, and the newest `gemini-3.8-flash` failed every request (overloaded, then out of free quota). The prototype uses `gemini-3.5-flash`; the model name is a setting, so a later switch is a configuration change plus one benchmark run.
- **Midterms during the sprint** reduced available hours for some members.

**Open questions carried into sprint 2** (from `docs/requirements.md`)

- Open Food Facts coverage for Canadian products: not yet measured (coverage check not started). Findings from #20 so far: Open Food Facts often has an empty `ingredients_text` for Canadian products, and it allows 15 product reads per minute per IP, so #14 needs caching.
- Where net package quantity comes from when the database lacks it.
- Hosting and budget for the staging deployment. (Vision-model API: answered by #16. The free tier is enough for development and user testing; the paid tier would cost about $0.017 per photo.)
- Whether uploaded photos are stored. Related: on the free tier, Google may use the photos sent to the API to improve its products, which the app should state.
- Photo-path additions to the #20 contract raised in review: a certainty flag on serving size and servings per package (Q1's critical fields), and a "confirmed by user" state for vision-model values.

### 2.3 Sprint 2 plan

**Goal.** Turn retrieved product data into the user-facing product: whole-package nutrition (F2), nutrient explanations (F3), ingredient analysis (F4), and one integrated results page. The three features are independent once sprint 1 provides normalised product data, so they can be built in parallel.

**Planned tasks** (issues to be created at sprint 2 planning; estimates from the planning table of October 5; owners assigned after sprint 1 closes)

| Task | Story | Part | Est. hours | Depends on | Owner |
|---|---|---|---|---|---|
| Implement whole-package nutrition calculations and display | #2 | Backend + frontend | 8–12 | — | [ ] |
| Implement nutrient %DV interpretation and explanation logic | #3 | Backend + frontend | 8–12 | — | [ ] |
| Build reviewed nutrient explanation / content repository | #3 | Content / data | 6–10 | — | [ ] |
| Implement ingredient knowledge-base schema, parsing and matching | #9 | Backend / data | 10–14 | — | [ ] |
| Seed reviewed ingredient knowledge-base entries | #9 | Data / research | 10–16 | KB schema | [ ] |
| Implement ingredient summary and ingredient-detail UI | #9 | Frontend | 6–10 | — | [ ] |
| Integrate product-analysis orchestration pipeline | #10, #2, #3, #9 | Backend / integration | 10–14 | the three features above | [ ] |
| Build integrated product analysis / results page | #2, #3, #9 | Frontend / full-stack | 10–14 | ingredient UI, orchestration | [ ] |
| Implement loading, partial-data, empty and error states | #10, #2, #3, #9 | Frontend | 5–8 | results page | [ ] |
| Add automated tests for nutrition and ingredient features | #2, #3, #9 | Testing | 8–12 | orchestration, results page | [ ] |
| Decision: keep or defer the photo fallback; if deferred, revise Q1 and update `docs/requirements.md` | #4, #10 | Requirements | 2 | #16 (done), coverage check | Frank |

Likely carried over from sprint 1 (confirm when sprint 1 closes): #13 image upload and barcode detection, #15 completeness and fallback routing, #22 staging deployment, the coverage check, and #14 if not finished. [update]

If the team keeps the photo fallback, sprint 2 also needs: the 50-photo benchmark with a second teammate checking the ground truth (#17), a photo endpoint that uses the #16 extraction, and a screen where the user confirms photo values before they are used (Q1's safe-use rule). The automated accuracy check in CI (#18) can stay in sprint 3.

**Risks for sprint 2**

- **Carry-over.** Several sprint-1 tasks move into sprint 2 and will compete with the planned features. The barcode → lookup path (#13, #14, #15) has to finish first, since every sprint-2 feature consumes its data.
- **The ingredient knowledge base** is the largest and least predictable piece of work (two tasks, 20–30 hours combined). It should start on day one of the sprint.
- **Late integration.** The orchestration pipeline and the results page depend on all three features, so integration problems will surface late. Mitigation: build the results page early against the example responses in the #20 contract.
- **Open Food Facts rate limit** of 15 product reads per minute per IP. Product caching must be in place before user testing.
- If the photo fallback is deferred, Q1 needs a replacement quality requirement to keep three in scope.

---

## 3. Individual task tables

Each member: one table for sprint 1 with estimated and actual hours, one for sprint 2 with estimated hours. Estimates are the numbers recorded before starting, one number per task (replace the ranges copied from the planning table); actuals are the real time spent, including coordination and review. For a task not finished in sprint 1, give the hours spent so far and mark it "in progress". Shared duties (code review, meetings) are listed as in the handout's example.

### 3.1 Liu's tasks

**Sprint 1**

| Task | Estimated time (hours) | Actual time (hours) |
|---|---|---|
| #19 Set up project skeleton, CI pipeline and development environment (including review fixes) | 7 | [ ] |
| #23 Write README, CONTRIBUTING and Code of Conduct * | 4 | [ ] |
| #16 Vision-model Nutrition Facts extraction prototype (time-boxed) | 5 | [ ] |
| #22 Staging deployment and environment configuration | 6 | [ ] |
| Set up and sort the backlog on the project board (stories, priorities, sprints) | 2 | [ ] |
| Draft this sprint report | 2 | [ ] |
| Review team-member pull requests timely and thoroughly (PR #25) | 2 | [ ] |
| Participate actively in common team duties (meetings, planning, Discord coordination) | 2 | [ ] |

\* The documents were written on October 4, before the sprint-planning estimates existed; this estimate comes from the planning table of October 5.

**Sprint 2**

| Task | Estimated time (hours) | Actual time (hours) |
|---|---|---|
| [Sprint 2 task, e.g. orchestration pipeline] | [ ] |  |
| [Sprint 2 task, e.g. automated tests for nutrition and ingredient features] | [ ] |  |
| Decide on the photo fallback; revise Q1 and requirements document if deferred | 2 |  |
| Review team-member pull requests timely and thoroughly | 3 |  |
| Participate actively in common team duties | 2 |  |

### 3.2 Park's tasks

**Sprint 1**

| Task | Estimated time (hours) | Actual time (hours) |
|---|---|---|
| #20 Define product data model and client–backend API contract | 4–6 | [ ] |
| #14 Integrate Open Food Facts product lookup | 6–8 | [ ] |
| Sprint planning tables and implementation issue breakdown | [ ] | [ ] |
| Review team-member pull requests timely and thoroughly (PR #21, PR #24) | [ ] | [ ] |
| Participate actively in common team duties | [ ] | [ ] |

**Sprint 2**

| Task | Estimated time (hours) | Actual time (hours) |
|---|---|---|
| [ ] | [ ] |  |
| Review team-member pull requests timely and thoroughly | [ ] |  |
| Participate actively in common team duties | [ ] |  |

### 3.3 Ahmed's tasks

**Sprint 1**

| Task | Estimated time (hours) | Actual time (hours) |
|---|---|---|
| #13 Implement product image upload and barcode detection | 6–10 | [ ] |
| Sprint report (this document) and backlog screenshot | [ ] | [ ] |
| Review team-member pull requests timely and thoroughly | [ ] | [ ] |
| Participate actively in common team duties | [ ] | [ ] |

**Sprint 2**

| Task | Estimated time (hours) | Actual time (hours) |
|---|---|---|
| [ ] | [ ] |  |
| Review team-member pull requests timely and thoroughly | [ ] |  |
| Participate actively in common team duties | [ ] |  |

### 3.4 An's tasks

**Sprint 1**

| Task | Estimated time (hours) | Actual time (hours) |
|---|---|---|
| Validate Open Food Facts coverage and field completeness for Canadian products (no issue yet) | 5–8 | [ ] |
| #15 Database completeness and fallback routing | 5–8 | [ ] |
| Review team-member pull requests timely and thoroughly | [ ] | [ ] |
| Participate actively in common team duties | [ ] | [ ] |

**Sprint 2**

| Task | Estimated time (hours) | Actual time (hours) |
|---|---|---|
| [ ] | [ ] |  |
| Review team-member pull requests timely and thoroughly | [ ] |  |
| Participate actively in common team duties | [ ] |  |

---

## 4. Repository documents (3 pts, graded in the repository)

| Document | Location | Status |
|---|---|---|
| README with project-management tools and links | `README.md` | Done (PR #21) |
| Contributing guide | `CONTRIBUTING.md` | Done (PR #21) |
| Code of Conduct | `CODE_OF_CONDUCT.md` | Done (PR #21) |

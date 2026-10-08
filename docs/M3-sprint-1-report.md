# Milestone 3.1 — First Sprint: Task Planning and Estimation

**ECE444 Software Engineering · Project 1: Web Application Development**
**Team Nexus (Group 20) · What's in My Food?**
**Members:** Suyeon Park, Frank Liu, Eyad Ahmed, Alex An
**Submitted:** [date]

> DRAFT. Items in [square brackets] must be filled in before submission. Each member fills in their own two tables in Section 3. Export to PDF, submit on Quercus under "Milestone 3.1 - First Sprint - Task Planning", and commit the PDF to `docs/`.

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
| 1 | [start] – [end] | Foundation and product retrieval: a deployed skeleton where a user can submit a product image, detect its barcode, retrieve normalised Open Food Facts data, and get sensible complete / partial / not-found states. |
| 2 | [start] – [end] | Core product functionality: whole-package nutrition, nutrient explanations, ingredient analysis, and one integrated results page. |
| 3 | [start] – [end] | Quality validation and release: performance, usability, end-to-end tests, defect fixes, final deployment. |

### 2.2 Sprint 1 summary

**Goal.** Build the foundation so that every later feature has something to run on, and prove the primary data path (barcode → Open Food Facts) works before investing in the fallback.

**Decisions made during the sprint**

- **Three sprints**, with the breakdown above, agreed on October 5.
- **Tech stack:** React Native with Expo (TypeScript) for one client codebase covering web, iOS and Android; Python with Flask for the backend; PostgreSQL; Open Food Facts as the product-data source; GitHub Actions for CI.
- **Photo fallback:** the OCR-library approach was dropped. Nutrition Facts extraction from a photo will be prototyped with a vision-model API instead (#16), time-boxed to 5 hours. The team decides at the end of sprint 1, using the Open Food Facts coverage result (#21) and the prototype result, whether the photo fallback stays in scope. If it is deferred, requirement Q1 is revised through the normal review process.
- **Process:** tasks are tracked on GitHub Projects instead of the Jira named in the original workflow document. README, CONTRIBUTING and Code of Conduct were added to the repository.

**Sprint 1 tasks and status** [update before submission]

| Issue | Task | Owner | Est. hours | Status |
|---|---|---|---|---|
| #19 | Set up project skeleton, CI pipeline and development environment | Frank | 6–8 | Done (PR #24 merged Oct 8) |
| #23 | Add README, CONTRIBUTING, Code of Conduct and project-management links | Frank | 3–5 | Done (PR #21 merged) |
| #16 | Prototype Nutrition Facts extraction with a vision-model API (time-boxed) | Frank | 5 | Not started |
| #22 | Set up staging deployment and environment configuration | Frank | 5–8 | Not started, depends on #19 |
| #20 | Define product data model and client–backend API contract | Suyeon | 4–6 | In review (PR #25 approved by Frank, CI green) [update] |
| #14 | Integrate Open Food Facts product lookup | Suyeon | 6–8 | In progress [update] |
| #13 | Implement product image upload and barcode detection | Eyad | 6–10 | [status] |
| #21 | Validate Open Food Facts coverage and field completeness for Canadian products | Alex | 5–8 | [status] |
| #15 | Handle complete, incomplete and missing product-database results | Alex | 5–8 | [status], depends on #14 |

**What was delivered** [update before submission]

- Repository documents: README with a project-management section, CONTRIBUTING, Code of Conduct (PR #21).
- Project skeleton (PR #24, merged Oct 8): Flask backend with a health endpoint and tests, Expo client whose home screen calls the backend, CI running lint, tests, typecheck and a web build on every pull request, Docker Compose for a local PostgreSQL, fixtures folder for the Q1 benchmark, setup instructions for web and phone.
- Backlog: all seven stories and all sprint-1 tasks on the board with priorities, sprint assignment and owners.
- Product data model and client–backend API contract (PR #25): `GET /api/products/{barcode}` response states, OpenAPI spec, Python model with tests that keep the spec and the model in sync, Open Food Facts field mapping. [Suyeon: update when merged; add #14 outcome]
- [Eyad: #13 outcome]
- [Alex: #21 coverage result, #15 outcome]

**What did not go as planned** [fill in honestly; this is what the estimation exercise is for]

- [e.g. Expo Go now requires an Expo account, which added setup steps for phone testing.]
- [e.g. tasks waited on #19 longer than expected.]

**Open questions carried into sprint 2** (from `docs/requirements.md`)

- Open Food Facts coverage for Canadian products: answered by #21. Result: [fill in].
- Where net package quantity comes from when the database lacks it.
- Hosting and budget for the staging deployment and for the vision-model API.
- Whether uploaded photos are stored.

### 2.3 Sprint 2 plan

**Goal.** Turn retrieved product data into the user-facing product: whole-package nutrition (F2), nutrient explanations (F3), ingredient analysis (F4), and one integrated results page. The three features are independent once sprint 1 provides normalised product data, so they can be built in parallel.

**Planned tasks** (issues to be created at sprint planning; estimates from the planning table of October 5)

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
| Decision: keep or defer the photo fallback; if deferred, revise Q1 and update `docs/requirements.md` | #4, #10 | Requirements | 2 | #16, #21 | Frank |

Carried over from sprint 1 if unfinished: [list].

**Risks for sprint 2**

- The ingredient knowledge base is the largest and least predictable piece of work (two tasks, 20–30 hours combined). It should start on day one of the sprint.
- The orchestration pipeline and the results page depend on all three features, so they land at the end of the sprint; integration problems will surface late. Mitigation: agree the response shape in #20 and build the results page against mock data early.
- If the photo fallback is deferred, Q1 needs a replacement quality requirement to keep three in scope.

---

## 3. Individual task tables

Each member: one table for sprint 1 with estimated and actual hours, one for sprint 2 with estimated hours. Estimates are the numbers recorded before starting; actuals are the real time spent, including coordination and review. Shared duties (code review, meetings) are listed as in the handout's example.

### 3.1 Liu's tasks

**Sprint 1**

| Task | Estimated time (hours) | Actual time (hours) |
|---|---|---|
| #19 Set up project skeleton, CI pipeline and development environment | 7 | [ ] |
| #23 Write README, CONTRIBUTING and Code of Conduct | 4 | [ ] |
| #16 Vision-model Nutrition Facts extraction prototype (time-boxed) | 5 | [ ] |
| #22 Staging deployment and environment configuration | 6 | [ ] |
| Set up and sort the backlog on the project board (stories, priorities, sprints) | 2 | [ ] |
| Review team-member pull requests timely and thoroughly | 2 | [ ] |
| Participate actively in common team duties (meetings, planning, Discord coordination) | 2 | [ ] |

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
| Review team-member pull requests timely and thoroughly | [ ] | [ ] |
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
| #21 Validate Open Food Facts coverage and field completeness for Canadian products | 5–8 | [ ] |
| #15 Handle complete, incomplete and missing product-database results | 5–8 | [ ] |
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

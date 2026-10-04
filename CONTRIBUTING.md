# Contributing to What's in My Food?

This guide describes how Team Nexus (ECE444 Group 20) works in this repository. It applies to all four team members. It is adapted from the [briandk CONTRIBUTING template](https://gist.github.com/briandk/3d2e8b3ec8daf5a27a62) and from our [Team Workflow Document](Team_Workflow_Document.md), which remains the authority on roles, meetings and conflict resolution.

By contributing, you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Where things live

| What | Where |
|---|---|
| Requirements (authoritative) | [docs/requirements.md](docs/requirements.md) |
| Candidate stories and review discussion | [Issues](https://github.com/suyeon240park/ECE444-Group20/issues) labelled `candidate-story` |
| Implementation tasks | Issues without the `candidate-story` label, each linked to its story |
| Backlog and sprint board | [GitHub Project board](https://github.com/users/suyeon240park/projects/2) |
| Team roles and process | [Team_Workflow_Document.md](Team_Workflow_Document.md) |
| Day-to-day discussion | The team Discord server |

## Reporting a problem or proposing work

Open a GitHub issue. Search existing issues first so the same thing is not filed twice.

**A bug report should include:**

- what you did, what you expected, and what happened instead;
- the product, barcode or photo that triggers it, if there is one;
- the browser or device, and a screenshot when the problem is visual.

**A new requirement** is a candidate story, not a task. Use the `candidate-story` label plus `functional` or `quality`, and include the three parts from Milestone 2:

1. **User story:** As a [role], I want [capability], so that [benefit].
2. **Source and rationale:** evidence for the need, or an explicitly labelled assumption.
3. **Acceptance criteria:** observable conditions, including failure and boundary cases. A quality requirement also states its measure, target, conditions and verification method.

A candidate story is reviewed by a teammate other than its author before the team selects, defers or rejects it.

**An implementation task** has a short description, a link to its story issue, a reference to the story's ID in `docs/requirements.md` (for example F1 or Q1), and a "Done when" list. Add it to the project board.

## Picking up a task

1. Choose an unassigned issue from the current sprint column of the board, highest priority first.
2. Assign yourself and move the card to **In Progress**. One person owns an issue at a time.
3. Record your time estimate in hours before you start. We compare estimates to actual time at the end of each sprint.
4. If you are blocked, say so in Discord as soon as you know. Do not wait for the next stand-up.

## Branches

- `main` is always in a working state. **Nobody commits directly to `main`.**
- Create one branch per issue, from the latest `main`:

  ```
  git switch main
  git pull
  git switch -c <type>/<issue-number>-<short-description>
  ```

- `<type>` is one of `feature`, `fix`, `docs`, `test`, `chore`. Examples: `feature/14-open-food-facts-lookup`, `docs/m3-readme`.
- Keep branches short-lived. Rebase or merge `main` into your branch before opening a pull request if `main` has moved.

## Commits

- Write the subject in the imperative, 72 characters or fewer: "Add barcode detection endpoint", not "added stuff".
- One logical change per commit. Reference the issue in the body when it helps, for example `Refs #14`.
- Never commit secrets, API keys, or users' photos. Benchmark images under `tests/fixtures/` must not contain personal information.

## Pull requests

Every change reaches `main` through a pull request.

**Before you open it**

- Review your own diff first.
- Add or update tests for the code you changed. Relevant unit and integration tests must pass.
- If the change touches Nutrition Facts extraction, run the accuracy benchmark and report the result (see requirement Q1).
- Run regression tests when the change could affect existing behaviour.

**In the description**

- What changed and why, in a few sentences.
- `Closes #<issue>` so the issue closes on merge.
- The acceptance criteria this pull request satisfies.
- Screenshots for any user-interface change.
- A short note on any decision that is not obvious from the code.

**Review and merge**

- At least **one other team member** must review and approve before merging.
- The author addresses every comment, either with a change or with a reply explaining why not.
- The author merges after approval, then checks that the application still works on `main` and moves the card to **Done**.

## Reviewing a pull request

Everyone reviews, and review work is shared roughly equally. Before starting new low-priority work, check whether a teammate is waiting on a review.

Read the code, do not just approve it. Look at:

- **Correctness:** does it meet the acceptance criteria, including failure cases?
- **Tests:** are they present, and do they test the behaviour that matters?
- **Maintainability and readability:** would another teammate understand this in a month?
- **Security and privacy:** no secrets, no user photos kept longer than needed.
- **Fit with the architecture:** does it follow the agreed structure and data flow?

Be specific and kind. Say what you checked, not only what is wrong. Aim to respond within 24 hours, as agreed in the workflow document.

## Changing a requirement

Requirements are not changed by editing code or a target quietly.

1. Explain the proposed change in a comment on the story's issue.
2. Update the issue description.
3. Have the story's reviewer confirm the change.
4. Update `docs/requirements.md` through a pull request.

This applies to provisional targets as well, such as the 95% extraction-accuracy target or the response-time targets.

## Documentation

- Update `README.md` when setup steps, tools or links change.
- Update `Team_Workflow_Document.md`, with a dated entry in its update table, when roles or team processes change.
- Sprint reports go in `docs/`.

## Questions

Ask in Discord. For anything that needs a decision, raise it at the next meeting or open an issue so the outcome is recorded.

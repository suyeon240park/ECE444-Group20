# Usability test report (Q3, #69)

> **If only a pilot was run** (one team member, see the test plan), say so in the Summary, paste the `--pilot` report, and state that Q3 is not evaluated; keep issue #69 open for the real round. Do not fill in the Q3 targets table as if it were met or missed.
>
> Copy this file to `docs/usability/report.md` after the sessions and fill in the brackets. Paste the output of `python -m scripts.usability_report ../docs/usability/session-1` (run from `backend/`) under "Results". No names anywhere: participants are P1 to P5.

**Date(s) of sessions:** [ ]  
**App version tested:** [staging URL and the commit shown by `/api/health`]  
**Facilitator:** Eyad Ahmed. **Second scorer (T3, T4):** Alex An.  
**Test plan and rubric version:** the commit of [`test-plan.md`](test-plan.md) used for every session: [ ]

## Summary

[Two or three sentences: did the run meet the three Q3 targets, and what were the main problems?]

| Measure | Target | Result | |
|---|---|---|---|
| Overall unassisted task success | at least 80% | [ ]% ([ ]/20) | [met / MISSED] |
| Per-task success | each task passed by at least 3 of 5 participants | T1 [ ]/5, T2 [ ]/5, T3 [ ]/5, T4 [ ]/5 | [met / MISSED] |
| Mean SUS | at least 68 | [ ] | [met / MISSED] |

## Conditions

| Condition | Required | Actual |
|---|---|---|
| Participants outside the team | 5 or more | [ ] |
| No nutrition or food-science training (screener answered "no") | all | [ ] |
| Phone-size browser | at least 3 | [ ] |
| Desktop or laptop browser | at least 2 | [ ] |
| Packaged-food categories | at least 3 | [ ] ([list]) |
| Facilitator gave no hints after a task began | all | [ ] |
| Attempts re-run after a Q2 performance failure | recorded against Q2 | [ ] ([issue or note]) |

## Results

[Paste the script's report here.]

## Usability problems

Each problem has its own issue (#69, done-when 6).

| Issue | Problem | Task | Participants | Severity (blocked / slowed / minor) |
|---|---|---|---|---|
| [#] | [ ] | [ ] | [P#] | [ ] |

## Open-ended scoring (T3, T4)

[How many answers the two scorers disagreed on, and what the disagreements were about. If the rubric was ambiguous, say where, so the next round can fix it before testing.]

## What happens next

- Targets met: [record that Q3 initial check passed; list problems that will still be fixed].
- Targets missed: fix the interface or, through a reviewed requirements revision, the requirement; then **retest with new participants** (Q3 verification step 9).

## Limits

- Five participants is a formative check (Q3's provisional assumption), not a statistical estimate.
- Time on task was not a pass/fail measure.
- Readability (Q3 measure 3) is reported separately.

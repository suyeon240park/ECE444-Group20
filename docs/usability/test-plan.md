# Usability test plan and answer rubric (Q3, #69)

Written **before the first session** (Q3 verification step 1). Do not change the task wording or the rubric once session 1 has started; if something is wrong, stop, fix it, and re-run the sessions that used the old version.

Requirement: [Q3](../requirements.md#q3--present-food-analysis-that-non-experts-can-understand-and-navigate-without-help). Facilitator: Eyad. Second scorer for T3 and T4: Alex. Record results in the files described in [Recording results](#recording-results), run `python -m scripts.usability_report ../docs/usability/session-1` from `backend/`, and write the [report](report-template.md).

## Before the sessions: pre-flight (once, by the team)

Run every test product on the deployed app (the staging link in [deployment.md](../deployment.md)) on a phone and a laptop, and fill in this table. The rubric below depends on it, and nothing may be added after session 1.

| Slot | Product and barcode | Category | Whole-package calories shown (T2) | Sodium amount and %DV shown (T3) | Reviewed ingredient to ask about (T4) |
|---|---|---|---|---|---|
| A | | | | | |
| B | | | | | |
| C | | | | | |

Rules for choosing products:

- The three products come from **three different packaged-food categories** (Q3 needs at least 3), for example condiments, beverages and snacks.
- Product A must reach a result that F2 can calculate (the app shows a whole-package calorie value, not "not calculated"). B and C only need to reach a result.
- Each product's ingredient list must contain at least one **reviewed** ingredient: one of the entries in `backend/content/ingredients/entries/`, shown as a tappable ingredient on the results page.
- Have a printed copy or an image file of each product's barcode (or front of pack) ready for T1. Check that the app reads it before the session.
- Wake the backend 10 minutes before each session (`/api/health`), so a cold start is not counted against the participant.

## Pilot run (reduced scope, agreed with Frank on 2026-11-19)

The team did not have time to recruit five outside participants before the sprint ended, so for now **one team member runs the tasks once** (a pilot). A pilot does not satisfy Q3: Q3 needs five outside participants, and the issue stays open until a real round happens (Q3 verification step 9 also says to retest with new participants after a miss).

How to run the pilot so it is still useful:

- Use the pre-flight products and the exact task wording and rubric below. Do the tasks on a phone-size browser (or the laptop at phone width), on the staging app.
- Record the screen (and your voice if you can) so the second scorer can judge T3 and T4 from the recording without you in the room. Say your answers aloud as if answering the facilitator.
- Do not read the rubric or the app's text again while a task is running, and end a task the way a participant would (finished, gave up, or "I'd ask for help").
- Eyad scores T3 and T4 from the recording and Alex scores them separately, as in [Scoring T3 and T4](#scoring-t3-and-t4).
- Record it in `docs/usability/pilot/` (copy the three blank CSV files there; use participant `P1`, `nutrition_training` is `no` only if it is true for the person doing it) and run `python -m scripts.usability_report --pilot ../docs/usability/pilot`. The report is stamped as a pilot.
- Say in the report that the person doing the pilot knows the app, so the success rate is likely higher than a stranger's, and that the pilot gives no Q3 verdict.

## Participants

| Requirement | How to check |
|---|---|
| 5 or more, **outside the development team** | Not in ECE444 Group 20 |
| **No** professional or formal academic training in nutrition or food science | Ask the screener question below; record the answer; exclude on "yes" |
| At least **3 on a phone-size browser**, at least **2 on a desktop or laptop** | Assign devices as you recruit: P1 to P3 phone, P4 and P5 desktop, and swap if someone cannot attend |
| Normal network connection | Their own Wi-Fi or mobile data; not the team's hotspot |

Screener question (read aloud): "Do you have professional or formal academic training in nutrition or food science?" Anything but a clear "no" excludes them. Do not ask for a name beyond what you need to schedule; the results never contain one.

Participants are identified only as **P1, P2, ...** in every file.

## Facilitator script

Read the words in quotes exactly. Same wording for every participant.

**Introduction.** "Thank you for helping. We are testing a web app, not you. There are no wrong answers and you cannot break anything. I'll give you four short tasks. Please say what you are thinking as you go. Once a task starts I can't answer questions or give hints, because I need to see what happens without help. If you get stuck you can say 'I'm done with this one' and we will move on. Do you have any questions before we begin?"

**Start.** Open the app link on the participant's device. Do not demonstrate it. Hand over the product (the barcode image or the printed pack) for the task.

**During a task.** Say nothing that points to a screen, button or word in the app. If asked a question: "I can't help during a task. Do what you think is best, or tell me you are done." Note what the participant did and said.

**A task ends** when the participant (1) says they have finished, (2) gives up, or (3) asks for help. Write down which. Asking for help, asking a team member for the answer, or leaving the app to search elsewhere is a failure; so is giving up.

**Do not tell** participants whether an answer was right until all four tasks and the SUS are done.

**If the backend is slow or fails** (a scan or lookup takes more than 10 seconds, or an error says the service is unavailable): stop, mark the attempt `rerun_q2`, record it against Q2 (#47, note the time and the product), wake the backend and re-run that task. It is not counted as a usability failure.

## Tasks

| Task | Requirement | Product | Participant instruction (read exactly) |
|---|---|---|---|
| T1 | F1 | A | "Here is a product. Use the app to find out about it." |
| T2 | F2 | A | "Using the app, find how many calories are in the whole package of this product." |
| T3 | F3 | B | "Using the app, find the sodium information for this product. Then tell me in your own words what the numbers mean." |
| T4 | F4 | C | "Using the app, find out what *[ingredient from the pre-flight table]* is, and where the information about it comes from." |

Keep the order T1 to T4. T1 starts from the app's first screen; for T2 to T4 the participant may use the same flow again to open the product. For T1 the participant provides the image themselves (phone: from the files or camera; desktop: file upload).

## Answer rubric

An attempt is a **success** only if it meets **every required item** and no help was given. Anything else is a failure.

### T1: reach the result (F1). Facilitator scores by observation

| Required | Success |
|---|---|
| Gets from the first screen to a result for the product | The results page shows the product's name (database result) or a "Nutrition-only result" (photo result) without the facilitator touching the device or giving a hint |

Failure: gives up; asks for help; stops at an error without finding another route (a retry, another image, or the Nutrition Facts photo option counts as finding a route); reaches a result for a different product.

### T2: whole-package calories (F2). Facilitator scores by observation

| Required | Success |
|---|---|
| Finds the **whole-package** calorie value | States the number in the "Whole package" column or row (the pre-flight value for slot A, as displayed, including any "Approximate" label) |

Failure: states the per-serving calories; states another number; gives up; asks for help. If the participant says the per-serving number and then corrects themselves without a hint, score what they settle on.

### T3: sodium and what it means (F3). Two scorers, independently

| ID | Required? | Concept the answer must contain |
|---|---|---|
| T3-a | **Yes** | Finds the sodium amount shown (states the figure in mg, or points to it, matching the pre-flight value for slot B) |
| T3-b | **Yes** | Says the % is a share of a day's recommended amount: for example "how much of what I should have in a day", "percent of the daily limit" |
| T3-c | No (recorded for information) | Says which amount the number refers to: per serving, or the whole package |

Wrong examples that fail T3-b: "it's the percentage of sodium in the food", "how salty it is", "it's the percent of the product that is salt".

### T4: ingredient explanation and source (F4). Two scorers, independently

| ID | Required? | Concept the answer must contain |
|---|---|---|
| T4-a | **Yes** | Opens the ingredient's page and says in their own words what it is or why it is used, consistent with the "What it is" or "Why it is used" text |
| T4-b | **Yes** | Names or points to where the information comes from (an organization or source shown on the page, for example the named authority) |

Failure: only repeats the ingredient's name; names a source that is not on the page; searches elsewhere.

### Scoring T3 and T4

Alex and Eyad each read the facilitator's notes for T3 and T4 **separately**, and each enter `pass` or `fail` in the attempts file (`scorer_a`, `scorer_b`) without seeing the other's score. Where the two differ, discuss against the rubric, then write the agreed result in `final` and the reason in `notes`. The report counts the disagreements.

## After the four tasks: SUS

Hand over the System Usability Scale (below). Each item is answered 1 (strongly disagree) to 5 (strongly agree). Record the ten numbers in `sus.csv`.

1. I think that I would like to use this system frequently.
2. I found the system unnecessarily complex.
3. I thought the system was easy to use.
4. I think that I would need the support of a technical person to be able to use this system.
5. I found the various functions in this system were well integrated.
6. I thought there was too much inconsistency in this system.
7. I would imagine that most people would learn to use this system very quickly.
8. I found the system very cumbersome to use.
9. I felt very confident using the system.
10. I needed to learn a lot of things before I could get going with this system.

Score: odd items contribute (answer - 1); even items contribute (5 - answer); the sum times 2.5 gives 0 to 100. `usability_report.py` does this.

Then ask: "What was the most confusing part?" and write down the answer. Thank them.

## Recording results

Copy the templates in this folder into a new folder, for example `docs/usability/session-1/`, and fill them in. They contain no names.

| File | One row per | Columns |
|---|---|---|
| `participants.csv` | participant | `participant`, `device` (`phone` or `desktop`), `nutrition_training` (`no`; exclude `yes`) |
| `attempts.csv` | participant and task | `participant`, `task` (T1 to T4), `category` (of the product used), `outcome`, `scorer_a`, `scorer_b`, `final`, `notes` |
| `sus.csv` | participant | `participant`, `q1` to `q10` |

`outcome` values: `completed`, `gave_up`, `asked_help`, `rerun_q2` (not counted; re-run the task and add the new row). For T1 and T2 leave `scorer_a` and `scorer_b` empty and set `final` from your observation using the rubric. For T3 and T4 `final` is the agreed result. `final` is `pass` or `fail`; `gave_up` and `asked_help` must be `fail`.

Optional extras the report ignores: time on task (Q3 says it is for information only) goes in `notes`.

## Problems found

For each usability problem observed, open **its own issue** (Q3, and #69 done-when 6) titled `Usability: <what went wrong>`, labelled as a usability finding, with:

- participants who hit it (P numbers) and the task;
- what they did and said (quote, no names);
- how severe: blocked the task, slowed it down, or minor;
- a suggested change, if one is obvious.

Link the issues from the report. If a target is missed, Q3 says to fix the interface or revise the requirement and **retest with new participants**; a target is only changed through a reviewed requirements revision.

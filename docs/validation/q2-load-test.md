# Issue #68: Q2 load test on staging

Run with `python -m scripts.load_test --out ../docs/validation/q2-load-test.json` against staging (commit `f243b23`, gunicorn with 1 worker and 4 threads on Render's free plan) on 2026-11-20. Every request is in [`q2-load-test.json`](q2-load-test.json); `python -m scripts.load_test --from ../docs/validation/q2-load-test.json` prints the report again. The photo set is [`tests/fixtures/barcode_photos/`](../../tests/fixtures/barcode_photos/README.md).

**Result: Q2 is not met on staging.** 78% of identifications answered within 5 s (target 95%). Every request got an answer within 10 s (max 6.8 s), so the hard limit holds. Cached lookups took about 3.6 s (provisional target: 95% within 1 s).

Run 2026-11-20T09:14:50-05:00.

- Cold start: 37.4 s until `/api/health` answered (not counted below).
- `/api/health` round trip: median 0.08 s; each time below includes about this much network time, which Q2's server-side measure leaves out.
- Open Food Facts directly, 15 reads 4 s apart: median 0.12 s, p95 0.45 s, max 0.45 s (HTTP 200, 404).
- Rounds: 1 external round of 20 concurrent photos, then 3 cached rounds of 20.

| Identifications | n | Target | Within target | p50 | p95 | Max | No answer in 10 s | Unexpected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| All identifications | 80 | 5 s | 78% | 3.80 s | 6.50 s | 6.78 s | 0% | 6% |
| External lookup (OFF) | 17 | 5 s | 35% | 6.19 s | 6.50 s | 6.50 s | 0% | 0% |
| Cached lookup | 53 | 1 s | 0% | 3.59 s | 3.89 s | 3.91 s | 0% | 0% |
| No barcode in photo | 5 | 5 s | 60% | 4.28 s | 6.28 s | 6.28 s | 0% | 0% |
| Unexpected answer or error | 5 | 5 s | 0% | 6.69 s | 6.78 s | 6.78 s | 0% | 100% |

| Target | Result |
|---|---|
| 95% within 5 s | FAIL |
| none without an answer after 10 s | PASS |
| cached: 95% within 1 s (provisional) | FAIL |

Unexpected answers:

- 01_cheerios.jpg (known): upstream_unavailable after 6.69 s
- 03_cream-of-wheat.jpg (known): upstream_unavailable after 6.69 s
- 04_lays-classic.jpg (known): upstream_unavailable after 6.58 s
- 13_unknown-a.jpg (unknown): upstream_unavailable after 6.78 s
- 02_harvest-crunch.jpg (known): no answer: SSLError after 0.20 s

## Why it is slow

- **Requests queue on the server.** Alone, an identification takes 0.2 to 0.4 s. In a round of 20, the barcode step's times rise evenly from 0.4 s to 3.7 s: the server works through 4 requests at a time, and reading a barcode is CPU work on a small free instance. Cached lookups take about 1.5 s for the same reason, though the lookup itself is a dictionary read: they wait behind the barcode requests. A full cached identification was 3.4 to 3.9 s in every round.
- **Open Food Facts rejects a burst.** 4 of the 15 lookups in the external round failed with `upstream_unavailable` after about 6.7 s. Read one every 4 s, OFF answered every barcode in 0.12 s (median). A local run of the same round logged HTTP 429 from OFF for 4 of 15 concurrent reads, so OFF limits bursts and not only reads per minute; staging's logs were not checked.
- One request (`02_harvest-crunch.jpg`, cached round) failed in the client with an `SSLError` after 0.2 s, while 20 connections opened at once. It is a client-side connection failure, not a server answer.

Times are measured by the client, so they include about 0.08 s of network per request (median `/api/health` round trip) and the upload. That does not change the outcome.

## What could change it (not done in #68)

1. More concurrency on the server: more gunicorn threads or workers, if the instance's memory allows, or a larger instance.
2. Pace or queue OFF reads on the server, and make concurrent lookups of the same barcode share one read, so a burst does not get HTTP 429.
3. Or, per Q2's verification step 7, revise the provisional 20-concurrent / 5 s / 1 s targets to what the free deployment supports, with reviewer confirmation.

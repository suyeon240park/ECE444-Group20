"""Load test of product identification on staging, for Q2 (#68).

Follows Q2's verification method (``docs/requirements.md``):

1. **Cold start.** Render's free backend sleeps after 15 minutes; the time until
   ``/api/health`` answers is reported on its own and not counted below.
2. **Open Food Facts baseline.** Each barcode in the photo set is read straight from OFF,
   one every 4 s to stay within its 15 product reads per minute.
3. **External round.** All 20 photos of ``tests/fixtures/barcode_photos/manifest.csv`` are
   sent at once: 12 known products, 3 unknown barcodes, 5 photos with no barcode. That is
   15 OFF reads by the server, its whole per-minute allowance.
4. **Cached rounds.** After a minute, rounds of 20 concurrent scans of the known products,
   which the server now answers from its product cache.

One identification is what the app does after a photo is taken: ``POST /api/barcode``,
then ``GET /api/products/{barcode}`` if a barcode was read. Its time is measured by this
client, so it includes the network and the upload, which Q2's server-side measure leaves
out; the median ``/api/health`` round trip is reported to show how much that is. A lookup
counts as cached when the product's ``retrieved_at`` is older than the request.

Run from ``backend/``::

    python -m scripts.load_test                       # staging, Markdown report
    python -m scripts.load_test --out ../q2.json      # also save every request
    python -m scripts.load_test --api http://localhost:5000 --skip-off-baseline

Run it on a sleeping backend (15 minutes after the last request) so the product cache is
empty; otherwise the known products of the external round are cached already, which the
report shows. Exit status 0 when Q2's targets are met, 1 otherwise.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import requests

API = "https://whats-in-my-food-api.onrender.com"
OFF = "https://world.openfoodfacts.org"
USER_AGENT = "WhatsInMyFood-LoadTest/1.0 (ECE444 course project)"

REPO = Path(__file__).resolve().parents[2]
PHOTOS = REPO / "tests" / "fixtures" / "barcode_photos"
MANIFEST = PHOTOS / "manifest.csv"

CONCURRENCY = 20
TARGET_SECONDS = 5  # 95% of identifications
CACHED_TARGET_SECONDS = 1  # 95% of cached lookups (provisional)
MAX_SECONDS = 10  # no request goes longer without an answer
TARGET_SHARE = 0.95
OFF_READS_PER_MINUTE = 15

WAKE_SECONDS = 180
TIMEOUT = 30  # longer than MAX_SECONDS, so a slow answer is measured instead of cut off
ROUND_PAUSE = 5

# Kinds of identification, reported separately.
EXTERNAL, CACHED, NO_BARCODE, ERROR = "external", "cached", "no_barcode", "error"
# Outcome prefix when the server gave no answer at all.
NO_ANSWER = "no answer: "


@dataclass(frozen=True)
class Photo:
    path: Path
    case: str  # "known", "unknown" or "no_barcode"
    barcode: str

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class Sample:
    """One identification."""

    photo: str
    case: str
    kind: str  # EXTERNAL, CACHED, NO_BARCODE or ERROR
    seconds: float
    barcode_seconds: float
    lookup_seconds: float | None
    outcome: str  # what the server answered, e.g. "product", "product_not_found"
    expected: bool  # the answer the photo should get
    timed_out: bool  # no answer within MAX_SECONDS


def load_photos(manifest: Path = MANIFEST) -> list[Photo]:
    with manifest.open(newline="", encoding="utf-8") as file:
        return [
            Photo((manifest.parent / row["photo"]).resolve(), row["case"], row["barcode"])
            for row in csv.DictReader(file)
        ]


def same_barcode(a: str, b: str) -> bool:
    """A 12-digit UPC-A and its EAN-13 form (a leading zero) are the same product."""
    return a.zfill(13) == b.zfill(13)


def is_cached(product: dict[str, Any], date_header: str | None, lookup_seconds: float) -> bool:
    """Whether the server answered from its cache rather than asking Open Food Facts.

    A fresh lookup's ``retrieved_at`` is a moment during the request, so it is at most the
    request's length older than the response's ``Date``. Both come from the server's clock,
    so the client's clock does not matter. ``Date`` has whole seconds, hence the 2 s margin.
    """
    try:
        retrieved = datetime.fromisoformat(
            product["product"]["source"]["retrieved_at"].replace("Z", "+00:00")
        )
        answered = parsedate_to_datetime(date_header or "")
    except (KeyError, TypeError, ValueError):
        return False
    return (answered - retrieved).total_seconds() > lookup_seconds + 2


def error_code(response: requests.Response) -> str:
    try:
        return response.json()["error"]["code"]
    except (ValueError, KeyError, TypeError):
        return f"http_{response.status_code}"


def percentile(values: Sequence[float], share: float) -> float:
    """Nearest-rank percentile: the smallest value with ``share`` of the values at or below."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]


class LoadTest:
    def __init__(
        self,
        api: str = API,
        off: str = OFF,
        timeout: float = TIMEOUT,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api = api.rstrip("/")
        self.off = off.rstrip("/")
        self.timeout = timeout
        self.clock = clock
        self.sleep = sleep

    # --- before the test ----------------------------------------------------------

    def wake(self, wake_seconds: float = WAKE_SECONDS, pause: float = 5) -> float:
        """Seconds until ``/api/health`` is ok: the cold start if the backend was asleep."""
        start = self.clock()
        while True:
            try:
                response = requests.get(self.api + "/api/health", timeout=wake_seconds)
                if response.ok and response.json().get("status") == "ok":
                    return self.clock() - start
            except (requests.RequestException, ValueError):
                pass
            if self.clock() - start >= wake_seconds:
                raise RuntimeError(f"/api/health not ok after {wake_seconds:.0f} s")
            self.sleep(pause)

    def round_trips(self, count: int = 5) -> list[float]:
        """``/api/health`` round trips: the network's share of each measured time."""
        times = []
        with requests.Session() as http:
            for _ in range(count):
                start = self.clock()
                http.get(self.api + "/api/health", timeout=self.timeout)
                times.append(self.clock() - start)
        return times

    def off_baseline(self, barcodes: Sequence[str]) -> list[dict[str, Any]]:
        """Time each barcode read straight from Open Food Facts, within its rate limit."""
        spacing = 60 / OFF_READS_PER_MINUTE
        results = []
        with requests.Session() as http:
            for number, barcode in enumerate(barcodes):
                if number:
                    self.sleep(spacing)
                start = self.clock()
                try:
                    response = http.get(
                        f"{self.off}/api/v3/product/{barcode.zfill(13)}",
                        params={"fields": "code,product_name"},
                        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                        timeout=self.timeout,
                    )
                    status = str(response.status_code)
                except requests.RequestException as exc:
                    status = type(exc).__name__
                results.append(
                    {"barcode": barcode, "seconds": self.clock() - start, "status": status}
                )
        return results

    # --- the test -----------------------------------------------------------------

    def identify(self, photo: Photo, http: requests.Session) -> Sample:
        """Read the barcode in ``photo`` and look the product up, as the app does."""
        start = self.clock()
        barcode_seconds = 0.0
        lookup_seconds: float | None = None

        def sample(kind: str, outcome: str, expected: bool) -> Sample:
            seconds = self.clock() - start
            return Sample(
                photo.name,
                photo.case,
                kind,
                round(seconds, 3),
                round(barcode_seconds, 3),
                None if lookup_seconds is None else round(lookup_seconds, 3),
                outcome,
                expected,
                timed_out=seconds > MAX_SECONDS,
            )

        try:
            with photo.path.open("rb") as image:
                read = http.post(
                    self.api + "/api/barcode",
                    files={"image": (photo.name, image, "image/jpeg")},
                    timeout=self.timeout,
                )
            barcode_seconds = self.clock() - start
            if read.status_code != 200:
                code = error_code(read)
                if code == "no_barcode_found":
                    return sample(NO_BARCODE, code, photo.case == "no_barcode")
                return sample(ERROR, code, False)

            barcode = read.json()["barcode"]
            if photo.case == "no_barcode" or not same_barcode(barcode, photo.barcode):
                return sample(ERROR, f"read {barcode}", False)

            lookup_start = self.clock()
            lookup = http.get(f"{self.api}/api/products/{barcode}", timeout=self.timeout)
            lookup_seconds = self.clock() - lookup_start
            if lookup.status_code == 200:
                cached = is_cached(lookup.json(), lookup.headers.get("Date"), lookup_seconds)
                return sample(CACHED if cached else EXTERNAL, "product", photo.case == "known")
            code = error_code(lookup)
            if code == "product_not_found":
                return sample(EXTERNAL, code, photo.case == "unknown")
            return sample(ERROR, code, False)
        except requests.Timeout:
            return sample(ERROR, NO_ANSWER + "timeout", False)
        except (requests.RequestException, ValueError, KeyError) as exc:
            return sample(ERROR, NO_ANSWER + type(exc).__name__, False)

    def concurrent_round(self, photos: Sequence[Photo]) -> list[Sample]:
        """Send every photo at once, one thread and connection each."""
        start_together = threading.Barrier(len(photos))

        def one(photo: Photo) -> Sample:
            with requests.Session() as http:
                start_together.wait()
                return self.identify(photo, http)

        with ThreadPoolExecutor(max_workers=len(photos)) as pool:
            return list(pool.map(one, photos))

    def run(
        self,
        photos: Sequence[Photo],
        cached_rounds: int = 3,
        off_baseline: bool = True,
        wake_seconds: float = WAKE_SECONDS,
    ) -> dict[str, Any]:
        cold_start = self.wake(wake_seconds)
        round_trips = self.round_trips()
        lookups = [p.barcode for p in photos if p.barcode]
        baseline = self.off_baseline(lookups) if off_baseline else []

        warm_up = next(p for p in photos if p.case == "no_barcode")  # costs no OFF read
        with requests.Session() as http:
            self.identify(warm_up, http)

        external = self.concurrent_round(photos[:CONCURRENCY])

        known = [p for p in photos if p.case == "known"]
        repeated = [known[i % len(known)] for i in range(CONCURRENCY)]
        cached: list[Sample] = []
        for number in range(cached_rounds):
            # The first wait lets OFF's per-minute window pass, in case a product was
            # not cached and is read again.
            self.sleep(60 if number == 0 else ROUND_PAUSE)
            cached += self.concurrent_round(repeated)

        return {
            "api": self.api,
            "started": datetime.now().astimezone().isoformat(timespec="seconds"),
            "cold_start_seconds": round(cold_start, 2),
            "health_round_trips": [round(t, 3) for t in round_trips],
            "off_baseline": baseline,
            "rounds": {
                "external": [asdict(s) for s in external],
                "cached": [asdict(s) for s in cached],
            },
        }


# --- report -----------------------------------------------------------------------


@dataclass(frozen=True)
class Summary:
    count: int
    within_target: float  # share answered (result or explicit failure) within the target
    p50: float
    p95: float
    max: float
    timed_out: float  # share with no answer within MAX_SECONDS
    failed: float  # share with an unexpected answer or none


def summarize(samples: Sequence[dict[str, Any]], target: float) -> Summary | None:
    if not samples:
        return None
    seconds = [s["seconds"] for s in samples]
    # An explicit failure (e.g. upstream_timeout) is an answer; a dropped connection is not.
    answered = [s for s in samples if not s["outcome"].startswith(NO_ANSWER)]
    return Summary(
        count=len(samples),
        within_target=sum(s["seconds"] <= target for s in answered) / len(samples),
        p50=statistics.median(seconds),
        p95=percentile(seconds, 0.95),
        max=max(seconds),
        timed_out=sum(s["timed_out"] for s in samples) / len(samples),
        failed=sum(not s["expected"] for s in samples) / len(samples),
    )


def groups(result: dict[str, Any]) -> dict[str, tuple[list[dict[str, Any]], float]]:
    """Every identification by kind, each with its target in seconds."""
    every = result["rounds"]["external"] + result["rounds"]["cached"]
    by_kind = {
        kind: [s for s in every if s["kind"] == kind] for kind in (EXTERNAL, CACHED, NO_BARCODE)
    }
    return {
        "All identifications": (every, TARGET_SECONDS),
        "External lookup (OFF)": (by_kind[EXTERNAL], TARGET_SECONDS),
        "Cached lookup": (by_kind[CACHED], CACHED_TARGET_SECONDS),
        "No barcode in photo": (by_kind[NO_BARCODE], TARGET_SECONDS),
        "Unexpected answer or error": ([s for s in every if s["kind"] == ERROR], TARGET_SECONDS),
    }


def verdict(result: dict[str, Any]) -> dict[str, bool]:
    """Q2's targets; the cached one only if any lookup was cached."""
    found = groups(result)
    every = summarize(found["All identifications"][0], TARGET_SECONDS)
    checks = {
        f"{TARGET_SHARE:.0%} within {TARGET_SECONDS} s": every is not None
        and every.within_target >= TARGET_SHARE,
        f"none without an answer after {MAX_SECONDS} s": every is not None and every.timed_out == 0,
    }
    cached = summarize(found["Cached lookup"][0], CACHED_TARGET_SECONDS)
    if cached is not None:
        checks[f"cached: {TARGET_SHARE:.0%} within {CACHED_TARGET_SECONDS} s (provisional)"] = (
            cached.within_target >= TARGET_SHARE
        )
    return checks


def report(result: dict[str, Any]) -> str:
    lines = [f"# Q2 load test: {result['api']}", "", f"Run {result['started']}.", ""]

    rtt = result["health_round_trips"]
    lines += [
        f"- Cold start: {result['cold_start_seconds']:.1f} s until `/api/health` answered "
        "(not counted below).",
        f"- `/api/health` round trip: median {statistics.median(rtt):.2f} s; each time below "
        "includes about this much network time, which Q2's server-side measure leaves out.",
    ]
    baseline = result["off_baseline"]
    if baseline:
        times = [b["seconds"] for b in baseline]
        statuses = ", ".join(sorted({b["status"] for b in baseline}))
        lines.append(
            f"- Open Food Facts directly, {len(baseline)} reads 4 s apart: median "
            f"{statistics.median(times):.2f} s, p95 {percentile(times, 0.95):.2f} s, "
            f"max {max(times):.2f} s (HTTP {statuses})."
        )
    external_round = result["rounds"]["external"]
    cached_round = result["rounds"]["cached"]
    lines.append(
        f"- Rounds: 1 external round of {len(external_round)} concurrent photos, then "
        f"{len(cached_round) // CONCURRENCY or 0} cached rounds of {CONCURRENCY}."
    )
    early = sum(s["kind"] == CACHED for s in external_round)
    if early:
        lines.append(
            f"- {early} known products of the external round were already cached: the backend "
            "was not asleep, so fewer external lookups were measured."
        )

    lines += [
        "",
        "| Identifications | n | Target | Within target | p50 | p95 | Max "
        "| No answer in 10 s | Unexpected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, (samples, target) in groups(result).items():
        summary = summarize(samples, target)
        if summary is None:
            lines.append(f"| {name} | 0 | {target} s | | | | | | |")
            continue
        lines.append(
            f"| {name} | {summary.count} | {target} s | {summary.within_target:.0%} | "
            f"{summary.p50:.2f} s | {summary.p95:.2f} s | {summary.max:.2f} s | "
            f"{summary.timed_out:.0%} | {summary.failed:.0%} |"
        )

    lines += ["", "| Target | Result |", "|---|---|"]
    lines += [f"| {name} | {'PASS' if ok else 'FAIL'} |" for name, ok in verdict(result).items()]

    unexpected = [s for s in external_round + cached_round if not s["expected"]]
    if unexpected:
        lines += ["", "Unexpected answers:", ""]
        lines += [
            f"- {s['photo']} ({s['case']}): {s['outcome']} after {s['seconds']:.2f} s"
            for s in unexpected
        ]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default=API, help=f"backend URL (default {API})")
    parser.add_argument("--cached-rounds", type=int, default=3, help="default 3")
    parser.add_argument(
        "--skip-off-baseline", action="store_true", help="do not time Open Food Facts directly"
    )
    parser.add_argument(
        "--wake-seconds",
        type=float,
        default=WAKE_SECONDS,
        help=f"how long to wait for a sleeping backend (default {WAKE_SECONDS})",
    )
    parser.add_argument("--out", type=Path, help="also save every request here as JSON")
    parser.add_argument(
        "--from", dest="saved", type=Path, help="report on a saved --out file; send nothing"
    )
    args = parser.parse_args(argv)

    if args.saved:
        result = json.loads(args.saved.read_text(encoding="utf-8"))
    else:
        result = LoadTest(args.api).run(
            load_photos(),
            cached_rounds=args.cached_rounds,
            off_baseline=not args.skip_off_baseline,
            wake_seconds=args.wake_seconds,
        )
        if args.out:
            args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(report(result))
    return 0 if all(verdict(result).values()) else 1


if __name__ == "__main__":
    sys.exit(main())

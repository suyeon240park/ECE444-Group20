"""The Q2 load test (#68): its photo set, and the script against a faked staging."""

import json

import pytest
import requests
import responses

from app.services.barcode import BarcodeError, detect_barcode
from scripts import load_test as lt

API = "https://api.test"
OFF = "https://off.test"
DATE = "Fri, 20 Nov 2026 12:00:10 GMT"
FRESH = "2026-11-20T12:00:09Z"  # retrieved during the request
OLD = "2026-11-20T11:58:00Z"  # retrieved two minutes earlier: cached

PHOTOS = lt.load_photos()
KNOWN = next(p for p in PHOTOS if p.case == "known")
UNKNOWN = next(p for p in PHOTOS if p.case == "unknown")
NO_BARCODE = next(p for p in PHOTOS if p.case == "no_barcode")


def product(retrieved_at=FRESH):
    return {"result": "product", "product": {"source": {"retrieved_at": retrieved_at}}}


def error(code):
    return {"error": {"code": code, "message": code}}


class FakeClock:
    """Each reading is 0.1 s after the last; ``sleep`` only moves the clock."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 0.1
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def make_tester(clock=None):
    clock = clock or FakeClock()
    return lt.LoadTest(API, OFF, clock=clock, sleep=clock.sleep)


# --- the photo set ----------------------------------------------------------------


def test_photo_set_has_twenty_photos_with_the_failure_cases():
    cases = [p.case for p in PHOTOS]
    assert len(PHOTOS) == lt.CONCURRENCY
    assert cases.count("known") == 12
    assert cases.count("unknown") == 3
    assert cases.count("no_barcode") == 5
    # The external round must stay within Open Food Facts' per-minute allowance.
    assert sum(1 for p in PHOTOS if p.barcode) <= lt.OFF_READS_PER_MINUTE


@pytest.mark.parametrize("photo", PHOTOS, ids=lambda p: p.name)
def test_each_photo_reads_as_the_manifest_says(photo):
    assert photo.path.stat().st_size <= 10 * 1024 * 1024  # Q2's condition
    try:
        found = detect_barcode(photo.path.read_bytes()).barcode
    except BarcodeError as exc:
        found = exc.code
    if photo.case == "no_barcode":
        assert found == "no_barcode_found"
    else:
        assert lt.same_barcode(found, photo.barcode)


# --- helpers ------------------------------------------------------------------------


def test_same_barcode_ignores_the_upc_a_leading_zero():
    assert lt.same_barcode("065633132832", "0065633132832")
    assert not lt.same_barcode("065633132832", "065633132833")


def test_is_cached_compares_retrieved_at_with_the_server_date():
    assert lt.is_cached(product(OLD), DATE, lookup_seconds=0.5)
    assert not lt.is_cached(product(FRESH), DATE, lookup_seconds=0.5)
    assert not lt.is_cached(product(FRESH), None, lookup_seconds=0.5)
    assert not lt.is_cached({"product": {}}, DATE, lookup_seconds=0.5)


def test_percentile_is_nearest_rank():
    values = [float(n) for n in range(1, 21)]
    assert lt.percentile(values, 0.95) == 19.0
    assert lt.percentile(values, 0.5) == 10.0
    assert lt.percentile([3.0], 0.95) == 3.0


# --- one identification -------------------------------------------------------------


def barcode_reply(barcode):
    responses.post(f"{API}/api/barcode", json={"barcode": barcode, "format": "EAN13"})


@responses.activate
def test_known_product_from_open_food_facts():
    barcode_reply(KNOWN.barcode)
    responses.get(f"{API}/api/products/{KNOWN.barcode}", json=product(), headers={"Date": DATE})
    sample = make_tester().identify(KNOWN, requests.Session())
    assert (sample.kind, sample.outcome, sample.expected) == (lt.EXTERNAL, "product", True)
    assert sample.lookup_seconds is not None and not sample.timed_out


@responses.activate
def test_known_product_from_the_cache():
    barcode_reply(KNOWN.barcode)
    responses.get(f"{API}/api/products/{KNOWN.barcode}", json=product(OLD), headers={"Date": DATE})
    assert make_tester().identify(KNOWN, requests.Session()).kind == lt.CACHED


@responses.activate
def test_unknown_product_is_an_external_lookup():
    barcode_reply(UNKNOWN.barcode[1:])  # read as UPC-A
    responses.get(
        f"{API}/api/products/{UNKNOWN.barcode[1:]}", status=404, json=error("product_not_found")
    )
    sample = make_tester().identify(UNKNOWN, requests.Session())
    assert (sample.kind, sample.outcome, sample.expected) == (
        lt.EXTERNAL,
        "product_not_found",
        True,
    )


@responses.activate
def test_photo_without_a_barcode_needs_no_lookup():
    responses.post(f"{API}/api/barcode", status=422, json=error("no_barcode_found"))
    sample = make_tester().identify(NO_BARCODE, requests.Session())
    assert (sample.kind, sample.expected, sample.lookup_seconds) == (lt.NO_BARCODE, True, None)


@responses.activate
def test_wrong_barcode_is_unexpected():
    barcode_reply("4006381333931")
    sample = make_tester().identify(KNOWN, requests.Session())
    assert (sample.kind, sample.outcome, sample.expected) == (lt.ERROR, "read 4006381333931", False)


@responses.activate
def test_upstream_failure_is_an_explicit_answer_but_unexpected():
    barcode_reply(KNOWN.barcode)
    responses.get(f"{API}/api/products/{KNOWN.barcode}", status=504, json=error("upstream_timeout"))
    sample = make_tester().identify(KNOWN, requests.Session())
    assert (sample.kind, sample.outcome, sample.expected) == (lt.ERROR, "upstream_timeout", False)


@responses.activate
def test_client_timeout_is_no_answer():
    responses.post(f"{API}/api/barcode", body=requests.Timeout())
    sample = make_tester().identify(KNOWN, requests.Session())
    assert sample.outcome.startswith(lt.NO_ANSWER)
    assert not sample.expected


def test_slow_answer_counts_as_timed_out():
    class SlowClock(FakeClock):
        def __call__(self):
            self.now += 6
            return self.now

    with responses.RequestsMock() as mock:
        mock.post(f"{API}/api/barcode", json={"barcode": KNOWN.barcode, "format": "EAN13"})
        mock.get(f"{API}/api/products/{KNOWN.barcode}", json=product(), headers={"Date": DATE})
        sample = make_tester(SlowClock()).identify(KNOWN, requests.Session())
    assert sample.timed_out and sample.seconds > lt.MAX_SECONDS


# --- the whole run ------------------------------------------------------------------


@pytest.fixture
def result():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        fake_staging(mock)
        # Real time: the faked staging answers at once. Waits are skipped.
        yield lt.LoadTest(API, OFF, sleep=lambda _seconds: None).run(PHOTOS, cached_rounds=2)


def fake_staging(mock):
    """A healthy staging, and an Open Food Facts that knows the known products."""
    mock.get(f"{API}/api/health", json={"status": "ok", "commit": "abc"})
    for photo in PHOTOS:
        if photo.barcode:
            mock.get(
                f"{OFF}/api/v3/product/{photo.barcode.zfill(13)}",
                status=200 if photo.case == "known" else 404,
                json={},
            )

    def read(request):
        name = request.body.decode("latin-1").split('filename="', 1)[1].split('"', 1)[0]
        photo = next(p for p in PHOTOS if p.name == name)
        if not photo.barcode:
            return 422, {}, json.dumps(error("no_barcode_found"))
        return 200, {}, json.dumps({"barcode": photo.barcode, "format": "EAN13"})

    seen = set()

    def lookup(request):
        barcode = request.url.rsplit("/", 1)[1]
        if any(p.barcode == barcode and p.case == "unknown" for p in PHOTOS):
            return 404, {}, json.dumps(error("product_not_found"))
        retrieved = OLD if barcode in seen else FRESH
        seen.add(barcode)
        return 200, {"Date": DATE}, json.dumps(product(retrieved))

    mock.add_callback(responses.POST, f"{API}/api/barcode", callback=read)
    for photo in PHOTOS:
        if photo.barcode:
            mock.add_callback(responses.GET, f"{API}/api/products/{photo.barcode}", callback=lookup)


def test_run_measures_each_kind(result):
    external, cached = result["rounds"]["external"], result["rounds"]["cached"]
    assert len(external) == lt.CONCURRENCY and len(cached) == 2 * lt.CONCURRENCY
    assert {s["kind"] for s in external} == {lt.EXTERNAL, lt.NO_BARCODE}
    assert {s["kind"] for s in cached} == {lt.CACHED}
    assert all(s["expected"] for s in external + cached)
    assert len(result["off_baseline"]) == 15
    assert {b["status"] for b in result["off_baseline"]} == {"200", "404"}


def test_run_waits_between_open_food_facts_reads():
    clock = FakeClock()
    with responses.RequestsMock() as mock:
        for photo in PHOTOS[:3]:
            mock.get(f"{OFF}/api/v3/product/{photo.barcode.zfill(13)}", json={})
        make_tester(clock).off_baseline([p.barcode for p in PHOTOS[:3]])
    assert clock.now >= 2 * 60 / lt.OFF_READS_PER_MINUTE


def test_report_and_verdict(result):
    text = lt.report(result)
    assert "| External lookup (OFF) | 15 |" in text
    assert "| Cached lookup | 40 |" in text
    assert "| No barcode in photo | 5 |" in text
    assert "Open Food Facts directly, 15 reads" in text
    assert "already cached" not in text
    assert all(lt.verdict(result).values())


def test_verdict_fails_on_slow_or_unanswered_requests(result):
    result["rounds"]["external"][0].update(seconds=12.0, timed_out=True)
    for sample in result["rounds"]["external"][1:3]:
        sample.update(outcome=lt.NO_ANSWER + "timeout", kind=lt.ERROR, expected=False)
    checks = lt.verdict(result)
    assert not checks["none without an answer after 10 s"]
    assert "Unexpected answers:" in lt.report(result)


def test_report_flags_a_warm_cache(result):
    result["rounds"]["external"][0]["kind"] = lt.CACHED
    assert "1 known products of the external round were already cached" in lt.report(result)


def test_main_reports_a_saved_run(result, tmp_path, capsys):
    saved = tmp_path / "q2.json"
    saved.write_text(json.dumps(result), encoding="utf-8")
    assert lt.main(["--from", str(saved)]) == 0
    assert "# Q2 load test: https://api.test" in capsys.readouterr().out

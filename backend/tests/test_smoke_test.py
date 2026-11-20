"""The staging smoke test (#72), against a faked staging: no network."""

import responses

from scripts import smoke_test as smoke

API, APP = "https://api.test", "https://app.test"
COMMIT = "abc1234def"


def photo_product(result="product"):
    return {
        "result": result,
        "product": {
            "serving": {
                "size_text": "1 tbsp (15 ml)",
                "source": "nutrition_label_photo",
                "certainty": "uncertain",
            },
            "nutrition": {
                "nutrients": {
                    "sodium": {
                        "amount": 780,
                        "source": "nutrition_label_photo",
                        "certainty": "uncertain",
                    },
                    "sugars": {"amount": 4, "source": "open_food_facts", "certainty": "reported"},
                }
            },
        },
    }


def fake_staging(app_commit=COMMIT, first_photo_status=200, photos=True):
    """Register every request the smoke test makes, as a healthy staging answers them."""
    responses.get(f"{API}/api/health", json={"status": "ok", "commit": COMMIT})
    responses.get(f"{APP}/", body='<script src="/_expo/static/js/web/index-1.js"></script>')
    responses.get(f"{APP}/_expo/static/js/web/index-1.js", body=f'var commit="{app_commit}";')
    responses.add(
        responses.OPTIONS,
        f"{API}/api/analysis/label-photo",
        headers={"Access-Control-Allow-Origin": APP},
    )
    responses.post(f"{API}/api/barcode", json={"barcode": "013000006408", "format": "UPCA"})
    responses.get(
        f"{API}/api/analysis/{smoke.KETCHUP}",
        json={"product": {"name": "Tomato Ketchup"}, "next_step": {"action": "use_database"}},
    )
    if photos:
        fake_photo_checks(first_photo_status)
    responses.get(
        f"{API}/api/analysis/123",
        status=400,
        json={"error": {"code": "invalid_barcode", "message": "bad"}},
    )
    responses.post(
        f"{API}/api/analysis/label-photo",
        status=400,
        json={"error": {"code": "invalid_image", "message": "bad"}},
    )


def fake_photo_checks(first_photo_status):
    responses.get(
        f"{API}/api/analysis/{smoke.OYSTER_SAUCE}",
        json={"next_step": {"action": "request_nutrition_photo"}},
    )
    if first_photo_status != 200:
        responses.post(
            f"{API}/api/analysis/label-photo",
            status=first_photo_status,
            json={"error": {"code": "upstream_timeout", "message": "slow"}},
        )
    responses.post(f"{API}/api/analysis/label-photo", json=photo_product())
    responses.post(f"{API}/api/analysis/confirm", json=photo_product())
    responses.get(
        f"{API}/api/analysis/{smoke.UNKNOWN}",
        status=404,
        json={"error": {"code": "product_not_found", "message": "not found"}},
    )
    responses.post(f"{API}/api/analysis/label-photo", json=photo_product("nutrition_only"))


def run(**kwargs):
    return {o.name: o for o in smoke.SmokeTest(API, APP, wake_seconds=0, pause=0).run(**kwargs)}


@responses.activate
def test_every_check_passes_on_a_healthy_staging():
    fake_staging()

    outcomes = run()

    assert [name for name, o in outcomes.items() if not o.passed] == []
    assert len(outcomes) == 8


@responses.activate
def test_an_app_built_from_another_commit_fails_that_check_only():
    fake_staging(app_commit="0000000")

    outcomes = run()

    assert not outcomes["App built from the same commit"].passed
    assert "abc1234def" in outcomes["App built from the same commit"].detail
    assert all(o.passed for name, o in outcomes.items() if name != "App built from the same commit")


@responses.activate
def test_a_slow_vision_model_is_retried_once():
    fake_staging(first_photo_status=504)

    assert run()["Incomplete product + label photo"].passed


@responses.activate
def test_a_backend_that_does_not_answer_stops_the_run():
    responses.get(f"{API}/api/health", status=503)

    outcomes = run()

    assert list(outcomes) == ["Backend up"]
    assert not outcomes["Backend up"].passed


@responses.activate
def test_skip_photos_leaves_out_the_vision_model():
    fake_staging(photos=False)

    outcomes = run(photos=False)

    assert "Incomplete product + label photo" not in outcomes
    assert all(o.passed for o in outcomes.values())


def test_confirm_all_marks_only_uncertain_photo_values():
    product = smoke.confirm_all(photo_product()["product"])

    assert product["serving"]["certainty"] == "user_confirmed"
    assert product["nutrition"]["nutrients"]["sodium"]["certainty"] == "user_confirmed"
    assert product["nutrition"]["nutrients"]["sugars"]["certainty"] == "reported"


@responses.activate
def test_main_exits_1_and_prints_the_table_when_a_check_fails(capsys):
    responses.get(f"{API}/api/health", status=503)

    assert smoke.main(["--api", API, "--app", APP, "--wake-seconds", "0"]) == 1
    assert "| Backend up | FAIL |" in capsys.readouterr().out

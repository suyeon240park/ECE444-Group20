"""Smoke test of the deployed app (#72): run it after a deploy and before the demo.

Against staging by default, it checks that

1. the backend is up (it waits for a sleeping Render instance to wake) and the app was
   built from the same commit;
2. the app's origin may call the API (CORS);
3. a barcode photo gives its barcode;
4. a complete product needs no label photo;
5. an incomplete product asks for one, and a label photo plus confirmation completes it;
6. an unknown barcode is "not found", and a label photo gives a nutrition-only result;
7. bad input gets the documented errors.

Checks 5 and 6 send two label photos to the vision model on the server. ``--skip-photos``
leaves them out, for example when the free quota is used up.

Run from ``backend/``::

    python -m scripts.smoke_test
    python -m scripts.smoke_test --api http://localhost:5000 --app http://localhost:8081

Exit status: 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

API = "https://whats-in-my-food-api.onrender.com"
APP = "https://whats-in-my-food.onrender.com"

REPO = Path(__file__).resolve().parents[2]
TEST_BARCODE = REPO / "docs" / "images" / "test-barcode.png"
LABELS = REPO / "tests" / "fixtures" / "nutrition_labels" / "images"

KETCHUP = "0013000006408"  # complete in Open Food Facts
OYSTER_SAUCE = "4891130005418"  # per-100 g data only; photo 010 is its label
UNKNOWN = "0620009999909"  # valid check digit, not in Open Food Facts

# A sleeping Render instance takes about a minute to wake.
WAKE_SECONDS = 120
TIMEOUT = 30
# The vision model may take 60 s per model it tries; the server allows 180 s.
PHOTO_TIMEOUT = 200

_BUNDLE = re.compile(r"/_expo/static/js/web/[^\"']+\.js")


class CheckFailed(Exception):
    pass


@dataclass(frozen=True)
class Outcome:
    name: str
    passed: bool
    detail: str


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


def error_code(response: requests.Response) -> str | None:
    try:
        return response.json()["error"]["code"]
    except (ValueError, KeyError, TypeError):
        return None


def confirm_all(product: Any) -> Any:
    """``product`` with every label-photo value marked as checked by the user."""
    if isinstance(product, dict):
        marked = {key: confirm_all(value) for key, value in product.items()}
        if (
            marked.get("source") == "nutrition_label_photo"
            and marked.get("certainty") == "uncertain"
        ):
            marked["certainty"] = "user_confirmed"
        return marked
    if isinstance(product, list):
        return [confirm_all(value) for value in product]
    return product


class SmokeTest:
    def __init__(self, api: str, app: str, wake_seconds: float = WAKE_SECONDS, pause: float = 5):
        self.api = api.rstrip("/")
        self.app = app.rstrip("/")
        self.wake_seconds = wake_seconds
        self.pause = pause
        self.http = requests.Session()
        self.commit: str | None = None

    # --- helpers -------------------------------------------------------------------

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.http.get(self.api + path, timeout=TIMEOUT, **kwargs)

    def label_photo(self, photo: Path, barcode: str | None = None) -> requests.Response:
        """POST a label photo, retrying once if the vision model was busy or slow."""
        data = {"barcode": barcode} if barcode else {}

        def send() -> requests.Response:
            with photo.open("rb") as image:
                return self.http.post(
                    self.api + "/api/analysis/label-photo",
                    files={"image": (photo.name, image, "image/jpeg")},
                    data=data,
                    timeout=PHOTO_TIMEOUT,
                )

        response = send()
        return send() if response.status_code in (502, 504) else response

    # --- checks --------------------------------------------------------------------

    def backend_up(self) -> str:
        deadline = time.monotonic() + self.wake_seconds
        while True:
            try:
                response = self.get("/api/health")
                if response.ok and response.json().get("status") == "ok":
                    self.commit = response.json().get("commit")
                    return f"commit {self.commit}"
            except requests.RequestException:
                pass
            if time.monotonic() >= deadline:
                raise CheckFailed(f"/api/health not ok after {self.wake_seconds:.0f} s")
            time.sleep(self.pause)

    def app_same_commit(self) -> str:
        page = self.http.get(self.app + "/", timeout=TIMEOUT)
        expect(page.ok, f"app answered {page.status_code}")
        bundle = _BUNDLE.search(page.text)
        expect(bundle is not None, "no JavaScript bundle on the app page")
        script = self.http.get(self.app + bundle.group(), timeout=TIMEOUT).text
        expect(
            bool(self.commit) and self.commit in script, f"app build is not commit {self.commit}"
        )
        return f"app build {self.commit}"

    def cors(self) -> str:
        response = self.http.options(
            self.api + "/api/analysis/label-photo",
            headers={"Origin": self.app, "Access-Control-Request-Method": "POST"},
            timeout=TIMEOUT,
        )
        allowed = response.headers.get("Access-Control-Allow-Origin")
        expect(allowed in (self.app, "*"), f"Access-Control-Allow-Origin is {allowed!r}")
        return f"allows {allowed}"

    def barcode_photo(self) -> str:
        with TEST_BARCODE.open("rb") as image:
            response = self.http.post(
                self.api + "/api/barcode",
                files={"image": (TEST_BARCODE.name, image, "image/png")},
                timeout=TIMEOUT,
            )
        expect(response.status_code == 200, f"/api/barcode answered {response.status_code}")
        found = response.json().get("barcode")
        expect(found in (KETCHUP, KETCHUP[1:]), f"read {found!r}")
        return f"read {found}"

    def complete_product(self) -> str:
        response = self.get(f"/api/analysis/{KETCHUP}")
        expect(response.status_code == 200, f"answered {response.status_code}")
        body = response.json()
        action = (body.get("next_step") or {}).get("action")
        expect(action == "use_database", f"next step is {action!r}")
        return f"{body['product'].get('name')}: no photo needed"

    def incomplete_product(self) -> str:
        response = self.get(f"/api/analysis/{OYSTER_SAUCE}")
        expect(response.status_code == 200, f"lookup answered {response.status_code}")
        action = (response.json().get("next_step") or {}).get("action")
        expect(action == "request_nutrition_photo", f"next step is {action!r}")

        photo = self.label_photo(LABELS / "010_dark-sauce.jpg", OYSTER_SAUCE)
        expect(
            photo.status_code == 200,
            f"label photo answered {photo.status_code} {error_code(photo)}",
        )
        reading = photo.json()
        expect(
            reading.get("result") == "product", f"label photo result is {reading.get('result')!r}"
        )

        confirmed = self.http.post(
            self.api + "/api/analysis/confirm",
            json={"result": reading["result"], "product": confirm_all(reading["product"])},
            timeout=TIMEOUT,
        )
        expect(
            confirmed.status_code == 200,
            f"confirm answered {confirmed.status_code} {error_code(confirmed)}",
        )
        serving = confirmed.json()["product"]["serving"].get("size_text")
        return f"asked for a photo; label read and confirmed (serving {serving})"

    def unknown_product(self) -> str:
        response = self.get(f"/api/analysis/{UNKNOWN}")
        expect(response.status_code == 404, f"lookup answered {response.status_code}")
        expect(error_code(response) == "product_not_found", f"error is {error_code(response)!r}")

        photo = self.label_photo(LABELS / "005_crackers.jpg")
        expect(
            photo.status_code == 200,
            f"label photo answered {photo.status_code} {error_code(photo)}",
        )
        result = photo.json().get("result")
        expect(result == "nutrition_only", f"label photo result is {result!r}")
        return "not found; label photo gave a nutrition-only result"

    def bad_input(self) -> str:
        response = self.get("/api/analysis/123")
        expect(
            error_code(response) == "invalid_barcode",
            f"short barcode gave {error_code(response)!r}",
        )
        upload = self.http.post(
            self.api + "/api/analysis/label-photo",
            files={"image": ("photo.jpg", b"not an image", "image/jpeg")},
            timeout=TIMEOUT,
        )
        expect(
            error_code(upload) == "invalid_image", f"non-image upload gave {error_code(upload)!r}"
        )
        return "invalid_barcode and invalid_image"

    def run(self, photos: bool = True) -> list[Outcome]:
        checks: list[tuple[str, Callable[[], str]]] = [
            ("Backend up", self.backend_up),
            ("App built from the same commit", self.app_same_commit),
            ("CORS for the app", self.cors),
            ("Barcode photo", self.barcode_photo),
            ("Complete product", self.complete_product),
        ]
        if photos:
            checks += [
                ("Incomplete product + label photo", self.incomplete_product),
                ("Unknown barcode + label photo", self.unknown_product),
            ]
        checks.append(("Bad input", self.bad_input))

        outcomes = []
        for name, check in checks:
            try:
                outcomes.append(Outcome(name, True, check()))
            except (CheckFailed, requests.RequestException, ValueError, KeyError) as exc:
                outcomes.append(Outcome(name, False, str(exc) or type(exc).__name__))
            if name == "Backend up" and not outcomes[-1].passed:
                break  # nothing else can pass
        return outcomes


def report(outcomes: Sequence[Outcome], api: str, app: str) -> str:
    lines = [f"Smoke test: {api} / {app}", "", "| Check | Result | Detail |", "|---|---|---|"]
    lines += [f"| {o.name} | {'PASS' if o.passed else 'FAIL'} | {o.detail} |" for o in outcomes]
    passed = sum(o.passed for o in outcomes)
    lines += ["", f"{passed}/{len(outcomes)} checks passed."]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default=API, help=f"backend URL (default {API})")
    parser.add_argument("--app", default=APP, help=f"app URL (default {APP})")
    parser.add_argument("--skip-photos", action="store_true", help="leave out the two label photos")
    parser.add_argument(
        "--wake-seconds",
        type=float,
        default=WAKE_SECONDS,
        help=f"how long to wait for a sleeping backend (default {WAKE_SECONDS})",
    )
    args = parser.parse_args(argv)

    smoke = SmokeTest(args.api, args.app, wake_seconds=args.wake_seconds)
    outcomes = smoke.run(photos=not args.skip_photos)
    sys.stdout.write(report(outcomes, args.api, args.app))
    return 0 if all(o.passed for o in outcomes) and outcomes else 1


if __name__ == "__main__":
    sys.exit(main())

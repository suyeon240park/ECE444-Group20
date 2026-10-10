import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "off"


def load_off(name: str) -> dict:
    """A full Open Food Facts v3 response body from tests/fixtures/off/."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def off_response():
    return load_off


@pytest.fixture
def off_product():
    """Just the ``product`` object of a found fixture, as the client returns it."""
    return lambda name: load_off(name)["product"]

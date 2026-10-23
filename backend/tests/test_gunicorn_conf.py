import runpy
from pathlib import Path

from app.services.label_extraction import VisionConfig
from app.services.label_reading import DEFAULT_FALLBACK_MODELS

CONF = Path(__file__).resolve().parents[1] / "gunicorn.conf.py"


def test_binds_to_render_port(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    assert runpy.run_path(str(CONF))["bind"] == "0.0.0.0:10000"


def test_timeout_outlasts_a_photo_on_every_vision_model():
    models = 1 + len(DEFAULT_FALLBACK_MODELS.split(","))
    vision_timeout = VisionConfig.__dataclass_fields__["timeout_seconds"].default
    assert runpy.run_path(str(CONF))["timeout"] >= models * vision_timeout

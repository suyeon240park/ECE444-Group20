"""Read a Nutrition Facts photo into the product contract (#42).

The photo is checked and made upright by ``load_image`` (#13), shrunk so the upload
to the model stays fast, read by the vision-model prototype (#16), and turned into
the contract's ``Serving``, ``Package`` and ``Nutrition`` (#20).

Every value from a photo is ``uncertain``: the model gives no per-value confidence,
so Q1's safe-use rule needs the user to confirm values before F2/F3 may use them.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.models.product import (
    ALL_NUTRIENTS,
    Certainty,
    NutrientValue,
    Nutrition,
    NutritionBasis,
    Package,
    Serving,
    Source,
)
from app.services.barcode import BarcodeError, load_image
from app.services.label_extraction import (
    Extraction,
    LabelExtractionError,
    LabelExtractionTimeout,
    VisionConfig,
    extract_label,
)

logger = logging.getLogger(__name__)

# Longest side sent to the model. Plenty for a Nutrition Facts table; a full-size
# phone photo took about twice as long to read in the #16 benchmark.
MAX_EDGE_PIXELS = 2000
JPEG_QUALITY = 85

# ISO base media "ftyp" brands used by iPhone HEIC/HEIF photos. Pillow cannot open
# them, so they are refused by name instead of failing as a generic invalid image.
HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}

# Tried in order when VISION_MODEL is overloaded (503), rate limited (429) or retired
# (404). Both read fixture photos 005, 007 and 008 correctly on Oct 14, while
# gemini-3.5-flash was answering 503 "high demand" to image requests.
DEFAULT_FALLBACK_MODELS = "gemini-3-flash-preview,gemini-3.5-flash-lite"

PHOTO = Source.NUTRITION_LABEL_PHOTO
UNCONFIRMED = Certainty.UNCERTAIN


def parse_models(value: str, primary: str) -> tuple[str, ...]:
    """``"a, b,a"`` → ``("a", "b")``, without blanks, repeats or the primary model."""
    models: list[str] = []
    for name in value.split(","):
        name = name.strip()
        if name and name != primary and name not in models:
            models.append(name)
    return tuple(models)


def _give_up(_seconds: float) -> None:
    raise LabelExtractionError("the vision model is rate limited")


def extract_without_waiting(image: bytes, mime_type: str, config: VisionConfig) -> Extraction:
    """``extract_label`` without its 30-second rate-limit waits.

    The benchmark CLI waits out a free-tier rate limit; a user waiting on a request
    should get a 502 they can retry instead.
    """
    return extract_label(image, mime_type, config, sleep=_give_up)


class LabelReadingError(Exception):
    """A failure with a stable ``code`` and the HTTP status the route returns."""

    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class LabelReading:
    """What a Nutrition Facts photo says, in the contract's types."""

    serving: Serving
    package: Package
    nutrition: Nutrition


def prepare_photo(data: bytes) -> bytes:
    """Validate the upload and return an upright JPEG no larger than ``MAX_EDGE_PIXELS``."""
    if is_heif(data):
        raise LabelReadingError(
            "unsupported_media_type",
            "HEIC/HEIF photos are not supported. Upload a JPEG, PNG or WEBP.",
            415,
        )
    try:
        image = load_image(data)
    except BarcodeError as error:
        raise LabelReadingError(error.code, error.message, error.status) from None
    if image.mode != "RGB":  # JPEG has no alpha or palette; PNG/WEBP uploads may
        image = image.convert("RGB")
    image.thumbnail((MAX_EDGE_PIXELS, MAX_EDGE_PIXELS))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def is_heif(data: bytes) -> bool:
    return data[4:8] == b"ftyp" and data[8:12] in HEIF_BRANDS


def to_contract(result: dict[str, Any]) -> LabelReading:
    """Turn the prototype's normalized result into contract objects, all unconfirmed.

    A nutrient whose amount could not be read is left ``None`` even if its %DV was
    read: the contract stores a %DV only next to an amount.
    """
    serving_in = result.get("serving") or {}
    size_text, quantity, unit = (serving_in.get(k) for k in ("size_text", "quantity", "unit"))
    has_serving = any(v is not None for v in (size_text, quantity, unit))
    serving = Serving(size_text, quantity, unit, PHOTO, UNCONFIRMED) if has_serving else Serving()

    servings = (result.get("package") or {}).get("servings_per_package")
    package = (
        Package(servings_per_package=servings, source=PHOTO, certainty=UNCONFIRMED)
        if servings is not None
        else Package()
    )

    nutrients_in = (result.get("nutrition") or {}).get("nutrients") or {}
    nutrients: dict[str, NutrientValue | None] = {}
    for name in ALL_NUTRIENTS:
        value = nutrients_in.get(name)
        if value and value.get("amount") is not None:
            nutrients[name] = NutrientValue(
                value["amount"],
                value["unit"],
                PHOTO,
                UNCONFIRMED,
                daily_value_percent=value.get("daily_value_percent"),
            )
    nutrition = (
        Nutrition(NutritionBasis.SERVING, nutrients)
        if any(v is not None for v in nutrients.values())
        else Nutrition()
    )
    return LabelReading(serving, package, nutrition)


class LabelReader:
    """Reads label photos with the vision model; ``config`` is None without an API key.

    If ``config.model`` fails, each of ``fallback_models`` is tried in turn with the
    same key. A timeout is not retried on another model: the user has already waited
    ``timeout_seconds``.
    """

    def __init__(
        self,
        config: VisionConfig | None,
        extract: Callable[[bytes, str, VisionConfig], Extraction] = extract_without_waiting,
        fallback_models: Sequence[str] = (),
    ) -> None:
        self._config = config
        self._extract = extract
        self._fallback_models = tuple(fallback_models)

    def read(self, data: bytes) -> LabelReading:
        if self._config is None:
            raise LabelReadingError(
                "photo_reading_unavailable",
                "Reading label photos is not configured on this server.",
                503,
            )
        photo = prepare_photo(data)
        extraction = self._extract_with_fallback(photo, self._config)

        if extraction.result.get("status") == "not_found":
            raise LabelReadingError(
                "nutrition_table_not_found",
                "No Nutrition Facts table was found. Retake the photo with the whole table "
                "flat, in focus and in frame.",
                422,
            )
        if extraction.result.get("unreadable_fields") or extraction.result.get("rejected_fields"):
            logger.info(
                "Label photo read with gaps: unreadable=%s rejected=%s",
                extraction.result.get("unreadable_fields"),
                extraction.result.get("rejected_fields"),
            )
        return to_contract(extraction.result)

    def _extract_with_fallback(self, photo: bytes, config: VisionConfig) -> Extraction:
        for model in (config.model, *self._fallback_models):
            try:
                extraction = self._extract(photo, "image/jpeg", replace(config, model=model))
            except LabelExtractionTimeout:
                logger.warning("Label photo extraction timed out on %s", model)
                raise LabelReadingError(
                    "upstream_timeout", "The label-reading service did not respond in time.", 504
                ) from None
            except LabelExtractionError as error:
                logger.warning("Label photo extraction failed on %s: %s", model, error)
                continue
            if model != config.model:
                logger.info("Label photo read by fallback model %s", model)
            return extraction
        raise LabelReadingError(
            "upstream_unavailable",
            "The label-reading service is unavailable. Try again shortly.",
            502,
        )

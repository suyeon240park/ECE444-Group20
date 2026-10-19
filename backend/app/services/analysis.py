"""Product-analysis pipeline (#43): every section the results page (#41) shows, in one result.

The response extends the product contract (#20): ``result``, ``completeness``,
``missing_fields`` and ``product`` keep their meaning, and four sections follow:

- ``next_step``: #15's routing decision for a barcode lookup; ``None`` for a photo result.
- ``package_nutrition``: per-serving and whole-package nutrition (#36, F2).
- ``explanations``: per-serving %DV, its 5% / 15% reading and the reviewed nutrient
  explanations (#37, F3).
- ``ingredients``: ingredient analysis (#33, F4).

Each section is computed on its own. A section that fails is logged and returned as
``None``, so a missing ingredient list or a broken knowledge base never hides the
nutrition, and the reverse.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from app.models.ingredients import IngredientAnalysisResult
from app.models.package_nutrition import PackageNutritionResult
from app.models.product import Certainty, Product, ProductResult
from app.services.fallback_routing import RoutingDecision
from app.services.ingredient_analysis import IngredientAnalysisService
from app.services.nutrient_content import NutrientContent
from app.services.nutrient_explanations import NutrientExplanationResult, explain_nutrients
from app.services.package_nutrition import calculate_package_nutrition

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class AnalysisResult:
    product: ProductResult
    next_step: RoutingDecision | None
    package_nutrition: PackageNutritionResult | None
    explanations: NutrientExplanationResult | None
    ingredients: IngredientAnalysisResult | None

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.product.to_dict(),
            "next_step": _next_step_dict(self.next_step),
            "package_nutrition": _dict_or_none(self.package_nutrition),
            "explanations": _dict_or_none(self.explanations),
            "ingredients": _dict_or_none(self.ingredients),
        }


def _dict_or_none(section: Any) -> dict[str, Any] | None:
    return None if section is None else section.to_dict()


def _next_step_dict(decision: RoutingDecision | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "action": decision.action.value,
        "reason": decision.reason.value,
        "product_identified": decision.product_identified,
        "photo_fields": list(decision.photo_fields),
        "can_retry_lookup": decision.can_retry_lookup,
    }


def confirmed_paths(product: Product) -> list[str]:
    """The ``user_confirmed`` values as the dotted paths #36's ``confirmed`` takes."""
    paths = []
    if product.serving.certainty is Certainty.USER_CONFIRMED:
        paths.append("serving")
    if product.package.certainty is Certainty.USER_CONFIRMED:
        paths += ["package.servings_per_package", "package.quantity"]
    for name, value in product.nutrition.nutrients.items():
        if value is not None and value.certainty is Certainty.USER_CONFIRMED:
            paths.append(f"nutrition.nutrients.{name}")
    return paths


class AnalysisService:
    """Builds an ``AnalysisResult``.

    ``ingredients`` is None if the knowledge base did not load, and
    ``nutrient_content`` is None if the reviewed nutrient content did not; that
    section is then always ``None``.
    """

    def __init__(
        self,
        ingredients: IngredientAnalysisService | None,
        nutrient_content: NutrientContent | None = None,
    ) -> None:
        self._ingredients = ingredients
        self._nutrient_content = nutrient_content

    def analyze(
        self, result: ProductResult, next_step: RoutingDecision | None = None
    ) -> AnalysisResult:
        product = result.product
        confirmed = confirmed_paths(product)
        package_nutrition = _section(
            "package_nutrition",
            lambda: calculate_package_nutrition(product, confirmed=confirmed),
        )
        content = self._nutrient_content
        explanations = (
            _section("explanations", lambda: explain_nutrients(product, content, confirmed))
            if content is not None
            else None
        )
        ingredients = (
            _section("ingredients", lambda: self._ingredients.analyze(product))
            if self._ingredients is not None
            else None
        )
        return AnalysisResult(result, next_step, package_nutrition, explanations, ingredients)


def _section(name: str, compute: Callable[[], T]) -> T | None:
    try:
        return compute()
    except Exception:
        # Deliberately broad: one broken section must not take down the others.
        logger.exception("Analysis section %s failed", name)
        return None

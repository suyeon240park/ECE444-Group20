"""Pure F4 analysis service for the future #43 pipeline; no network or Flask I/O."""

from app.models.ingredients import (
    IngredientAnalysisResult,
    IngredientOccurrence,
    IngredientStatus,
    MatchedIngredient,
    UnmatchedIngredient,
)
from app.models.product import Product, Source
from app.services.ingredient_knowledge import IngredientKnowledgeBase
from app.services.ingredient_names import normalize_name
from app.services.ingredient_parser import parse_ingredients


class IngredientAnalysisService:
    def __init__(self, knowledge: IngredientKnowledgeBase):
        self.knowledge = knowledge

    def analyze(self, product: Product) -> IngredientAnalysisResult:
        text = product.ingredients_text
        if product.source.provider is not Source.OPEN_FOOD_FACTS or not text or not text.strip():
            return IngredientAnalysisResult(IngredientStatus.UNAVAILABLE)
        parsed = parse_ingredients(text, self.knowledge)
        matched: dict[str, list[IngredientOccurrence]] = {}
        unmatched: dict[str, list[IngredientOccurrence]] = {}
        for candidate in parsed.candidates:
            entry = (
                None if candidate.force_unmatched else self.knowledge.match(candidate.lookup_text)
            )
            occurrence = IngredientOccurrence(candidate.text, candidate.path)
            if entry:
                matched.setdefault(entry.id, []).append(occurrence)
            else:
                key = normalize_name(candidate.lookup_text)
                unmatched.setdefault(key, []).append(occurrence)
        return IngredientAnalysisResult(
            IngredientStatus.ANALYZED if matched else IngredientStatus.NO_MATCHES,
            tuple(
                MatchedIngredient(self.knowledge.entries[key], tuple(value))
                for key, value in matched.items()
            ),
            tuple(UnmatchedIngredient(value[0].text, tuple(value)) for value in unmatched.values()),
            parsed.warnings,
        )

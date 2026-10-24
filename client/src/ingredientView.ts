import type {
  IngredientAnalysisResult,
  IngredientAuthority,
  IngredientEntry,
  IngredientFlagCategory,
  IngredientSource,
} from './ingredients';

/** How many flagged ingredients the summary shows before "Show N more" (#40). */
export const FLAGGED_PREVIEW_COUNT = 3;

export const CATEGORY_LABELS: Record<IngredientFlagCategory, string> = {
  authority_action: 'A regulator has acted on this',
  conflicting_assessments: 'Authorities disagree',
};

export const AUTHORITY_LABELS: Record<IngredientAuthority, string> = {
  health_canada: 'Health Canada',
  efsa: 'European Food Safety Authority (EFSA)',
  fda: 'U.S. Food and Drug Administration (FDA)',
  who_jecfa: 'WHO/FAO expert committee on food additives (JECFA)',
};

/** The flagged ingredients, in the order the label lists them. */
export function flaggedEntries(result: IngredientAnalysisResult): IngredientEntry[] {
  return result.flagged_ids
    .map((id) => result.matched.find((m) => m.ingredient.id === id)?.ingredient)
    .filter((entry): entry is IngredientEntry => entry !== undefined);
}

/** Ingredients that were checked and have no flag. This is not a verdict that they are fine. */
export function unflaggedEntries(result: IngredientAnalysisResult): IngredientEntry[] {
  const flagged = new Set(result.flagged_ids);
  return result.matched.map((m) => m.ingredient).filter((entry) => !flagged.has(entry.id));
}

export function findEntry(
  result: IngredientAnalysisResult | null,
  id: string,
): IngredientEntry | undefined {
  return result?.matched.find((m) => m.ingredient.id === id)?.ingredient;
}

/** The entry's sources with the given ids, in the order asked for; unknown ids are skipped. */
export function sourcesFor(entry: IngredientEntry, ids: string[]): IngredientSource[] {
  return ids
    .map((id) => entry.sources.find((source) => source.id === id))
    .filter((source): source is IngredientSource => source !== undefined);
}

/**
 * The product contract (#20) and the analysis response (#43) the results page (#41) reads.
 * Shapes are `ProductResult` and `AnalysisResult` in docs/api/openapi.yaml; the rules for
 * using them are in docs/api/analysis.md.
 */
import type { IngredientAnalysisResult } from './ingredients';
import type { NutrientExplanationResult } from './nutrientExplanations';
import type { NutrientName, NutrientValue, PackageNutritionResult } from './packageNutrition';

export type DataSource = 'open_food_facts' | 'nutrition_label_photo';

export type Product = {
  barcode: string | null;
  name: string | null;
  brand: string | null;
  ingredients_text: string | null;
  nutrition: {
    basis: 'serving' | '100g' | '100ml' | null;
    nutrients: Record<NutrientName, NutrientValue | null>;
  };
  source: {
    provider: DataSource;
    url: string | null;
    retrieved_at: string;
    last_modified_at: string | null;
  };
};

export type NextStep = {
  action: 'use_database' | 'request_nutrition_photo' | 'nutrition_only_photo' | 'retake_barcode_photo';
  reason: string;
  product_identified: boolean;
  photo_fields: string[];
  can_retry_lookup: boolean;
};

export type AnalysisResult = {
  result: 'product' | 'nutrition_only';
  completeness: 'complete' | 'incomplete';
  /** Dotted paths of what a full analysis still lacks, such as `serving.size_text`. */
  missing_fields: string[];
  product: Product;
  /** Null when the result came from a photo. */
  next_step: NextStep | null;
  /** Each of these is null when its section failed on the server; the others still stand. */
  package_nutrition: PackageNutritionResult | null;
  explanations: NutrientExplanationResult | null;
  ingredients: IngredientAnalysisResult | null;
};

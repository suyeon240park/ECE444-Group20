/**
 * The product contract (#20) and the analysis endpoints (#43) the confirm screen
 * (#39) needs. Shapes are `ProductResult`, `AnalysisResult` and `ConfirmationRequest`
 * in docs/api/openapi.yaml.
 */
import { API_BASE_URL } from './api';
import type { IngredientAnalysisResult } from './ingredients';
import type { NutrientExplanationResult } from './nutrientExplanations';
import type { NutrientName, NutrientValue, PackageNutritionResult } from './packageNutrition';

export type Source = 'open_food_facts' | 'nutrition_label_photo';
export type Certainty = NutrientValue['certainty'];

export type Serving = {
  size_text: string | null;
  quantity: number | null;
  unit: 'g' | 'ml' | null;
  source: Source | null;
  certainty: Certainty | null;
};

export type Package = {
  quantity_text: string | null;
  quantity: number | null;
  unit: 'g' | 'ml' | null;
  servings_per_package: number | null;
  source: Source | null;
  certainty: Certainty | null;
};

export type Product = {
  barcode: string | null;
  name: string | null;
  brand: string | null;
  ingredients_text: string | null;
  serving: Serving;
  package: Package;
  nutrition: {
    basis: 'serving' | '100g' | '100ml' | null;
    nutrients: Record<NutrientName, NutrientValue | null>;
  };
  source: {
    provider: Source;
    url: string | null;
    retrieved_at: string;
    last_modified_at: string | null;
  };
};

export type ProductResult = {
  result: 'product' | 'nutrition_only';
  completeness: 'complete' | 'incomplete';
  missing_fields: string[];
  product: Product;
};

export type AnalysisResult = ProductResult & {
  next_step: unknown;
  package_nutrition: PackageNutritionResult | null;
  explanations: NutrientExplanationResult | null;
  ingredients: IngredientAnalysisResult | null;
};

export type ConfirmationRequest = Pick<ProductResult, 'result' | 'product'>;

export type ConfirmOutcome =
  { kind: 'ok'; analysis: AnalysisResult } | { kind: 'error'; code: string; message: string };

const CONFIRM_TIMEOUT_MS = 15_000;

/** POST /api/analysis/confirm: re-analyze a photo result after the user checked it. */
export async function confirmPhotoValues(request: ConfirmationRequest): Promise<ConfirmOutcome> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CONFIRM_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}/api/analysis/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal: controller.signal,
    });
    const body: unknown = await response.json().catch(() => null);
    if (response.ok && body) {
      return { kind: 'ok', analysis: body as AnalysisResult };
    }
    const error = (body as { error?: { code?: string; message?: string } } | null)?.error;
    return {
      kind: 'error',
      code: error?.code ?? 'unexpected_response',
      message: error?.message ?? `The server answered ${response.status}.`,
    };
  } catch {
    return controller.signal.aborted
      ? {
          kind: 'error',
          code: 'timeout',
          message: 'The server did not answer in time. Try again.',
        }
      : {
          kind: 'error',
          code: 'network_error',
          message: 'Could not reach the server. Try again.',
        };
  } finally {
    clearTimeout(timer);
  }
}

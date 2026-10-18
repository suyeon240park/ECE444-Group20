/** #36 contract (`PackageNutritionResult` in docs/api/openapi.yaml) for #41/#43. */
export type NutrientName =
  | 'calories'
  | 'total_fat'
  | 'saturated_fat'
  | 'sodium'
  | 'carbohydrate'
  | 'sugars'
  | 'fibre'
  | 'protein'
  | 'trans_fat'
  | 'cholesterol';

export type NutrientValue = {
  amount: number;
  unit: 'kcal' | 'g' | 'mg';
  /** The %DV printed on the label; never a calculated one. */
  daily_value_percent: number | null;
  source: 'open_food_facts' | 'nutrition_label_photo';
  certainty: 'reported' | 'confident' | 'uncertain';
};

export type WholePackageAmount = {
  /** Unrounded; show `display_amount`. */
  amount: number;
  unit: 'kcal' | 'g' | 'mg';
  display_amount: number;
  daily_value_percent: number | null;
  display_daily_value_percent: number | null;
};

export type WholePackageStatus = 'calculated' | 'not_available' | 'needs_confirmation';

export type PackageNutrientRow = {
  name: NutrientName;
  per_serving: NutrientValue | null;
  whole_package: WholePackageAmount | null;
  whole_package_status: WholePackageStatus;
};

export type NotCalculatedReason =
  | 'no_per_serving_nutrition'
  | 'no_package_information'
  | 'no_serving_quantity'
  | 'incompatible_units'
  | 'package_smaller_than_serving'
  | 'unconfirmed_photo_values';

export type PackageNutritionResult = {
  status: 'calculated' | 'not_calculated';
  per_serving_label: string | null;
  whole_package_label: string | null;
  servings: number | null;
  display_servings: number | null;
  method: 'servings_per_package' | 'package_quantity' | null;
  approximate: boolean;
  approximate_label: 'Approximate' | null;
  /** Shown once with the whole-package column; never on each row. */
  daily_value_label: 'Calculated for whole package' | null;
  reason: NotCalculatedReason | null;
  message: string | null;
  pending_confirmation: string[];
  rows: PackageNutrientRow[];
};

export const NUTRIENT_LABELS: Record<NutrientName, string> = {
  calories: 'Calories',
  total_fat: 'Fat',
  saturated_fat: 'Saturated fat',
  trans_fat: 'Trans fat',
  cholesterol: 'Cholesterol',
  sodium: 'Sodium',
  carbohydrate: 'Carbohydrate',
  fibre: 'Fibre',
  sugars: 'Sugars',
  protein: 'Protein',
};

export const NOT_AVAILABLE = 'Not available';

/** Per-serving amounts are shown as the source states them. */
export function formatAmount(amount: number, unit: string): string {
  return unit === 'kcal' ? `${amount}` : `${amount} ${unit}`;
}

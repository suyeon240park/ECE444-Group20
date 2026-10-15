/** #37 contract (`NutrientExplanationResult` in docs/api/openapi.yaml) for #41/#43. */
import type { NutrientName, NutrientValue } from './packageNutrition';

export type ExplanationSource = {
  id: string;
  publisher: string;
  title: string;
  url: string;
};

export type ExplanationText = {
  text: string;
  sources: ExplanationSource[];
};

export type PerServingDailyValue = {
  percent: number;
  display_percent: number;
  origin: 'label' | 'calculated';
  label: 'Calculated' | null;
  interpretation: 'a_little' | 'a_lot' | null;
  interpretation_text: 'a little' | 'a lot' | null;
};

export type NutrientExplanationRow = {
  name: NutrientName;
  display_name: string;
  guidance: 'limit' | 'get_more' | 'neutral';
  value: NutrientValue | null;
  status: 'verified' | 'not_available' | 'needs_confirmation';
  status_text: string | null;
  daily_value: PerServingDailyValue | null;
  what_it_is: ExplanationText | null;
  how_to_read: ExplanationText | null;
  explanation_message: 'No verified explanation available yet.' | null;
};

export type NutrientExplanationResult = {
  basis: 'serving' | '100g' | '100ml' | null;
  /** Shown with every amount: "per serving", "per 100 g" or "per 100 mL". */
  basis_label: 'per serving' | 'per 100 g' | 'per 100 mL' | null;
  /** Per-100 g / 100 mL data only: why the amounts are not per serving and have no %DV. */
  basis_note: string | null;
  daily_values_reference: { title: string; url: string; version: string };
  daily_value_definition: (ExplanationText & { term: string }) | null;
  rows: NutrientExplanationRow[];
};

/**
 * Confirming values read from a Nutrition Facts photo (#39, Q1 safe-use rule).
 *
 * The vision model gives no per-value confidence, so every value it reads must be
 * confirmed or corrected by the user before #36 (whole-package totals) or #37
 * (explanations) may use it. The confirmed paths returned here are the ones those
 * services take as `confirmed`.
 */
import { NUTRIENT_LABELS, type NutrientName } from './packageNutrition';

/** A photo reading, as `backend/app/services/label_extraction.py` returns it (#16/#42). */
export type LabelNutrient = {
  amount: number | null;
  unit: string | null;
  daily_value_percent: number | null;
};

export type LabelReading =
  | { status: 'not_found' }
  | {
      status: 'found';
      serving: {
        size_text: string | null;
        household: string | null;
        quantity: number | null;
        unit: 'g' | 'ml' | null;
      };
      package: { servings_per_package: number | null };
      nutrition: {
        basis: 'serving' | null;
        nutrients: Partial<Record<NutrientName, LabelNutrient | null>>;
      };
      unreadable_fields: string[];
    };

export const SERVING_PATH = 'serving';
export const SERVINGS_PER_PACKAGE_PATH = 'package.servings_per_package';
export const nutrientPath = (name: NutrientName) => `nutrition.nutrients.${name}`;

/** Table order of the Canadian Nutrition Facts table. */
export const LABEL_ORDER: NutrientName[] = [
  'calories',
  'total_fat',
  'saturated_fat',
  'trans_fat',
  'cholesterol',
  'sodium',
  'carbohydrate',
  'fibre',
  'sugars',
  'protein',
];

const UNITS: Record<NutrientName, string> = {
  calories: 'kcal',
  total_fat: 'g',
  saturated_fat: 'g',
  trans_fat: 'g',
  cholesterol: 'mg',
  sodium: 'mg',
  carbohydrate: 'g',
  fibre: 'g',
  sugars: 'g',
  protein: 'g',
};

/** Nutrients printed with a %DV on the Canadian label; saturated fat carries saturated + trans. */
const DV_ON_LABEL = new Set<NutrientName>(['total_fat', 'saturated_fat', 'sodium', 'fibre', 'sugars']);

/** One editable row. Text fields keep what the user typed; numbers are parsed on use. */
export type Field = {
  path: string;
  label: string;
  unit: string | null;
  amountText: string;
  /** Null for nutrients the label prints without a %DV. */
  dvText: string | null;
  /** Serving size and servings per package multiply everything else. */
  highlighted: boolean;
  unreadable: boolean;
  confirmed: boolean;
};

const toText = (value: number | null | undefined) => (value == null ? '' : String(value));

export function buildFields(reading: Extract<LabelReading, { status: 'found' }>): Field[] {
  const unreadable = new Set(reading.unreadable_fields);
  const isUnreadable = (path: string) =>
    [...unreadable].some((p) => p === path || p.startsWith(`${path}.`));
  const fields: Field[] = [
    {
      path: SERVING_PATH,
      label: reading.serving.size_text ? `Serving size (${reading.serving.size_text})` : 'Serving size',
      unit: reading.serving.unit,
      amountText: toText(reading.serving.quantity),
      dvText: null,
      highlighted: true,
      unreadable: isUnreadable(SERVING_PATH),
      confirmed: false,
    },
    {
      path: SERVINGS_PER_PACKAGE_PATH,
      label: 'Servings per package',
      unit: null,
      amountText: toText(reading.package.servings_per_package),
      dvText: null,
      highlighted: true,
      unreadable: isUnreadable(SERVINGS_PER_PACKAGE_PATH),
      confirmed: false,
    },
  ];
  for (const name of LABEL_ORDER) {
    const value = reading.nutrition.nutrients[name] ?? null;
    fields.push({
      path: nutrientPath(name),
      label: NUTRIENT_LABELS[name],
      unit: UNITS[name],
      amountText: toText(value?.amount),
      dvText: DV_ON_LABEL.has(name) ? toText(value?.daily_value_percent) : null,
      highlighted: false,
      unreadable: isUnreadable(nutrientPath(name)),
      confirmed: false,
    });
  }
  return fields;
}

/** A non-negative number, or null for an empty field; `undefined` when the text is invalid. */
export function parseNumber(text: string): number | null | undefined {
  const trimmed = text.trim().replace(',', '.');
  if (trimmed === '') return null;
  if (!/^\d+(\.\d+)?$/.test(trimmed)) return undefined;
  return Number(trimmed);
}

export function fieldError(field: Field): string | null {
  const amount = parseNumber(field.amountText);
  if (amount === undefined) return 'Enter a number, for example 12 or 2.5.';
  const positiveOnly = field.path === SERVING_PATH || field.path === SERVINGS_PER_PACKAGE_PATH;
  if (positiveOnly && amount === 0) return 'This must be more than 0.';
  if (field.path === SERVING_PATH && amount !== null && field.unit === null) {
    return 'Choose g or mL for the serving size.';
  }
  if (field.dvText !== null && parseNumber(field.dvText) === undefined) {
    return 'Enter the %DV as a number, for example 8.';
  }
  return null;
}

/** An empty field has nothing to confirm; an invalid one must be fixed first. */
export const canConfirm = (field: Field) =>
  fieldError(field) === null && parseNumber(field.amountText) !== null;

export type ConfirmedReading = {
  serving: { quantity: number | null; unit: 'g' | 'ml' | null };
  servings_per_package: number | null;
  nutrients: Partial<Record<NutrientName, LabelNutrient | null>>;
  /** Pass these to #36/#37 as `confirmed`. Unconfirmed values are not in this list. */
  confirmed: string[];
};

/** The values as the user left them, and which of them the user confirmed. */
export function buildConfirmedReading(fields: Field[]): ConfirmedReading {
  const byPath = new Map(fields.map((f) => [f.path, f]));
  const amount = (path: string) => parseNumber(byPath.get(path)?.amountText ?? '') ?? null;
  const nutrients: ConfirmedReading['nutrients'] = {};
  for (const name of LABEL_ORDER) {
    const field = byPath.get(nutrientPath(name));
    const value = amount(nutrientPath(name));
    const dv = field?.dvText != null ? (parseNumber(field.dvText) ?? null) : null;
    nutrients[name] =
      value === null && dv === null
        ? null
        : { amount: value, unit: value === null ? null : UNITS[name], daily_value_percent: dv };
  }
  const serving = byPath.get(SERVING_PATH);
  return {
    serving: {
      quantity: amount(SERVING_PATH),
      unit: (serving?.unit as 'g' | 'ml' | null | undefined) ?? null,
    },
    servings_per_package: amount(SERVINGS_PER_PACKAGE_PATH),
    nutrients,
    confirmed: fields.filter((f) => f.confirmed && canConfirm(f)).map((f) => f.path),
  };
}

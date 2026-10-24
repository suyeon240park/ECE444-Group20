/**
 * Confirming values read from a Nutrition Facts photo (#39, Q1 safe-use rule).
 *
 * The photo endpoints (#42/#43) mark every value they read `uncertain`: the vision
 * model gives no per-value confidence. The user checks each value against the label,
 * corrects it if needed, and confirms it. `buildConfirmationRequest` turns that into
 * the body of `POST /api/analysis/confirm`, with checked values `user_confirmed` and
 * the rest still `uncertain`, so #36 and #37 use only what the user checked.
 *
 * Only label-photo values are editable. Database values are never shown here: the
 * server keeps its own copy of them anyway.
 */
import type { ConfirmationRequest, Package, Product, ProductResult, Serving } from './analysis';
import { NUTRIENT_LABELS, type NutrientName, type NutrientValue } from './packageNutrition';

export const SERVING_PATH = 'serving';
export const PACKAGE_PATH = 'package';
export const nutrientPath = (name: NutrientName) => `nutrition.nutrients.${name}`;

const PHOTO = 'nutrition_label_photo';

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

const UNITS: Record<NutrientName, NutrientValue['unit']> = {
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
const DV_ON_LABEL = new Set<NutrientName>([
  'total_fat',
  'saturated_fat',
  'sodium',
  'fibre',
  'sugars',
]);

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
  /** Nothing was read from the photo for this row. */
  unread: boolean;
  confirmed: boolean;
};

const toText = (value: number | null | undefined) => (value == null ? '' : String(value));
const isPhoto = (value: { source: string | null } | null | undefined) => value?.source === PHOTO;

/**
 * The rows to show for a photo result.
 *
 * - `nutrition_only`: every value came from the photo, so every row is shown; a value
 *   the photo did not give is an empty row the user may fill in.
 * - `product`: only the photo's values and the gaps the database leaves are shown.
 *   The serving appears only if it came from the photo: adding one would replace the
 *   database's whole nutrition. A database value is never shown for editing.
 */
export function buildFields(result: ProductResult): Field[] {
  const { product } = result;
  const nutritionOnly = result.result === 'nutrition_only';
  const fields: Field[] = [];

  if (nutritionOnly || isPhoto(product.serving)) {
    fields.push({
      path: SERVING_PATH,
      label: product.serving.size_text
        ? `Serving size (${product.serving.size_text})`
        : 'Serving size',
      unit: product.serving.unit,
      amountText: toText(product.serving.quantity),
      dvText: null,
      highlighted: true,
      unread: product.serving.quantity == null,
      confirmed: product.serving.certainty === 'user_confirmed',
    });
  }
  if (nutritionOnly || isPhoto(product.package) || product.package.servings_per_package == null) {
    fields.push({
      path: PACKAGE_PATH,
      label: 'Servings per package',
      unit: null,
      amountText: isPhoto(product.package) ? toText(product.package.servings_per_package) : '',
      dvText: null,
      highlighted: true,
      unread: !isPhoto(product.package) || product.package.servings_per_package == null,
      confirmed: isPhoto(product.package) && product.package.certainty === 'user_confirmed',
    });
  }
  for (const name of LABEL_ORDER) {
    const value = product.nutrition.nutrients[name];
    if (value != null && !isPhoto(value)) continue;
    fields.push({
      path: nutrientPath(name),
      label: NUTRIENT_LABELS[name],
      unit: UNITS[name],
      amountText: toText(value?.amount),
      dvText: DV_ON_LABEL.has(name) ? toText(value?.daily_value_percent) : null,
      highlighted: false,
      unread: value == null,
      confirmed: value?.certainty === 'user_confirmed',
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
  const positiveOnly = field.path === SERVING_PATH || field.path === PACKAGE_PATH;
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

const certaintyOf = (field: Field) =>
  field.confirmed && canConfirm(field) ? ('user_confirmed' as const) : ('uncertain' as const);

const EMPTY_SERVING: Serving = {
  size_text: null,
  quantity: null,
  unit: null,
  source: null,
  certainty: null,
};

const EMPTY_PACKAGE: Package = {
  quantity_text: null,
  quantity: null,
  unit: null,
  servings_per_package: null,
  source: null,
  certainty: null,
};

/**
 * The body for `POST /api/analysis/confirm`: the result with the user's values, each
 * photo value `user_confirmed` if the user confirmed it and `uncertain` otherwise.
 * An emptied field is sent as missing.
 */
export function buildConfirmationRequest(
  result: ProductResult,
  fields: Field[],
): ConfirmationRequest {
  const product: Product = JSON.parse(JSON.stringify(result.product));
  for (const field of fields) {
    const amount = parseNumber(field.amountText) ?? null;
    if (field.path === SERVING_PATH) {
      product.serving =
        amount === null
          ? { ...EMPTY_SERVING }
          : {
              size_text: product.serving.size_text,
              quantity: amount,
              unit: field.unit as Serving['unit'],
              source: PHOTO,
              certainty: certaintyOf(field),
            };
    } else if (field.path === PACKAGE_PATH) {
      if (amount !== null) {
        const photoPackage: Package = {
          quantity_text: null,
          quantity: null,
          unit: null,
          servings_per_package: amount,
          source: PHOTO,
          certainty: certaintyOf(field),
        };
        product.package = photoPackage;
      } else if (isPhoto(product.package)) {
        product.package = { ...EMPTY_PACKAGE };
      }
    } else {
      const name = field.path.slice('nutrition.nutrients.'.length) as NutrientName;
      const dv = field.dvText === null ? null : (parseNumber(field.dvText) ?? null);
      product.nutrition.nutrients[name] =
        amount === null
          ? null
          : {
              amount,
              unit: UNITS[name],
              daily_value_percent: dv,
              source: PHOTO,
              certainty: certaintyOf(field),
            };
    }
  }
  if (Object.values(product.nutrition.nutrients).some((v) => v != null)) {
    product.nutrition.basis = product.nutrition.basis ?? 'serving';
  }
  return { result: result.result, product };
}

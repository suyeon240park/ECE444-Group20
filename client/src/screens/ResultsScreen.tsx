import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import IngredientSection from '../components/IngredientSection';
import NutrientExplanationList from '../components/NutrientExplanationList';
import PackageNutritionTable from '../components/PackageNutritionTable';

import PerBasisNutritionTable from '../components/PerBasisNutritionTable';
import Section, { Unavailable } from '../components/Section';
import StatusCard from '../components/StatusCard';
import { formatDate, joinWords } from '../format';

import { NOT_AVAILABLE, NUTRIENT_LABELS, type NutrientName } from '../packageNutrition';
import type { AnalysisResult, DataSource } from '../productResult';

const EXPLANATIONS_UNAVAILABLE = 'No verified explanation available yet.';

/** Where the data came from, with the date it was retrieved. */
function sourceLine(provider: DataSource, retrievedAt: string): string {
  const date = formatDate(retrievedAt);
  return provider === 'open_food_facts'
    ? `Data from Open Food Facts, retrieved ${date}.`
    : `Read from your Nutrition Facts photo on ${date}.`;
}


/** A missing-data path from the API in words a shopper would use. */
export function describeMissing(path: string): string {
  const nutrientPrefix = 'nutrition.nutrients.';
  if (path.startsWith(nutrientPrefix)) {
    const name = path.slice(nutrientPrefix.length) as NutrientName;
    return (NUTRIENT_LABELS[name] ?? name).toLowerCase();
  }
  switch (path) {
    case 'name':
      return 'product name';
    case 'ingredients_text':
      return 'ingredient list';
    case 'serving.size_text':
      return 'serving size';
    case 'nutrition.basis':
      return 'whether the nutrition values are per serving or per 100 g';
    default:
      return path;
  }
}


/** What the analysis does have, in words a shopper would use (#45). */
export function describeShown(analysis: AnalysisResult): string[] {
  const { product } = analysis;
  const shown: string[] = [];
  if (analysis.result === 'product' && product.name) {
    shown.push('product name');
  }
  const values = Object.values(product.nutrition.nutrients).some((value) => value !== null);
  if (values) {
    const basis = product.nutrition.basis;
    shown.push(
      analysis.result === 'nutrition_only'
        ? 'nutrition values read from your photo'
        : basis === '100g'
          ? 'nutrition values per 100 g'
          : basis === '100ml'
            ? 'nutrition values per 100 ml'
            : basis === 'serving'
              ? 'nutrition values per serving'
              : 'nutrition values',
    );
  }
  if (analysis.package_nutrition?.status === 'calculated') {
    shown.push('whole-package amounts');
  }
  if (analysis.explanations && analysis.explanations.rows.length > 0) {
    shown.push('nutrient explanations');
  }
  if (analysis.ingredients && analysis.ingredients.status !== 'unavailable') {
    shown.push('ingredient check');
  }
  return shown;
}

/** The sections the server could not provide at all (they came back null). */
export function describeFailedSections(analysis: AnalysisResult): string[] {
  const failed: string[] = [];
  if (analysis.package_nutrition === null) {
    failed.push('nutrition');
  }
  if (analysis.explanations === null) {
    failed.push('nutrient explanations');
  }
  if (analysis.ingredients === null) {
    failed.push('ingredients');
  }
  return failed;
}


type Props = {
  analysis: AnalysisResult;
  /** Go back to the scan screen. */
  onScanAnother: () => void;
  /** Open the detail view for one checked ingredient. */
  onOpenIngredient: (ingredientId: string) => void;

  /** Look the product up again; given only when there is a barcode to look up. */
  onRetry?: () => void;

};

/**
 * The whole analysis for one product on one page (#41): who the product is and where the
 * data came from, nutrition per serving and for the whole package, what each nutrient
 * means, and the ingredient summary. Each section stands alone, so one the server could
 * not provide says so and the rest still show. There is no overall score, grade or verdict.
 */

export default function ResultsScreen({
  analysis,
  onScanAnother,
  onOpenIngredient,
  onRetry,
}: Props) {
  const { product } = analysis;
  const nutritionOnly = analysis.result === 'nutrition_only';
  const pending = analysis.package_nutrition?.pending_confirmation ?? [];
  const failedSections = describeFailedSections(analysis);
  const shown = describeShown(analysis);
  const nutrition = analysis.package_nutrition;
  // No serving size, but the database lists values per 100 g: show those, labelled, rather
  // than a table of "Not available".
  const basis = product.nutrition.basis;
  const perBasis =
    nutrition?.reason === 'no_per_serving_nutrition' && (basis === '100g' || basis === '100ml')
      ? basis
      : null;


  return (
    <View style={styles.container}>
      <Section
        title={nutritionOnly ? 'Nutrition-only result' : (product.name ?? 'Unnamed product')}
        subtitle={
          nutritionOnly
            ? "We couldn't identify the product, so this shows only the values read from your photo."
            : (product.brand ?? 'Brand not available')
        }
      >
        {product.barcode ? <Text style={styles.meta}>Barcode {product.barcode}</Text> : null}
        <Text style={styles.meta}>
          {sourceLine(product.source.provider, product.source.retrieved_at)}
        </Text>
        {product.source.url ? (
          <Text
            accessibilityRole="link"
            style={styles.link}
            onPress={() => void Linking.openURL(product.source.url as string)}
          >
            View this product on Open Food Facts
          </Text>
        ) : null}
      </Section>

      {analysis.missing_fields.length > 0 ? (

        <StatusCard
          kind="notice"
          title="Some information is missing"
          message={`Missing: ${analysis.missing_fields.map(describeMissing).join(', ')}.`}
          lines={[
            shown.length > 0
              ? `Still shown: ${joinWords(shown)}.`
              : 'There is nothing else to show for this product.',
            ...(pending.length > 0
              ? [
                  'Values read from a photo are shown, but not used in totals or explanations until you confirm them.',
                ]
              : []),
          ]}
        />
      ) : null}

      {failedSections.length > 0 ? (
        <StatusCard
          kind="error"
          title="Part of the analysis didn't load"
          message={`We couldn't get ${joinWords(failedSections)} from the server. The rest is shown below.`}
          actions={onRetry ? [{ label: 'Try again', onPress: onRetry, primary: true }] : []}
        />

      ) : null}

      <Section
        title="Nutrition"

        subtitle={
          perBasis
            ? 'Amounts as the food database lists them.'
            : 'Per serving is what the label states. Whole package is calculated from it.'
        }
      >
        {nutrition && perBasis ? (
          <PerBasisNutritionTable
            basis={perBasis}
            nutrients={product.nutrition.nutrients}
            order={nutrition.rows.map((row) => row.name)}
          />
        ) : nutrition ? (
          <PackageNutritionTable result={nutrition} />

        ) : (
          <Unavailable message={NOT_AVAILABLE} />
        )}
      </Section>

      <Section title="What the nutrients mean">
        {analysis.explanations ? (
          <NutrientExplanationList result={analysis.explanations} />
        ) : (
          <Unavailable message={EXPLANATIONS_UNAVAILABLE} />
        )}
      </Section>

      <Section title="Ingredients">
        <IngredientSection result={analysis.ingredients} onOpen={onOpenIngredient} />

      </Section>

      <Pressable
        accessibilityRole="button"
        onPress={onScanAnother}
        style={({ pressed }) => [styles.button, pressed && styles.buttonDim]}
      >
        <Text style={styles.buttonText}>Scan another product</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignSelf: 'stretch', gap: 16 },
  meta: { color: '#555' },
  link: { color: '#1b7f3b', textDecorationLine: 'underline' },

  button: {
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1b7f3b',
    backgroundColor: '#1b7f3b',
    alignItems: 'center',
  },
  buttonDim: { opacity: 0.6 },
  buttonText: { color: '#fff', fontWeight: '600' },
});

import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import IngredientSection from '../components/IngredientSection';
import NutrientExplanationList from '../components/NutrientExplanationList';
import PackageNutritionTable from '../components/PackageNutritionTable';
import Section, { Unavailable } from '../components/Section';
import { formatDate } from '../format';

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

type Props = {
  analysis: AnalysisResult;
  /** Go back to the scan screen. */
  onScanAnother: () => void;
  /** Open the detail view for one checked ingredient. */
  onOpenIngredient: (ingredientId: string) => void;

};

/**
 * The whole analysis for one product on one page (#41): who the product is and where the
 * data came from, nutrition per serving and for the whole package, what each nutrient
 * means, and the ingredient summary. Each section stands alone, so one the server could
 * not provide says so and the rest still show. There is no overall score, grade or verdict.
 */
export default function ResultsScreen({ analysis, onScanAnother, onOpenIngredient }: Props) {

  const { product } = analysis;
  const nutritionOnly = analysis.result === 'nutrition_only';
  const pending = analysis.package_nutrition?.pending_confirmation ?? [];

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
        <View style={styles.notice} accessibilityLiveRegion="polite">
          <Text style={styles.noticeTitle}>Some information is missing</Text>
          <Text style={styles.noticeBody}>
            Everything we have is shown below. Still missing or unconfirmed:{' '}
            {analysis.missing_fields.map(describeMissing).join(', ')}.
          </Text>
          {pending.length > 0 ? (
            <Text style={styles.noticeBody}>
              Values read from a photo are shown, but not used in totals or explanations until you
              confirm them.
            </Text>
          ) : null}
        </View>
      ) : null}

      <Section
        title="Nutrition"
        subtitle="Per serving is what the label states. Whole package is calculated from it."
      >
        {analysis.package_nutrition ? (
          <PackageNutritionTable result={analysis.package_nutrition} />
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
  notice: {
    gap: 4,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e0b252',
    backgroundColor: '#fff6e5',
  },
  noticeTitle: { fontWeight: '600', color: '#7a4b00' },
  noticeBody: { color: '#7a4b00', lineHeight: 20 },
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

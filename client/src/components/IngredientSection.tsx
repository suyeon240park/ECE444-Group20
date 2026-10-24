import { StyleSheet, Text, View } from 'react-native';

import type { IngredientAnalysisResult, IngredientFlagCategory } from '../ingredients';
import { Unavailable } from './Section';

/** Shown when there is no ingredient result at all, or no ingredient list to check. */
export const INGREDIENTS_UNAVAILABLE = 'Ingredient information not available';

const CATEGORY_LABELS: Record<IngredientFlagCategory, string> = {
  authority_action: 'A regulator has acted on this',
  conflicting_assessments: 'Authorities disagree',
};

type Props = { result: IngredientAnalysisResult | null };

/**
 * The ingredient summary (F4): how many ingredients were checked, which were flagged and
 * why, and which are not in the reviewed database yet. It never says an ingredient is
 * "safe" and gives no overall verdict. #40 adds the three-item collapse and the detail view.
 */
export default function IngredientSection({ result }: Props) {
  if (!result || result.status === 'unavailable') {
    return <Unavailable message={result?.message ?? INGREDIENTS_UNAVAILABLE} />;
  }

  const flagged = result.flagged_ids
    .map((id) => result.matched.find((m) => m.ingredient.id === id)?.ingredient)
    .filter((entry) => entry !== undefined);

  return (
    <View style={styles.container}>
      {result.coverage_text ? <Text style={styles.coverage}>{result.coverage_text}</Text> : null}
      {result.message ? <Text style={styles.body}>{result.message}</Text> : null}

      {flagged.map((entry) =>
        entry.flag ? (
          <View key={entry.id} style={styles.flag}>
            <Text style={styles.flagName}>{entry.name}</Text>
            <Text style={styles.flagCategory}>{CATEGORY_LABELS[entry.flag.category]}</Text>
            <Text style={styles.body}>{entry.flag.flag_reason}</Text>
          </View>
        ) : null,
      )}

      {result.unmatched.length > 0 ? (
        <View style={styles.unmatched}>
          <Text style={styles.unmatchedTitle}>Not in our database yet</Text>
          <Text style={styles.body}>{result.unmatched.map((u) => u.text).join(', ')}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignSelf: 'stretch', gap: 12 },
  coverage: { color: '#1a1a1a', fontWeight: '600', lineHeight: 20 },
  body: { color: '#333', lineHeight: 20 },
  flag: {
    gap: 2,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e0b252',
    backgroundColor: '#fff6e5',
  },
  flagName: { fontWeight: '600', color: '#1a1a1a' },
  flagCategory: { color: '#7a4b00', fontSize: 12 },
  unmatched: { gap: 2 },
  unmatchedTitle: { fontWeight: '600', color: '#1a1a1a' },
});

import { StyleSheet, Text, View } from 'react-native';

import {
  formatAmount,
  NOT_AVAILABLE,
  NUTRIENT_LABELS,
  type NutrientName,
  type NutrientValue,
} from '../packageNutrition';

type Props = {
  basis: '100g' | '100ml';
  nutrients: Record<NutrientName, NutrientValue | null>;
  /** The nutrients in the order the other table lists them. */
  order: NutrientName[];
};

const BASIS_AMOUNT = { '100g': '100 g', '100ml': '100 ml' } as const;

/**
 * Nutrition for products whose database record gives values per 100 g (or 100 ml) and no
 * serving size (#45). Per-serving and whole-package amounts cannot be worked out from it, so
 * this shows what the database has, labelled for what it is, instead of a table of "Not
 * available".
 */
export default function PerBasisNutritionTable({ basis, nutrients, order }: Props) {
  const amount = BASIS_AMOUNT[basis];
  return (
    <View style={styles.container}>
      <Text style={styles.message}>
        These amounts are per {amount}. The serving size is missing, so amounts per serving and
        for the whole package cannot be worked out.
      </Text>

      <View style={[styles.row, styles.header]}>
        <Text style={[styles.cell, styles.name, styles.headerText]}>Nutrient</Text>
        <Text style={[styles.cell, styles.headerText]}>Per {amount}</Text>
      </View>

      {order.map((name) => {
        const value = nutrients[name];
        return (
          <View key={name} style={styles.row}>
            <Text style={[styles.cell, styles.name]}>{NUTRIENT_LABELS[name]}</Text>
            {value ? (
              <Text style={[styles.cell, styles.amount]}>
                {formatAmount(value.amount, value.unit)}
              </Text>
            ) : (
              <Text style={[styles.cell, styles.muted]}>{NOT_AVAILABLE}</Text>
            )}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignSelf: 'stretch', gap: 8 },
  message: { color: '#555', lineHeight: 20 },
  row: { flexDirection: 'row', gap: 8, borderBottomWidth: 1, borderBottomColor: '#e2e5e2' },
  header: { borderBottomColor: '#1a1a1a' },
  headerText: { fontWeight: '600', color: '#1a1a1a' },
  cell: { flex: 1, paddingVertical: 8 },
  name: { flex: 1.2 },
  amount: { fontWeight: '600', color: '#1a1a1a' },
  muted: { color: '#777' },
});

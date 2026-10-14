import { StyleSheet, Text, View } from 'react-native';

import {
  formatAmount,
  NOT_AVAILABLE,
  NUTRIENT_LABELS,
  type PackageNutrientRow,
  type PackageNutritionResult,
} from '../packageNutrition';

type Props = { result: PackageNutritionResult };

/**
 * Per-serving and whole-package nutrition side by side (#36, F2). The labelled serving
 * view is always shown; the whole-package column appears only when it was calculated.
 */
export default function PackageNutritionTable({ result }: Props) {
  const calculated = result.status === 'calculated';
  return (
    <View style={styles.container}>
      {result.approximate_label ? (
        <Text style={styles.approximate}>
          {result.approximate_label}: about {result.display_servings} servings, worked out from
          the package size and serving size.
        </Text>
      ) : null}
      {result.message ? <Text style={styles.message}>{result.message}</Text> : null}

      <View style={[styles.row, styles.header]}>
        <Text style={[styles.cell, styles.name, styles.headerText]}>Nutrient</Text>
        <Text style={[styles.cell, styles.headerText]}>
          {result.per_serving_label ?? 'Per serving'}
        </Text>
        {calculated ? (
          <Text style={[styles.cell, styles.headerText]}>
            {result.whole_package_label}
            {result.approximate ? ' (approximate)' : ''}
          </Text>
        ) : null}
      </View>

      {result.rows.map((row) => (
        <View key={row.name} style={styles.row}>
          <Text style={[styles.cell, styles.name]}>{NUTRIENT_LABELS[row.name]}</Text>
          <PerServingCell row={row} />
          {calculated ? <WholePackageCell row={row} /> : null}
        </View>
      ))}
    </View>
  );
}

function PerServingCell({ row }: { row: PackageNutrientRow }) {
  const value = row.per_serving;
  if (!value) {
    return <Text style={[styles.cell, styles.muted]}>{NOT_AVAILABLE}</Text>;
  }
  return (
    <View style={styles.cell}>
      <Text style={styles.amount}>{formatAmount(value.amount, value.unit)}</Text>
      {value.daily_value_percent !== null ? (
        <Text style={styles.note}>{value.daily_value_percent}% DV</Text>
      ) : null}
    </View>
  );
}

function WholePackageCell({ row }: { row: PackageNutrientRow }) {
  const whole = row.whole_package;
  if (row.whole_package_status === 'needs_confirmation') {
    return <Text style={[styles.cell, styles.muted]}>Confirm the photo value first</Text>;
  }
  if (!whole) {
    return <Text style={[styles.cell, styles.muted]}>{NOT_AVAILABLE}</Text>;
  }
  return (
    <View style={styles.cell}>
      <Text style={styles.amount}>{formatAmount(whole.display_amount, whole.unit)}</Text>
      {whole.display_daily_value_percent !== null ? (
        <Text style={styles.note}>
          {whole.display_daily_value_percent}% DV · {whole.daily_value_label}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignSelf: 'stretch', gap: 8 },
  approximate: {
    color: '#7a4b00',
    backgroundColor: '#fff6e5',
    borderRadius: 8,
    padding: 8,
    lineHeight: 20,
  },
  message: { color: '#555', lineHeight: 20 },
  row: {
    flexDirection: 'row',
    gap: 8,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e5e2',
  },
  header: { borderBottomColor: '#1a1a1a' },
  headerText: { fontWeight: '600', color: '#1a1a1a' },
  cell: { flex: 1 },
  name: { color: '#1a1a1a' },
  amount: { color: '#1a1a1a', fontWeight: '600' },
  note: { color: '#555', fontSize: 12 },
  muted: { color: '#777' },
});

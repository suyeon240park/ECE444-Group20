import { Linking, StyleSheet, Text, View } from 'react-native';

import type {
  ExplanationText,
  NutrientExplanationResult,
  NutrientExplanationRow,
} from '../nutrientExplanations';
import { formatAmount } from '../packageNutrition';

type Props = { result: NutrientExplanationResult };

/**
 * Each nutrient with its per-serving %DV, Health Canada's "a little" / "a lot" reading,
 * and its sourced explanation (#37, F3). No overall score is shown.
 */
export default function NutrientExplanationList({ result }: Props) {
  const definition = result.daily_value_definition;
  return (
    <View style={styles.container}>
      {result.basis_note ? <Text style={styles.basisNote}>{result.basis_note}</Text> : null}
      {definition ? (
        <View style={styles.definition}>
          <Text style={styles.definitionTerm}>{definition.term}</Text>
          <Text style={styles.body}>{definition.text}</Text>
          <Sources text={definition} />
        </View>
      ) : null}
      {result.rows.map((row) => (
        <NutrientCard key={row.name} row={row} basisLabel={result.basis_label} />
      ))}
    </View>
  );
}

function NutrientCard({
  row,
  basisLabel,
}: {
  row: NutrientExplanationRow;
  basisLabel: string | null;
}) {
  const dv = row.daily_value;
  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.name}>{row.display_name}</Text>
        <View style={styles.amountBox}>
          <Text style={styles.amount}>
            {row.value ? formatAmount(row.value.amount, row.value.unit) : row.status_text}
          </Text>
          {row.value && basisLabel ? <Text style={styles.basis}>{basisLabel}</Text> : null}
        </View>
      </View>
      {dv ? (
        <Text style={styles.dv}>
          {dv.display_percent}% DV
          {dv.label ? ` (${dv.label})` : ''}
          {dv.interpretation_text ? `: ${dv.interpretation_text}` : ''}
        </Text>
      ) : null}
      {row.status === 'needs_confirmation' ? (
        <Text style={styles.warning}>{row.status_text}</Text>
      ) : null}
      {row.what_it_is ? <Explanation text={row.what_it_is} /> : null}
      {row.how_to_read ? <Explanation text={row.how_to_read} /> : null}
      {row.explanation_message ? <Text style={styles.muted}>{row.explanation_message}</Text> : null}
    </View>
  );
}

function Explanation({ text }: { text: ExplanationText }) {
  return (
    <View style={styles.explanation}>
      <Text style={styles.body}>{text.text}</Text>
      <Sources text={text} />
    </View>
  );
}

function Sources({ text }: { text: ExplanationText }) {
  return (
    <View style={styles.sources}>
      {text.sources.map((source) => (
        <Text
          key={source.id}
          accessibilityRole="link"
          style={styles.link}
          onPress={() => void Linking.openURL(source.url)}
        >
          Source: {source.publisher}, {source.title}
        </Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignSelf: 'stretch', gap: 12 },
  definition: { backgroundColor: '#f1faf3', borderRadius: 8, padding: 12, gap: 4 },
  definitionTerm: { fontWeight: '600', color: '#1a1a1a' },
  card: { borderWidth: 1, borderColor: '#e2e5e2', borderRadius: 8, padding: 12, gap: 6 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  name: { fontWeight: '600', color: '#1a1a1a', flexShrink: 1 },
  amountBox: { alignItems: 'flex-end' },
  amount: { color: '#1a1a1a', fontWeight: '600' },
  basis: { color: '#555', fontSize: 12 },
  basisNote: {
    color: '#7a4b00',
    backgroundColor: '#fff6e5',
    borderRadius: 8,
    padding: 12,
    lineHeight: 20,
  },
  dv: { color: '#1a1a1a' },
  warning: { color: '#7a4b00' },
  explanation: { gap: 2 },
  body: { color: '#333', lineHeight: 20 },
  sources: { gap: 2 },
  link: { color: '#1b7f3b', fontSize: 12, textDecorationLine: 'underline' },
  muted: { color: '#777' },
});

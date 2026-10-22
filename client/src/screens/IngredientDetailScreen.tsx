import { Pressable, StyleSheet, Text, View } from 'react-native';

import Section from '../components/Section';
import SourceLinks from '../components/SourceLinks';
import { formatDate } from '../format';
import type { IngredientAuthorityPosition, IngredientEntry } from '../ingredients';
import { AUTHORITY_LABELS, CATEGORY_LABELS, sourcesFor } from '../ingredientView';

type Props = {
  entry: IngredientEntry;
  /** Go back to the results page. */
  onBack: () => void;
};

/**
 * One ingredient in detail (#40): what it is, why it is used, an explanation, its sources and
 * when the entry was last reviewed. A flagged ingredient also shows why it is flagged and what
 * each authority said, one position at a time. There is no safe/unsafe verdict.
 */
export default function IngredientDetailScreen({ entry, onBack }: Props) {
  const otherNames = [...entry.aliases, ...entry.e_numbers, ...entry.ins_numbers];

  return (
    <View style={styles.container}>
      <BackButton onBack={onBack} />

      <Section
        title={entry.name}
        subtitle={otherNames.length > 0 ? `Also listed as: ${otherNames.join(', ')}` : undefined}
      >
        {entry.flag ? (
          <View style={styles.flag}>
            <Text style={styles.flagCategory}>{CATEGORY_LABELS[entry.flag.category]}</Text>
            <Text style={styles.body}>{entry.flag.flag_reason}</Text>
            <SourceLinks sources={sourcesFor(entry, entry.flag.source_ids)} />
          </View>
        ) : null}
        <Text style={styles.reviewed}>Last reviewed {formatDate(entry.last_reviewed)}</Text>
      </Section>

      <Section title="What it is">
        <Statement entry={entry} text={entry.what_it_is} />
      </Section>
      <Section title="Why it is used">
        <Statement entry={entry} text={entry.why_used} />
      </Section>
      <Section title="Explanation">
        <Statement entry={entry} text={entry.explanation} />
      </Section>

      {entry.authority_positions.length > 0 ? (
        <Section
          title="What authorities say"
          subtitle="Each position is shown on its own, with what it covers and when it was made."
        >
          {entry.authority_positions.map((position) => (
            <Position key={position.id} entry={entry} position={position} />
          ))}
        </Section>
      ) : null}
    </View>
  );
}

function BackButton({ onBack }: { onBack: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onBack}
      style={({ pressed }) => [styles.button, pressed && styles.dim]}
    >
      <Text style={styles.buttonText}>‹ Back to results</Text>
    </Pressable>
  );
}

function Statement({
  entry,
  text,
}: {
  entry: IngredientEntry;
  text: { text: string; source_ids: string[] };
}) {
  return (
    <View style={styles.statement}>
      <Text style={styles.body}>{text.text}</Text>
      <SourceLinks sources={sourcesFor(entry, text.source_ids)} />
    </View>
  );
}

function Position({
  entry,
  position,
}: {
  entry: IngredientEntry;
  position: IngredientAuthorityPosition;
}) {
  const dates = [
    position.assessed_on ? `Assessed ${formatDate(position.assessed_on)}` : null,
    position.effective_on ? `In effect from ${formatDate(position.effective_on)}` : null,
  ].filter((date) => date !== null);

  return (
    <View style={styles.position}>
      <Text style={styles.authority}>{AUTHORITY_LABELS[position.authority]}</Text>
      <Text style={styles.body}>{position.statement}</Text>
      <Text style={styles.meta}>Applies to: {position.scope}</Text>
      {dates.length > 0 ? <Text style={styles.meta}>{dates.join(' · ')}</Text> : null}
      <SourceLinks sources={sourcesFor(entry, position.source_ids)} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignSelf: 'stretch', gap: 16 },
  body: { color: '#333', lineHeight: 20 },
  meta: { color: '#555', fontSize: 12 },
  reviewed: { color: '#555', fontSize: 12 },
  dim: { opacity: 0.6 },
  statement: { gap: 4 },
  flag: {
    gap: 4,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e0b252',
    backgroundColor: '#fff6e5',
  },
  flagCategory: { color: '#7a4b00', fontWeight: '600' },
  position: { gap: 4, padding: 12, borderRadius: 8, borderWidth: 1, borderColor: '#e2e5e2' },
  authority: { fontWeight: '600', color: '#1a1a1a' },
  button: {
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1b7f3b',
    backgroundColor: '#fff',
    alignItems: 'center',
  },
  buttonText: { color: '#1b7f3b', fontWeight: '600' },
});

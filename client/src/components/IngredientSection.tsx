import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { IngredientAnalysisResult, IngredientEntry } from '../ingredients';
import {
  CATEGORY_LABELS,
  FLAGGED_PREVIEW_COUNT,
  flaggedEntries,
  unflaggedEntries,
} from '../ingredientView';
import { Unavailable } from './Section';

/** Shown when there is no ingredient result at all, or no ingredient list to check. */
export const INGREDIENTS_UNAVAILABLE = 'Ingredient information not available';

const PARSE_NOTE =
  'We had trouble reading part of this ingredient list, so the counts above may not be exact.';

type Props = {
  result: IngredientAnalysisResult | null;
  /** Open the detail view for one checked ingredient. */
  onOpen: (ingredientId: string) => void;
};

/**
 * The ingredient summary (F4, #40): how many ingredients were checked, up to three flagged
 * ones with their reason (the rest behind "Show N more"), the other ingredients that were
 * checked, and the ones not in the reviewed database yet. Every checked ingredient opens its
 * detail view. It never says an ingredient is "safe" and gives no overall verdict.
 */
export default function IngredientSection({ result, onOpen }: Props) {
  const [showAll, setShowAll] = useState(false);

  if (!result || result.status === 'unavailable') {
    return <Unavailable message={result?.message ?? INGREDIENTS_UNAVAILABLE} />;
  }

  const flagged = flaggedEntries(result);
  const shown = showAll ? flagged : flagged.slice(0, FLAGGED_PREVIEW_COUNT);
  const hidden = flagged.length - FLAGGED_PREVIEW_COUNT;
  const others = unflaggedEntries(result);
  const showParseNote = result.warnings.some((warning) => warning.code !== 'ignored_preamble');

  return (
    <View style={styles.container}>
      {result.coverage_text ? <Text style={styles.coverage}>{result.coverage_text}</Text> : null}
      {result.message ? <Text style={styles.body}>{result.message}</Text> : null}
      {showParseNote ? <Text style={styles.muted}>{PARSE_NOTE}</Text> : null}

      {flagged.length > 0 ? (
        <View style={styles.group}>
          <Text style={styles.groupTitle} accessibilityRole="header">
            Flagged ingredients ({flagged.length})
          </Text>
          {shown.map((entry) => (
            <FlaggedCard key={entry.id} entry={entry} onOpen={onOpen} />
          ))}
          {hidden > 0 ? (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ expanded: showAll }}
              onPress={() => setShowAll((value) => !value)}
              style={({ pressed }) => [styles.moreButton, pressed && styles.dim]}
            >
              <Text style={styles.moreText}>{showAll ? 'Show fewer' : `Show ${hidden} more`}</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}

      {others.length > 0 ? (
        <View style={styles.group}>
          <Text style={styles.groupTitle} accessibilityRole="header">
            {flagged.length > 0 ? 'Other ingredients we checked' : 'Ingredients we checked'}
          </Text>
          <View style={styles.pills}>
            {others.map((entry) => (
              <Pressable
                key={entry.id}
                accessibilityRole="button"
                accessibilityHint="Opens the details for this ingredient"
                onPress={() => onOpen(entry.id)}
                style={({ pressed }) => [styles.pill, pressed && styles.dim]}
              >
                <Text style={styles.pillText}>{entry.name}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : null}

      {result.unmatched.length > 0 ? (
        <View style={styles.group}>
          <Text style={styles.groupTitle} accessibilityRole="header">
            Not in our database yet
          </Text>
          <Text style={styles.body}>{result.unmatched.map((u) => u.text).join(', ')}</Text>
        </View>
      ) : null}
    </View>
  );
}

function FlaggedCard({ entry, onOpen }: { entry: IngredientEntry; onOpen: Props['onOpen'] }) {
  if (!entry.flag) {
    return null;
  }
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityHint="Opens the details for this ingredient"
      onPress={() => onOpen(entry.id)}
      style={({ pressed }) => [styles.flag, pressed && styles.dim]}
    >
      <View style={styles.flagHeader}>
        <Text style={styles.flagName}>{entry.name}</Text>
        <Text style={styles.chevron}>›</Text>
      </View>
      <Text style={styles.flagCategory}>{CATEGORY_LABELS[entry.flag.category]}</Text>
      <Text style={styles.body}>{entry.flag.flag_reason}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { alignSelf: 'stretch', gap: 16 },
  group: { gap: 8 },
  groupTitle: { fontWeight: '600', color: '#1a1a1a' },
  coverage: { color: '#1a1a1a', fontWeight: '600', lineHeight: 20 },
  body: { color: '#333', lineHeight: 20 },
  muted: { color: '#777', lineHeight: 20 },
  dim: { opacity: 0.6 },
  flag: {
    gap: 2,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e0b252',
    backgroundColor: '#fff6e5',
  },
  flagHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  flagName: { fontWeight: '600', color: '#1a1a1a', flexShrink: 1 },
  chevron: { color: '#7a4b00', fontSize: 20, lineHeight: 22 },
  flagCategory: { color: '#7a4b00', fontSize: 12 },
  moreButton: {
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1b7f3b',
    backgroundColor: '#fff',
    alignItems: 'center',
  },
  moreText: { color: '#1b7f3b', fontWeight: '600' },
  pills: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  pill: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#cfd6cf',
    backgroundColor: '#fff',
  },
  pillText: { color: '#1a1a1a' },
});

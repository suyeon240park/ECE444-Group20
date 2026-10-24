import { Linking, StyleSheet, Text, View } from 'react-native';

import type { IngredientSource } from '../ingredients';

/** Links to the sources a statement rests on, one per line. */
export default function SourceLinks({ sources }: { sources: IngredientSource[] }) {
  if (sources.length === 0) {
    return null;
  }
  return (
    <View style={styles.sources}>
      {sources.map((source) => (
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
  sources: { gap: 2 },
  link: { color: '#1b7f3b', fontSize: 12, textDecorationLine: 'underline' },
});

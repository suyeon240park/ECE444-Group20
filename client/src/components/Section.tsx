import type { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';

type Props = {
  title: string;
  /** One line under the title saying what the section shows. */
  subtitle?: string;
  children: ReactNode;
};

/** A titled card, so every part of the results page looks the same. */
export default function Section({ title, subtitle, children }: Props) {
  return (
    <View style={styles.card}>
      <Text style={styles.title} accessibilityRole="header">
        {title}
      </Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      {children}
    </View>
  );
}

/** The one line a section shows when the server could not provide it. */
export function Unavailable({ message }: { message: string }) {
  return <Text style={styles.unavailable}>{message}</Text>;
}

const styles = StyleSheet.create({
  card: {
    alignSelf: 'stretch',
    gap: 12,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e2e5e2',
    backgroundColor: '#fff',
  },
  title: { fontSize: 18, fontWeight: '600', color: '#1a1a1a' },
  subtitle: { color: '#555', lineHeight: 20 },
  unavailable: { color: '#777' },
});

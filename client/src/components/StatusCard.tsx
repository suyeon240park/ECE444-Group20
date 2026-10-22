import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

type Action = { label: string; onPress: () => void; primary?: boolean };

/** How long a lookup may wait before the card says it is taking longer than usual. */
const SLOW_AFTER_MS = 8_000;

type Props =
  | {
      kind: 'loading';
      message: string;
      /** Shown instead of `message` once the wait has gone on for a while. */
      slowMessage?: string;
    }
  | {
      /** `error`: something failed. `notice`: partial data. `success`: a step worked. */
      kind: 'error' | 'notice' | 'success';
      title: string;
      message?: string;
      /** More paragraphs under the message. */
      lines?: string[];
      /** What the person can do next, one button each. */
      actions?: Action[];
    };

/**
 * The one look for loading, error, partial-data and success messages, so every screen shows
 * them the same way (#45). An error says what went wrong and offers a next step.
 */
export default function StatusCard(props: Props) {
  if (props.kind === 'loading') {
    return <Loading message={props.message} slowMessage={props.slowMessage} />;
  }
  const tone = TONES[props.kind];
  return (
    <View style={[styles.card, tone.card]} accessibilityLiveRegion="polite">
      <Text style={styles.title}>{props.title}</Text>
      {props.message ? <Text style={[styles.message, tone.text]}>{props.message}</Text> : null}
      {props.lines?.map((line) => (
        <Text key={line} style={[styles.message, tone.text]}>
          {line}
        </Text>
      ))}
      {props.actions && props.actions.length > 0 ? (
        <View style={styles.buttons}>
          {props.actions.map((action) => (
            <Pressable
              key={action.label}
              accessibilityRole="button"
              onPress={action.onPress}
              style={({ pressed }) => [
                styles.button,
                action.primary ? styles.buttonPrimary : styles.buttonSecondary,
                pressed && styles.dim,
              ]}
            >
              <Text style={action.primary ? styles.buttonPrimaryText : styles.buttonSecondaryText}>
                {action.label}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function Loading({ message, slowMessage }: { message: string; slowMessage?: string }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!slowMessage) {
      return;
    }
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(timer);
  }, [slowMessage]);

  return (
    <View style={styles.row} accessibilityLiveRegion="polite">
      <ActivityIndicator />
      <Text style={styles.status}>{slow && slowMessage ? slowMessage : message}</Text>
    </View>
  );
}

const TONES = {
  error: {
    card: { borderColor: '#b3261e', backgroundColor: '#fdf3f2' },
    text: { color: '#333' },
  },
  notice: {
    card: { borderColor: '#e0b252', backgroundColor: '#fff6e5' },
    text: { color: '#7a4b00' },
  },
  success: {
    card: { borderColor: '#1b7f3b', backgroundColor: '#f1faf3' },
    text: { color: '#333' },
  },
} as const;

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' },
  status: { color: '#555', flexShrink: 1 },
  card: { padding: 16, borderRadius: 8, borderWidth: 1, gap: 8 },
  title: { fontWeight: '600', color: '#1a1a1a' },
  message: { lineHeight: 20 },
  buttons: { flexDirection: 'row', gap: 12, flexWrap: 'wrap' },
  button: {
    flexGrow: 1,
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  dim: { opacity: 0.6 },
  buttonPrimary: { backgroundColor: '#1b7f3b', borderColor: '#1b7f3b' },
  buttonSecondary: { backgroundColor: '#fff', borderColor: '#1b7f3b' },
  buttonPrimaryText: { color: '#fff', fontWeight: '600' },
  buttonSecondaryText: { color: '#1b7f3b', fontWeight: '600' },
});

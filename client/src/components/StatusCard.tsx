import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

type Action = { label: string; onPress: () => void; primary?: boolean };

type Props =
  | { kind: 'loading'; message: string }
  | { kind: 'error'; title: string; message: string; actions: Action[] };

/**
 * A loading or error block with a message and, for errors, what to do next. Used where the
 * results page waits for the server or the lookup fails.
 */
export default function StatusCard(props: Props) {
  if (props.kind === 'loading') {
    return (
      <View style={styles.row} accessibilityLiveRegion="polite">
        <ActivityIndicator />
        <Text style={styles.status}>{props.message}</Text>
      </View>
    );
  }
  return (
    <View style={[styles.card, styles.cardError]} accessibilityLiveRegion="polite">
      <Text style={styles.title}>{props.title}</Text>
      <Text style={styles.message}>{props.message}</Text>
      <View style={styles.buttons}>
        {props.actions.map((action) => (
          <Pressable
            key={action.label}
            accessibilityRole="button"
            onPress={action.onPress}
            style={[styles.button, action.primary ? styles.buttonPrimary : styles.buttonSecondary]}
          >
            <Text style={action.primary ? styles.buttonPrimaryText : styles.buttonSecondaryText}>
              {action.label}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' },
  status: { color: '#555' },
  card: { padding: 16, borderRadius: 8, borderWidth: 1, gap: 8 },
  cardError: { borderColor: '#b3261e', backgroundColor: '#fdf3f2' },
  title: { fontWeight: '600', color: '#1a1a1a' },
  message: { color: '#333', lineHeight: 20 },
  buttons: { flexDirection: 'row', gap: 12, flexWrap: 'wrap' },
  button: {
    flexGrow: 1,
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  buttonPrimary: { backgroundColor: '#1b7f3b', borderColor: '#1b7f3b' },
  buttonSecondary: { backgroundColor: '#fff', borderColor: '#1b7f3b' },
  buttonPrimaryText: { color: '#fff', fontWeight: '600' },
  buttonSecondaryText: { color: '#1b7f3b', fontWeight: '600' },
});

import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { API_BASE_URL, fetchHealth, type HealthResponse } from './src/api';
import BarcodeScreen from './src/screens/BarcodeScreen';

type BackendState =
  | { kind: 'loading' }
  | { kind: 'ok'; health: HealthResponse }
  | { kind: 'error'; message: string };

export default function App() {
  const [backend, setBackend] = useState<BackendState>({ kind: 'loading' });

  useEffect(() => {
    fetchHealth()
      .then((health) => setBackend({ kind: 'ok', health }))
      .catch((error: unknown) =>
        setBackend({ kind: 'error', message: error instanceof Error ? error.message : String(error) }),
      );
  }, []);

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <View style={styles.column}>
        <View style={styles.header}>
          <Text style={styles.title}>What's in My Food?</Text>
          <Text style={styles.subtitle}>Scan a product's barcode to see what's in it.</Text>
        </View>

        <View style={styles.card}>
          <BarcodeScreen />
        </View>

        <View style={styles.status}>
          {backend.kind === 'loading' && <Text style={styles.statusText}>Checking backend…</Text>}
          {backend.kind === 'ok' && (
            <View style={styles.statusRow}>
              <View style={[styles.dot, styles.dotOk]} />
              <Text style={styles.statusText}>Backend connected</Text>
            </View>
          )}
          {backend.kind === 'error' && (
            <View style={styles.statusRow}>
              <View style={[styles.dot, styles.dotError]} />
              <Text style={styles.statusText}>Backend unreachable ({backend.message})</Text>
            </View>
          )}
          <Text style={styles.statusUrl}>{API_BASE_URL}</Text>
        </View>
      </View>

      <StatusBar style="auto" />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: {
    flexGrow: 1,
    backgroundColor: '#f6f7f6',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 56,
    paddingBottom: 32,
  },
  column: { width: '100%', maxWidth: 520, gap: 20 },
  header: { gap: 4, alignItems: 'center' },
  title: { fontSize: 28, fontWeight: '700', color: '#1a1a1a' },
  subtitle: { color: '#555', textAlign: 'center' },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e2e5e2',
    padding: 20,
  },
  status: { alignItems: 'center', gap: 2 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  dotOk: { backgroundColor: '#1b7f3b' },
  dotError: { backgroundColor: '#b3261e' },
  statusText: { color: '#555', fontSize: 12 },
  statusUrl: { color: '#999', fontSize: 11 },
});

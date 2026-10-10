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
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>What's in My Food?</Text>

      <BarcodeScreen />

      <View style={styles.status}>
        <Text style={styles.statusLabel}>Backend: {API_BASE_URL}</Text>
        {backend.kind === 'loading' && <Text style={styles.statusText}>Checking…</Text>}
        {backend.kind === 'ok' && (
          <Text style={styles.ok}>
            {backend.health.status} · {backend.health.service} · {backend.health.commit}
          </Text>
        )}
        {backend.kind === 'error' && <Text style={styles.error}>Unreachable: {backend.message}</Text>}
      </View>

      <StatusBar style="auto" />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    backgroundColor: '#fff',
    alignItems: 'center',
    padding: 24,
    paddingTop: 56,
    gap: 24,
  },
  title: { fontSize: 24, fontWeight: '600' },
  status: { gap: 4, alignItems: 'center', marginTop: 8 },
  statusLabel: { color: '#777', fontSize: 12 },
  statusText: { color: '#777', fontSize: 12 },
  ok: { color: '#1b7f3b', fontSize: 12 },
  error: { color: '#b3261e', fontSize: 12 },
});

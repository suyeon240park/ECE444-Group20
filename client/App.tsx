import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { API_BASE_URL, fetchHealth, type HealthResponse } from './src/api';

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
    <View style={styles.container}>
      <Text style={styles.title}>What's in My Food?</Text>
      <Text style={styles.subtitle}>Project skeleton. Features arrive in sprint 1 and 2.</Text>

      <View style={styles.card}>
        <Text style={styles.label}>Backend: {API_BASE_URL}</Text>
        {backend.kind === 'loading' && <Text>Checking…</Text>}
        {backend.kind === 'ok' && (
          <Text style={styles.ok}>
            {backend.health.status} · {backend.health.service} · {backend.health.commit}
          </Text>
        )}
        {backend.kind === 'error' && <Text style={styles.error}>Unreachable: {backend.message}</Text>}
      </View>

      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    gap: 12,
  },
  title: { fontSize: 24, fontWeight: '600' },
  subtitle: { color: '#555' },
  card: {
    marginTop: 16,
    padding: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#ddd',
    gap: 6,
    minWidth: 280,
  },
  label: { fontWeight: '500' },
  ok: { color: '#1b7f3b' },
  error: { color: '#b3261e' },
});

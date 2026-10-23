import { StatusBar } from 'expo-status-bar';
import { useEffect, useRef, useState } from 'react';
import { Platform, ScrollView, StyleSheet, Text, View } from 'react-native';

import {
  API_BASE_URL,
  CLIENT_COMMIT,
  fetchHealth,
  shortCommit,
  type HealthResponse,
} from './src/api';
import { fetchAnalysis } from './src/analysisApi';
import StatusCard from './src/components/StatusCard';
import { isMockName, MOCKS } from './src/mocks';
import type { AnalysisResult } from './src/productResult';
import BarcodeScreen from './src/screens/BarcodeScreen';
import ResultsScreen from './src/screens/ResultsScreen';

type BackendState =
  | { kind: 'loading' }
  | { kind: 'ok'; health: HealthResponse }
  | { kind: 'error'; message: string };

type Screen =
  | { kind: 'scan' }
  | { kind: 'loading'; barcode: string }
  | { kind: 'error'; barcode: string; message: string }
  | { kind: 'results'; analysis: AnalysisResult };

/**
 * Development only, on the web: `?preview=complete` (or incomplete, nutrition_only, flagged,
 * sections_unavailable) opens the results page with mock data and no backend (#41).
 */
function previewFromUrl(): AnalysisResult | null {
  if (!__DEV__ || Platform.OS !== 'web' || typeof window === 'undefined') {
    return null;
  }
  const name = new URLSearchParams(window.location.search).get('preview');
  return isMockName(name) ? MOCKS[name] : null;
}

export default function App() {
  const [backend, setBackend] = useState<BackendState>({ kind: 'loading' });
  const [view, setView] = useState<Screen>(() => {
    const preview = previewFromUrl();
    return preview ? { kind: 'results', analysis: preview } : { kind: 'scan' };
  });
  // Only the latest lookup may change the screen; a slow one for an earlier scan is ignored.
  const latestLookup = useRef(0);

  async function openResults(barcode: string) {
    const lookup = ++latestLookup.current;
    setView({ kind: 'loading', barcode });
    const outcome = await fetchAnalysis(barcode);
    if (latestLookup.current !== lookup) {
      return;
    }
    setView(
      outcome.kind === 'ok'
        ? { kind: 'results', analysis: outcome.analysis }
        : { kind: 'error', barcode, message: outcome.message },
    );
  }

  function scanAnother() {
    latestLookup.current += 1;
    setView({ kind: 'scan' });
  }

  useEffect(() => {
    fetchHealth()
      .then((health) => setBackend({ kind: 'ok', health }))
      .catch((error: unknown) =>
        setBackend({ kind: 'error', message: error instanceof Error ? error.message : String(error) }),
      );
  }, []);

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <View style={[styles.column, view.kind === 'results' && styles.columnWide]}>
        <View style={styles.header}>
          <Text style={styles.title}>What's in My Food?</Text>
          {view.kind === 'scan' ? (
            <Text style={styles.subtitle}>Scan a product's barcode to see what's in it.</Text>
          ) : null}
        </View>

        {view.kind === 'scan' && (
          <View style={styles.card}>
            <BarcodeScreen onBarcode={(barcode) => void openResults(barcode)} />
          </View>
        )}

        {view.kind === 'loading' && (
          <View style={styles.card}>
            <StatusCard kind="loading" message="Looking up the product…" />
          </View>
        )}

        {view.kind === 'error' && (
          <StatusCard
            kind="error"
            title="Couldn't get the product"
            message={view.message}
            actions={[
              { label: 'Try again', onPress: () => void openResults(view.barcode), primary: true },
              { label: 'Scan another product', onPress: scanAnother },
            ]}
          />
        )}

        {view.kind === 'results' && (
          <ResultsScreen analysis={view.analysis} onScanAnother={scanAnother} />
        )}

        <View style={styles.status}>
          {backend.kind === 'loading' && <Text style={styles.statusText}>Checking backend…</Text>}
          {backend.kind === 'ok' && (
            <View style={styles.statusRow}>
              <View style={[styles.dot, styles.dotOk]} />
              <Text style={styles.statusText}>
                Backend connected · {shortCommit(backend.health.commit)}
              </Text>
            </View>
          )}
          {backend.kind === 'error' && (
            <View style={styles.statusRow}>
              <View style={[styles.dot, styles.dotError]} />
              <Text style={styles.statusText}>Backend unreachable ({backend.message})</Text>
            </View>
          )}
          <Text style={styles.statusUrl}>{API_BASE_URL}</Text>
          <Text style={styles.statusUrl}>App build {shortCommit(CLIENT_COMMIT)}</Text>
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
  columnWide: { maxWidth: 760 },
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

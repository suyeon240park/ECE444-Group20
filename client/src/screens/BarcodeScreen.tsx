import * as ImagePicker from 'expo-image-picker';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View } from 'react-native';

import { detectBarcode, type PickedImage } from '../barcode';
import {
  failure,
  formatLabel,
  validateImage,
  type BarcodeErrorCode,
  type BarcodeResult,
} from '../barcodeRules';
import LiveScanner, { isLiveScanSupported } from '../LiveScanner';
import type { LiveScanOutcome } from '../liveScan';

type Source = 'camera' | 'library';

type ScreenState =
  | { kind: 'idle' }
  | { kind: 'live'; request: number }
  | { kind: 'loading'; previewUri: string }
  | { kind: 'success'; previewUri: string; barcode: string; format: string }
  | { kind: 'failure'; previewUri: string | null; code: BarcodeErrorCode; message: string };

const PICKER_OPTIONS: ImagePicker.ImagePickerOptions = {
  mediaTypes: ['images'],
  // Re-encodes to JPEG on phones, which also turns most iPhone HEIC photos into JPEG.
  quality: 0.8,
  allowsEditing: false,
  exif: false,
};

function toState(previewUri: string | null, outcome: BarcodeResult): ScreenState {
  if (outcome.ok) {
    return {
      kind: 'success',
      previewUri: previewUri ?? '',
      barcode: outcome.barcode,
      format: outcome.format,
    };
  }
  return { kind: 'failure', previewUri, code: outcome.code, message: outcome.message };
}

/**
 * Take or upload a photo of a product, send it to the backend, show the barcode found.
 * On the web, a webcam mode keeps scanning until it reads one.
 */
export default function BarcodeScreen() {
  const [state, setState] = useState<ScreenState>({ kind: 'idle' });
  // Only the latest request may update the screen; older ones, and ones that finish
  // after the screen is gone, are ignored.
  const latestRequest = useRef(0);

  useEffect(() => {
    return () => {
      latestRequest.current += 1;
    };
  }, []);

  const busy = state.kind === 'loading' || state.kind === 'live';
  const liveSupported = isLiveScanSupported();

  function startLive() {
    setState({ kind: 'live', request: ++latestRequest.current });
  }

  function stopLive() {
    latestRequest.current += 1;
    setState({ kind: 'idle' });
  }

  function onLiveResult(request: number, outcome: LiveScanOutcome) {
    if (latestRequest.current !== request) {
      return;
    }
    const previewUri = outcome.image?.file ? URL.createObjectURL(outcome.image.file) : null;
    setState(toState(previewUri, outcome.result));
  }

  async function pick(source: Source) {
    const request = ++latestRequest.current;
    const showFailure = (code: BarcodeErrorCode, previewUri: string | null = null) => {
      if (latestRequest.current === request) {
        setState(toState(previewUri, failure(code)));
      }
    };

    let picked: ImagePicker.ImagePickerResult;
    try {
      if (source === 'camera') {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) {
          showFailure('camera_permission_denied');
          return;
        }
        picked = await ImagePicker.launchCameraAsync(PICKER_OPTIONS);
      } else {
        picked = await ImagePicker.launchImageLibraryAsync(PICKER_OPTIONS);
      }
    } catch {
      showFailure('picker_error');
      return;
    }
    if (picked.canceled || latestRequest.current !== request) {
      return;
    }

    const asset = picked.assets[0];
    const image: PickedImage = {
      uri: asset.uri,
      fileName: asset.fileName,
      mimeType: asset.mimeType,
      fileSize: asset.fileSize,
      file: asset.file,
    };

    const invalid = validateImage(image);
    if (invalid) {
      showFailure(invalid, image.uri);
      return;
    }

    setState({ kind: 'loading', previewUri: image.uri });
    const outcome = await detectBarcode(image);
    if (latestRequest.current === request) {
      setState(toState(image.uri, outcome));
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Scan a product</Text>
      <Text style={styles.help}>
        Scan the barcode, or upload a photo of it. Keep the barcode flat, in focus and fully in
        frame.
      </Text>

      <View style={styles.buttons}>
        <ActionButton label="Upload photo" onPress={() => pick('library')} disabled={busy} primary />
        {liveSupported ? (
          <ActionButton label="Scan live" onPress={startLive} disabled={busy} />
        ) : (
          // Phones in Expo Go, and web pages that cannot open a webcam, take one photo instead.
          <ActionButton label="Take photo" onPress={() => pick('camera')} disabled={busy} />
        )}
      </View>

      {state.kind === 'live' && (
        <LiveScanner onResult={(outcome) => onLiveResult(state.request, outcome)} onStop={stopLive} />
      )}

      {'previewUri' in state && state.previewUri ? (
        <Image
          source={{ uri: state.previewUri }}
          style={styles.preview}
          resizeMode="contain"
          accessibilityLabel="The photo you chose"
        />
      ) : null}

      {state.kind === 'loading' && (
        <View style={styles.row} accessibilityLiveRegion="polite">
          <ActivityIndicator />
          <Text style={styles.status}>Looking for a barcode…</Text>
        </View>
      )}

      {state.kind === 'success' && (
        <View style={[styles.card, styles.cardOk]} accessibilityLiveRegion="polite">
          <Text style={styles.cardTitle}>Barcode found</Text>
          <Text style={styles.barcode} selectable>
            {state.barcode}
          </Text>
          {state.format ? <Text style={styles.format}>{formatLabel(state.format)}</Text> : null}
        </View>
      )}

      {state.kind === 'failure' && (
        <View style={[styles.card, styles.cardError]} accessibilityLiveRegion="polite">
          <Text style={styles.cardTitle}>Couldn't read a barcode</Text>
          <Text style={styles.message}>{state.message}</Text>
        </View>
      )}
    </View>
  );
}

type ActionButtonProps = {
  label: string;
  onPress: () => void;
  disabled: boolean;
  primary?: boolean;
};

function ActionButton({ label, onPress, disabled, primary }: ActionButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled }}
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        primary ? styles.buttonPrimary : styles.buttonSecondary,
        (pressed || disabled) && styles.buttonDim,
      ]}
    >
      <Text style={primary ? styles.buttonPrimaryText : styles.buttonSecondaryText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { alignSelf: 'stretch', maxWidth: 480, gap: 16 },
  heading: { fontSize: 24, fontWeight: '600', textAlign: 'center' },
  help: { color: '#555', textAlign: 'center' },
  buttons: { flexDirection: 'row', gap: 12, justifyContent: 'center', flexWrap: 'wrap' },
  button: {
    minWidth: 140,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  buttonPrimary: { backgroundColor: '#1b7f3b', borderColor: '#1b7f3b' },
  buttonSecondary: { backgroundColor: '#fff', borderColor: '#1b7f3b' },
  buttonDim: { opacity: 0.6 },
  buttonPrimaryText: { color: '#fff', fontWeight: '600' },
  buttonSecondaryText: { color: '#1b7f3b', fontWeight: '600' },
  preview: { height: 220, borderRadius: 8, backgroundColor: '#f2f2f2' },
  row: { flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' },
  status: { color: '#555' },
  card: { padding: 16, borderRadius: 8, borderWidth: 1, gap: 6 },
  cardOk: { borderColor: '#1b7f3b', backgroundColor: '#f1faf3' },
  cardError: { borderColor: '#b3261e', backgroundColor: '#fdf3f2' },
  cardTitle: { fontWeight: '600' },
  barcode: { fontSize: 28, fontWeight: '600', letterSpacing: 1 },
  format: { color: '#555' },
  message: { color: '#b3261e' },
});

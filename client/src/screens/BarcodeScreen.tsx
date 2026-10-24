import * as ImagePicker from 'expo-image-picker';
import { useEffect, useRef, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';

import { detectBarcode, type PickedImage } from '../barcode';
import {
  failure,
  formatLabel,
  validateImage,
  type BarcodeErrorCode,
  type BarcodeResult,
} from '../barcodeRules';
import StatusCard from '../components/StatusCard';
import LiveScanner, { isLiveScanSupported } from '../LiveScanner';
import type { LiveScanOutcome } from '../liveScan';

type Source = 'camera' | 'library';

/** Failures to do with sending the photo or the server's answer, not with the photo itself. */
const CONNECTION_CODES: readonly BarcodeErrorCode[] = [
  'network_error',
  'timeout',
  'upload_failed',
  'unexpected_response',
];

type ScreenState =
  | { kind: 'idle' }
  | { kind: 'live'; request: number }
  | { kind: 'loading'; previewUri: string }
  | { kind: 'success'; previewUri: string; barcode: string; format: string }
  | { kind: 'failure'; previewUri: string | null; code: BarcodeErrorCode; message: string };

const PICKER_OPTIONS: ImagePicker.ImagePickerOptions = {
  mediaTypes: ['images'],
  // Compresses the photo before it is uploaded.
  quality: 0.8,
  allowsEditing: false,
  exif: false,
  // iOS keeps library photos as HEIC unless it is asked for the compatible (JPEG) version.
  // Ignored on Android and the web. The HEIC check in validateImage stays as a fallback.
  preferredAssetRepresentationMode: ImagePicker.UIImagePickerPreferredAssetRepresentationMode.Compatible,
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

type Props = {
  /** Called once with the barcode when one is read; the results page opens from it (#41). */
  onBarcode?: (barcode: string) => void;
};

/**
 * Take or upload a photo of a product, send it to the backend, show the barcode found.
 * On the web, a webcam mode keeps scanning until it reads one.
 */
export default function BarcodeScreen({ onBarcode }: Props) {
  const [state, setState] = useState<ScreenState>({ kind: 'idle' });
  // Only the latest request may update the screen; older ones, and ones that finish
  // after the screen is gone, are ignored.
  const latestRequest = useRef(0);
  // What "Try again" repeats after a failure: the last way the person started a scan.
  const lastStart = useRef<Source | 'live'>('library');

  useEffect(() => {
    return () => {
      latestRequest.current += 1;
    };
  }, []);

  useEffect(() => {
    if (state.kind === 'success') {
      onBarcode?.(state.barcode);
    }
    // Only a new result should fire it, not a new callback from a parent re-render.
  }, [state]);

  const busy = state.kind === 'loading' || state.kind === 'live';
  const liveSupported = isLiveScanSupported();

  function startLive() {
    lastStart.current = 'live';
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

  function tryAgain() {
    if (lastStart.current === 'live') {
      startLive();
    } else {
      void pick(lastStart.current);
    }
  }

  async function pick(source: Source) {
    lastStart.current = source;
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

      {state.kind === 'loading' && <StatusCard kind="loading" message="Looking for a barcode…" />}

      {state.kind === 'success' && (
        <StatusCard
          kind="success"
          title="Barcode found"
          message={`${state.barcode}${state.format ? ` (${formatLabel(state.format)})` : ''}`}
        />
      )}

      {state.kind === 'failure' && (
        <StatusCard
          kind="error"
          title={
            CONNECTION_CODES.includes(state.code)
              ? "Couldn't check the photo"
              : "Couldn't read a barcode"
          }
          message={state.message}
          actions={[{ label: 'Try again', onPress: tryAgain, primary: true }]}
        />
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
  container: { alignSelf: 'stretch', gap: 16 },
  heading: { fontSize: 18, fontWeight: '600', color: '#1a1a1a' },
  help: { color: '#555', lineHeight: 20 },
  buttons: { flexDirection: 'row', gap: 12 },
  button: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  buttonPrimary: { backgroundColor: '#1b7f3b', borderColor: '#1b7f3b' },
  buttonSecondary: { backgroundColor: '#fff', borderColor: '#1b7f3b' },
  buttonDim: { opacity: 0.6 },
  buttonPrimaryText: { color: '#fff', fontWeight: '600' },
  buttonSecondaryText: { color: '#1b7f3b', fontWeight: '600' },
  preview: {
    height: 220,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e2e5e2',
    backgroundColor: '#f2f2f2',
  },
});

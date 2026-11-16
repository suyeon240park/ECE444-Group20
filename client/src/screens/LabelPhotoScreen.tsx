import * as ImagePicker from 'expo-image-picker';
import { useRef, useState } from 'react';
import { Image, Platform, StyleSheet, Text, View } from 'react-native';

import type { PickedImage } from '../barcode';
import { ERROR_MESSAGES } from '../barcodeRules';
import StatusCard from '../components/StatusCard';
import { PRIVACY_NOTICE, readLabelPhoto } from '../labelPhoto';
import { ActionButton, PICKER_OPTIONS } from './BarcodeScreen';
import type { PhotoReading } from './ConfirmPhotoValuesScreen';

type Source = 'camera' | 'library';

type ScreenState =
  | { kind: 'idle' }
  | { kind: 'loading'; previewUri: string }
  | { kind: 'failure'; previewUri: string | null; message: string };

type Props = {
  /** The barcode of a product the database found but could not complete; null for a nutrition-only photo. */
  barcode: string | null;
  /** Called with what the photo showed; the confirm screen (#39) opens from it. */
  onReading: (reading: PhotoReading) => void;
  onCancel: () => void;
  cancelLabel: string;
};

/**
 * Take or upload a photo of the Nutrition Facts table and send it to be read (#63): for a
 * product the database could not complete, or one it could not find (docs/api/analysis.md).
 * The photo leaves the device only after the person has seen where it goes.
 */
export default function LabelPhotoScreen({ barcode, onReading, onCancel, cancelLabel }: Props) {
  const [state, setState] = useState<ScreenState>({ kind: 'idle' });
  // Only the latest photo may change the screen.
  const latestRequest = useRef(0);
  const lastSource = useRef<Source>('library');
  const busy = state.kind === 'loading';

  async function pick(source: Source) {
    lastSource.current = source;
    const request = ++latestRequest.current;
    const showFailure = (message: string, previewUri: string | null = null) => {
      if (latestRequest.current === request) {
        setState({ kind: 'failure', previewUri, message });
      }
    };

    let picked: ImagePicker.ImagePickerResult;
    try {
      if (source === 'camera') {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) {
          showFailure(ERROR_MESSAGES.camera_permission_denied);
          return;
        }
        picked = await ImagePicker.launchCameraAsync(PICKER_OPTIONS);
      } else {
        picked = await ImagePicker.launchImageLibraryAsync(PICKER_OPTIONS);
      }
    } catch {
      showFailure(ERROR_MESSAGES.picker_error);
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

    setState({ kind: 'loading', previewUri: image.uri });
    const outcome = await readLabelPhoto(image, barcode);
    if (latestRequest.current !== request) {
      return;
    }
    if (outcome.kind === 'reading') {
      onReading(outcome.reading);
    } else {
      showFailure(outcome.message, image.uri);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Photograph the Nutrition Facts</Text>
      <Text style={styles.help}>
        {barcode
          ? 'The food database is missing some of this product. A photo of its Nutrition Facts table fills the gaps.'
          : "We couldn't find this product, but a photo of its Nutrition Facts table still shows what's in it."}{' '}
        Take the photo straight on, with the whole table in frame and no glare. You'll check each
        value before it's used.
      </Text>
      <Text style={styles.privacy}>{PRIVACY_NOTICE}</Text>

      <View style={styles.buttons}>
        <ActionButton label="Upload photo" onPress={() => pick('library')} disabled={busy} primary />
        {Platform.OS !== 'web' ? (
          <ActionButton label="Take photo" onPress={() => pick('camera')} disabled={busy} />
        ) : null}
      </View>

      {'previewUri' in state && state.previewUri ? (
        <Image
          source={{ uri: state.previewUri }}
          style={styles.preview}
          resizeMode="contain"
          accessibilityLabel="The photo you chose"
        />
      ) : null}

      {state.kind === 'loading' && (
        <StatusCard
          kind="loading"
          message="Reading the Nutrition Facts table…"
          slowMessage="Still reading. This can take up to a minute."
        />
      )}

      {state.kind === 'failure' && (
        <StatusCard
          kind="error"
          title="Couldn't read the label"
          message={state.message}
          actions={[{ label: 'Try again', onPress: () => void pick(lastSource.current), primary: true }]}
        />
      )}

      <View style={styles.buttons}>
        <ActionButton label={cancelLabel} onPress={onCancel} disabled={busy} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignSelf: 'stretch', gap: 16 },
  heading: { fontSize: 18, fontWeight: '600', color: '#1a1a1a' },
  help: { color: '#555', lineHeight: 20 },
  privacy: { color: '#666', fontSize: 13, lineHeight: 18 },
  buttons: { flexDirection: 'row', gap: 12 },
  preview: {
    height: 220,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e2e5e2',
    backgroundColor: '#f2f2f2',
  },
});

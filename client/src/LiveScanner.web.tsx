import { useEffect, useRef } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import type { PickedImage } from './barcode';
import { failure } from './barcodeRules';
import { runLiveScan, type LiveScannerProps } from './liveScan';

/** Frames are shrunk to this width before upload; a barcode stays readable and the file small. */
const MAX_FRAME_WIDTH = 1280;

/** Browsers only offer a webcam on https pages and on localhost. */
export function isLiveScanSupported(): boolean {
  return typeof navigator !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia);
}

async function captureFrame(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
): Promise<PickedImage | null> {
  if (video.readyState < 2 || !video.videoWidth) {
    return null;
  }
  const scale = Math.min(1, MAX_FRAME_WIDTH / video.videoWidth);
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  const context = canvas.getContext('2d');
  if (!context) {
    return null;
  }
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, 'image/jpeg', 0.85),
  );
  if (!blob) {
    return null;
  }
  const file = new File([blob], 'webcam-frame.jpg', { type: 'image/jpeg' });
  return { uri: '', fileName: file.name, mimeType: file.type, fileSize: file.size, file };
}

/** Webcam preview that keeps sending frames to the backend until a barcode is read. */
export default function LiveScanner({ onResult, onStop }: LiveScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  // The latest callback, so the effect below can run once without going stale.
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  useEffect(() => {
    const signal = { aborted: false };
    let stream: MediaStream | null = null;

    async function start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        });
        const video = videoRef.current;
        if (signal.aborted || !video) {
          return;
        }
        video.srcObject = stream;
        await video.play();
      } catch {
        if (!signal.aborted) {
          onResultRef.current({ result: failure('webcam_unavailable'), image: null });
        }
        return;
      }

      const video = videoRef.current;
      if (!video) {
        return;
      }
      const canvas = document.createElement('canvas');
      const outcome = await runLiveScan({ capture: () => captureFrame(video, canvas), signal });
      if (outcome && !signal.aborted) {
        onResultRef.current(outcome);
      }
    }

    void start();
    return () => {
      signal.aborted = true;
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  return (
    <View style={styles.container}>
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        aria-label="Webcam preview"
        style={{ width: '100%', height: 260, objectFit: 'cover', borderRadius: 8, background: '#000' }}
      />
      <View style={styles.row} accessibilityLiveRegion="polite">
        <ActivityIndicator />
        <Text style={styles.status}>Hold the barcode up to the camera…</Text>
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Stop scanning"
        onPress={onStop}
        style={({ pressed }) => [styles.stop, pressed && styles.dim]}
      >
        <Text style={styles.stopText}>Stop</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 12 },
  row: { flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' },
  status: { color: '#555' },
  stop: {
    alignSelf: 'center',
    paddingVertical: 10,
    paddingHorizontal: 24,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#b3261e',
  },
  stopText: { color: '#b3261e', fontWeight: '600' },
  dim: { opacity: 0.6 },
});

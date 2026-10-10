import { detectBarcode, type PickedImage } from './barcode';
import { failure, type BarcodeResult } from './barcodeRules';

/** Pause between one attempt finishing and the next frame being grabbed. */
export const SCAN_INTERVAL_MS = 400;

/** Stop looking after this long, so the camera is never left on forever. */
export const SCAN_TIMEOUT_MS = 60_000;

/** How a live scan ended. `image` is the frame that was read, when there is one. */
export type LiveScanOutcome = { result: BarcodeResult; image: PickedImage | null };

export type LiveScannerProps = {
  /** Called once, when a barcode is read or scanning cannot go on. */
  onResult: (outcome: LiveScanOutcome) => void;
  /** Called when the person presses Stop. */
  onStop: () => void;
};

type LiveScanOptions = {
  /** Grab the current camera frame, or null while the camera is not ready yet. */
  capture: () => Promise<PickedImage | null>;
  signal: { aborted: boolean };
  detect?: (image: PickedImage) => Promise<BarcodeResult>;
  intervalMs?: number;
  timeoutMs?: number;
  now?: () => number;
  sleep?: (ms: number) => Promise<void>;
};

/**
 * Grab frames and send them to the backend one at a time until one has a barcode.
 *
 * "No barcode in this frame" is expected while the person lines the code up, so it
 * just means try again. Any other failure ends the scan. Returns null if `signal`
 * was aborted first, in which case nothing should be shown.
 */
export async function runLiveScan({
  capture,
  signal,
  detect = detectBarcode,
  intervalMs = SCAN_INTERVAL_MS,
  timeoutMs = SCAN_TIMEOUT_MS,
  now = Date.now,
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
}: LiveScanOptions): Promise<LiveScanOutcome | null> {
  const deadline = now() + timeoutMs;
  while (!signal.aborted) {
    if (now() >= deadline) {
      return { result: failure('live_timeout'), image: null };
    }
    const image = await capture();
    if (signal.aborted) {
      return null;
    }
    if (image) {
      const result = await detect(image);
      if (signal.aborted) {
        return null;
      }
      if (result.ok) {
        return { result, image };
      }
      if (result.code !== 'no_barcode_found') {
        return { result, image: null };
      }
    }
    await sleep(intervalMs);
  }
  return null;
}

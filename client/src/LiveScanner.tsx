import type { LiveScannerProps } from './liveScan';

/** Live scanning uses the browser's webcam, so it is only offered on the web. */
export function isLiveScanSupported(): boolean {
  return false;
}

export default function LiveScanner(_props: LiveScannerProps) {
  return null;
}

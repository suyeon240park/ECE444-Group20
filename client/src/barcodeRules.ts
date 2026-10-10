/**
 * Rules and messages for barcode detection (#13). No React Native imports, so this
 * module is plain TypeScript.
 *
 * The backend contract is POST /api/barcode (backend/README.md):
 *   200 {"barcode": "5901234123457", "format": "EAN13"}
 *   4xx {"error": {"code": "...", "message": "..."}}
 */

/** Largest upload the backend accepts (MAX_UPLOAD_BYTES in backend/app/__init__.py). */
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

/** Image types the backend accepts. It checks the file contents, not this label. */
export const SUPPORTED_MIME_TYPES: readonly string[] = ['image/jpeg', 'image/png', 'image/webp'];

/** Error codes the backend can return. */
export type BackendErrorCode =
  | 'missing_image'
  | 'invalid_image'
  | 'unsupported_media_type'
  | 'file_too_large'
  | 'image_too_large'
  | 'no_barcode_found';

/** Failures that happen on the device, before or without an answer from the backend. */
export type ClientErrorCode =
  | 'heic_image'
  | 'camera_permission_denied'
  | 'picker_error'
  | 'webcam_unavailable'
  | 'live_timeout'
  | 'network_error'
  | 'timeout'
  | 'unexpected_response';

export type BarcodeErrorCode = BackendErrorCode | ClientErrorCode;

export type BarcodeResult =
  | { ok: true; barcode: string; format: string }
  | { ok: false; code: BarcodeErrorCode; message: string };

/** What is known about a picked photo. Every field can be missing on some platforms. */
export type ImageInfo = {
  fileName?: string | null;
  mimeType?: string | null;
  fileSize?: number | null;
};

/** One plain-language message per failure, each saying what the person can do next. */
export const ERROR_MESSAGES: Record<BarcodeErrorCode, string> = {
  no_barcode_found:
    "We couldn't read a barcode in that photo. Retake it with the barcode flat, in focus and fully in frame, in good light.",
  invalid_image: "That file isn't a readable image. Choose a photo from your camera or library.",
  unsupported_media_type: "That image type isn't supported. Use a JPEG, PNG or WebP photo.",
  heic_image:
    "HEIC photos aren't supported yet. Take a new photo with the camera button, or choose a JPEG or PNG.",
  file_too_large: 'That photo is too large (over 10 MB). Choose a smaller one.',
  image_too_large: 'That photo has too many pixels. Choose a smaller one.',
  missing_image: 'No photo was sent. Please try again.',
  camera_permission_denied:
    'Camera access is turned off. Allow it in your device settings, or upload a photo instead.',
  picker_error: "We couldn't open the camera or photo library. Try again, or use the other button.",
  webcam_unavailable:
    'We could not open the webcam. Allow camera access in your browser, or upload a photo instead.',
  live_timeout:
    "We couldn't find a barcode after a minute. Hold it flat, closer to the camera and well lit, or upload a photo instead.",
  network_error: "We couldn't reach the server. Check your connection and try again.",
  timeout: 'The server took too long to respond. Try again.',
  unexpected_response: "We couldn't understand the server's answer. Please try again.",
};

export function failure(code: BarcodeErrorCode): BarcodeResult {
  return { ok: false, code, message: ERROR_MESSAGES[code] };
}

function isBackendErrorCode(value: unknown): value is BackendErrorCode {
  return (
    value === 'missing_image' ||
    value === 'invalid_image' ||
    value === 'unsupported_media_type' ||
    value === 'file_too_large' ||
    value === 'image_too_large' ||
    value === 'no_barcode_found'
  );
}

function isHeic(image: ImageInfo): boolean {
  const mime = image.mimeType?.toLowerCase() ?? '';
  const name = image.fileName?.toLowerCase() ?? '';
  return (
    mime === 'image/heic' || mime === 'image/heif' || name.endsWith('.heic') || name.endsWith('.heif')
  );
}

/**
 * Check a picked photo before uploading it, so the person gets an instant answer.
 * Returns the failure code, or null when the photo looks fine. The backend repeats
 * every check and stays the source of truth.
 */
export function validateImage(image: ImageInfo): BarcodeErrorCode | null {
  if (typeof image.fileSize === 'number' && image.fileSize > MAX_UPLOAD_BYTES) {
    return 'file_too_large';
  }
  if (isHeic(image)) {
    return 'heic_image';
  }
  const mime = image.mimeType?.toLowerCase();
  if (mime && !SUPPORTED_MIME_TYPES.includes(mime)) {
    return 'unsupported_media_type';
  }
  return null;
}

/** Turn the backend's HTTP status and JSON body into a result. */
export function parseBarcodeResponse(status: number, body: unknown): BarcodeResult {
  if (typeof body === 'object' && body !== null) {
    const record = body as Record<string, unknown>;
    if (status === 200 && typeof record.barcode === 'string' && /^\d{8,14}$/.test(record.barcode)) {
      return {
        ok: true,
        barcode: record.barcode,
        format: typeof record.format === 'string' ? record.format : '',
      };
    }
    const error = record.error;
    if (typeof error === 'object' && error !== null) {
      const code = (error as Record<string, unknown>).code;
      if (isBackendErrorCode(code)) {
        return failure(code);
      }
    }
  }
  return failure('unexpected_response');
}

const FORMAT_LABELS: Record<string, string> = {
  EAN13: 'EAN-13',
  EAN8: 'EAN-8',
  UPCA: 'UPC-A',
  ITF14: 'GTIN-14',
};

/** The backend's format name as people write it, for example EAN13 becomes EAN-13. */
export function formatLabel(format: string): string {
  return FORMAT_LABELS[format] ?? format;
}

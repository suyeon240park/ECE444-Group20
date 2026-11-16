import type { AnalysisResult } from './analysis';
import { API_BASE_URL } from './api';
import { buildForm, type PickedImage } from './barcode';
import { ERROR_MESSAGES as PHOTO_MESSAGES, validateImage } from './barcodeRules';
import type { PhotoReading } from './screens/ConfirmPhotoValuesScreen';

/**
 * The vision model can take up to VISION_TIMEOUT_SECONDS (60) on each model it tries, and the
 * server allows 180 s (backend/gunicorn.conf.py). Wait a little longer than one slow model.
 */
const REQUEST_TIMEOUT_MS = 90_000;

/** Shown before the photo is sent (privacy decision in docs/requirements.md, question 4). */
export const PRIVACY_NOTICE =
  "The photo is sent to Google's Gemini service to read the table. On its free tier, Google may use photos to improve its products. We don't keep the photo.";

export type LabelPhotoOutcome =
  /** A reading for the confirm screen (#39): the values found, or "no table in this photo". */
  | { kind: 'reading'; reading: PhotoReading }
  | { kind: 'error'; code: string; message: string };

/** Messages for failures that only the label photo has; the rest are shared with the barcode photo. */
const LABEL_MESSAGES: Record<string, string> = {
  upstream_unavailable:
    "We couldn't read the label right now. The reading service is busy; try again in a minute.",
  upstream_timeout: 'Reading the label took too long. Try again, or use a smaller, sharper photo.',
  photo_reading_unavailable: "Reading label photos isn't available on this server right now.",
  invalid_barcode: 'That barcode does not look right. Scan it again.',
};

function failure(code: string): LabelPhotoOutcome {
  const message =
    LABEL_MESSAGES[code] ??
    (PHOTO_MESSAGES as Record<string, string>)[code] ??
    PHOTO_MESSAGES.unexpected_response;
  return { kind: 'error', code, message };
}

/**
 * POST /api/analysis/label-photo (#43): read a photo of a Nutrition Facts table. With the
 * barcode of a product the database found, the label fills that product's gaps; without one,
 * the result is nutrition-only (docs/api/analysis.md). Never throws.
 */
export async function readLabelPhoto(
  image: PickedImage,
  barcode?: string | null,
): Promise<LabelPhotoOutcome> {
  const invalid = validateImage(image);
  if (invalid) {
    return failure(invalid);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const form = await buildForm(image);
    if (barcode) {
      form.append('barcode', barcode);
    }
    // No Content-Type header: fetch sets it, including the multipart boundary.
    const response = await fetch(`${API_BASE_URL}/api/analysis/label-photo`, {
      method: 'POST',
      body: form,
      signal: controller.signal,
    });
    const body: unknown = await response.json().catch(() => null);
    if (response.ok && body && typeof body === 'object') {
      return { kind: 'reading', reading: { status: 'found', result: body as AnalysisResult } };
    }
    const code = (body as { error?: { code?: unknown } } | null)?.error?.code;
    if (code === 'nutrition_table_not_found') {
      return { kind: 'reading', reading: { status: 'not_found' } };
    }
    return failure(typeof code === 'string' ? code : 'unexpected_response');
  } catch (error: unknown) {
    if (controller.signal.aborted) {
      return failure('upstream_timeout');
    }
    console.warn('Label photo upload failed', error);
    return failure(error instanceof TypeError ? 'network_error' : 'upload_failed');
  } finally {
    clearTimeout(timer);
  }
}

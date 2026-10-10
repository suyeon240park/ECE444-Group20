import { Platform } from 'react-native';

import { API_BASE_URL } from './api';
import { failure, parseBarcodeResponse, type BarcodeResult, type ImageInfo } from './barcodeRules';

/** The multipart field the backend reads the photo from. */
const UPLOAD_FIELD = 'image';

/** Give up on the request after this long. */
const REQUEST_TIMEOUT_MS = 20_000;

/** A photo picked with the camera or the library. */
export type PickedImage = ImageInfo & {
  uri: string;
  /** Set on the web only: the File the person chose. */
  file?: File;
};

async function buildForm(image: PickedImage): Promise<FormData> {
  const form = new FormData();
  if (Platform.OS === 'web') {
    const blob = image.file ?? (await (await fetch(image.uri)).blob());
    form.append(UPLOAD_FIELD, blob, image.fileName ?? 'photo');
  } else {
    // React Native's FormData uploads a file from a { uri, name, type } object.
    form.append(UPLOAD_FIELD, {
      uri: image.uri,
      name: image.fileName ?? 'photo.jpg',
      type: image.mimeType ?? 'image/jpeg',
    } as unknown as Blob);
  }
  return form;
}

/**
 * Send a photo to POST /api/barcode and return the barcode in it, or the reason it
 * could not be read. Never throws: every failure comes back as a result with a
 * plain-language message.
 */
export async function detectBarcode(image: PickedImage): Promise<BarcodeResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    // No Content-Type header: fetch sets it, including the multipart boundary.
    const response = await fetch(`${API_BASE_URL}/api/barcode`, {
      method: 'POST',
      body: await buildForm(image),
      signal: controller.signal,
    });
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // Not JSON, for example an error page from a proxy. parseBarcodeResponse handles null.
    }
    return parseBarcodeResponse(response.status, body);
  } catch (error: unknown) {
    if (controller.signal.aborted) {
      return failure('timeout');
    }
    return failure(error instanceof TypeError ? 'network_error' : 'unexpected_response');
  } finally {
    clearTimeout(timer);
  }
}

import { File as NativeFile } from 'expo-file-system';
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
    // expo/fetch, the default fetch on iOS and Android, cannot send React Native's
    // { uri, name, type } form parts and throws before any request is made. A File from
    // expo-file-system is a Blob it can send.
    form.append(UPLOAD_FIELD, new NativeFile(image.uri), image.fileName ?? 'photo.jpg');
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
    // Shows in the Expo terminal and the browser console, so a failure before any reply
    // arrived (for example a photo that could not be packed into the request) can be traced.
    console.warn('Barcode upload failed', error);
    // A TypeError is how fetch reports a network failure. Any other error was thrown before
    // a reply existed; "unexpected_response" is kept for replies that really were unreadable.
    return failure(error instanceof TypeError ? 'network_error' : 'upload_failed');
  } finally {
    clearTimeout(timer);
  }
}

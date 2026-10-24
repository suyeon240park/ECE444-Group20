import { API_BASE_URL } from './api';
import type { AnalysisResult } from './productResult';

/** Give up on the request after this long. */
const REQUEST_TIMEOUT_MS = 20_000;

export type AnalysisOutcome =
  | { kind: 'ok'; analysis: AnalysisResult }
  | { kind: 'error'; code: string; message: string };

/** What to tell the person for each way the lookup can fail, and what to do next. */
const ERROR_MESSAGES: Record<string, string> = {
  product_not_found:
    "We couldn't find this product in the food database. Check the barcode, or scan a different product.",
  invalid_barcode: 'That barcode does not look right. Scan it again.',
  upstream_unavailable:
    "The food database isn't answering right now. Try again in a moment.",
  upstream_timeout: 'The food database took too long to answer. Try again in a moment.',
  timeout: 'The server took too long to answer. Try again in a moment.',
  network_error: "We couldn't reach the server. Check your connection and try again.",
  unexpected_response: 'The server sent an answer we could not read. Try again.',
};

function failure(code: string): AnalysisOutcome {
  return {
    kind: 'error',
    code,
    message: ERROR_MESSAGES[code] ?? ERROR_MESSAGES.unexpected_response,
  };
}

/**
 * GET /api/analysis/{barcode}: everything the results page shows for a scanned barcode.
 * Never throws: every failure comes back as a plain-language message.
 */
export async function fetchAnalysis(barcode: string): Promise<AnalysisOutcome> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}/api/analysis/${encodeURIComponent(barcode)}`, {
      signal: controller.signal,
    });
    const body: unknown = await response.json().catch(() => null);
    if (response.ok && body && typeof body === 'object') {
      return { kind: 'ok', analysis: body as AnalysisResult };
    }
    const code = (body as { error?: { code?: unknown } } | null)?.error?.code;
    return failure(typeof code === 'string' ? code : 'unexpected_response');
  } catch (error: unknown) {
    if (controller.signal.aborted) {
      return failure('timeout');
    }
    console.warn('Analysis request failed', error);
    return failure(error instanceof TypeError ? 'network_error' : 'unexpected_response');
  } finally {
    clearTimeout(timer);
  }
}

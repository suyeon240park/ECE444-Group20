import Constants from 'expo-constants';

/**
 * Base URL of the backend API.
 *
 * Order of precedence:
 * 1. EXPO_PUBLIC_API_BASE_URL at build time (used by the staging deployment, #22)
 * 2. `extra.apiBaseUrl` in app.json (local development default)
 */
export const API_BASE_URL: string =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  (Constants.expoConfig?.extra?.apiBaseUrl as string | undefined) ??
  'http://localhost:5000';

export type HealthResponse = {
  status: string;
  service: string;
  commit: string;
};

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}

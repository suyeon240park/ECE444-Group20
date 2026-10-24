/**
 * Mock analysis responses in the #20 / #43 format, for building and previewing the results
 * page without a backend (#41). Four were captured from the real pipeline (recorded Open Food
 * Facts and Gemini replies from the backend's end-to-end tests); `flagged` swaps in the
 * documented ingredient example, because no product in those tests has a flagged ingredient.
 */
import type { AnalysisResult } from '../productResult';
import complete from './complete.json';
import flagged from './flagged.json';
import incomplete from './incomplete.json';
import nutritionOnly from './nutrition_only.json';
import sectionsUnavailable from './sections_unavailable.json';

export const MOCKS = {
  /** A product with everything: per-serving and whole-package nutrition, explanations, ingredients. */
  complete: complete as unknown as AnalysisResult,
  /** Open Food Facts has per-100 g values only and no ingredients. */
  incomplete: incomplete as unknown as AnalysisResult,
  /** A Nutrition Facts photo with no product identified; every value waits for confirmation. */
  nutrition_only: nutritionOnly as unknown as AnalysisResult,
  /** A product whose ingredient analysis flags one ingredient, and leaves one unmatched. */
  flagged: flagged as unknown as AnalysisResult,
  /** Every analysis section failed on the server and came back null. */
  sections_unavailable: sectionsUnavailable as unknown as AnalysisResult,
} as const;

export type MockName = keyof typeof MOCKS;

export function isMockName(value: string | null): value is MockName {
  return value !== null && value in MOCKS;
}

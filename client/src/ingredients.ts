/** Reusable #33 contract for #40/#43. The current lookup endpoint is unchanged. */
export type IngredientStatus = 'unavailable' | 'no_matches' | 'analyzed';
export type IngredientAuthority = 'health_canada' | 'efsa' | 'fda' | 'who_jecfa';
export type IngredientFlagCategory = 'authority_action' | 'conflicting_assessments';

export type IngredientSourcedText = {
  text: string;
  source_ids: string[];
};

export type IngredientSource = {
  id: string;
  publisher: string;
  title: string;
  url: string;
  published_on: string | null;
  accessed_on: string;
};

export type IngredientAuthorityPosition = {
  id: string;
  authority: IngredientAuthority;
  statement: string;
  scope: string;
  source_ids: string[];
  assessed_on: string | null;
  effective_on: string | null;
};

export type IngredientFlag = {
  flag_reason: string;
  category: IngredientFlagCategory;
  source_ids: string[];
  position_ids: string[];
};

export type IngredientEntry = {
  id: string;
  name: string;
  aliases: string[];
  e_numbers: string[];
  ins_numbers: string[];
  what_it_is: IngredientSourcedText;
  why_used: IngredientSourcedText;
  explanation: IngredientSourcedText;
  sources: IngredientSource[];
  last_reviewed: string;
  authority_positions: IngredientAuthorityPosition[];
  flag: IngredientFlag | null;
};

export type IngredientOccurrence = {
  text: string;
  /** Zero-based section/token/nesting path; not character offsets. */
  path: number[];
};

export type MatchedIngredient = {
  ingredient: IngredientEntry;
  occurrences: IngredientOccurrence[];
};

export type UnmatchedIngredient = {
  text: string;
  occurrences: IngredientOccurrence[];
};

export type IngredientWarning = {
  code:
    | 'unbalanced_brackets'
    | 'ambiguous_group'
    | 'ambiguous_oil_component'
    | 'nesting_limit'
    | 'text_limit'
    | 'ignored_preamble'
    | 'no_ingredient_candidates';
  text: string;
};

export type IngredientAnalysisResult = {
  status: IngredientStatus;
  checked_count: number;
  total_count: number;
  flagged_count: number;
  matched: MatchedIngredient[];
  unmatched: UnmatchedIngredient[];
  flagged_ids: string[];
  warnings: IngredientWarning[];
  message: string | null;
  coverage_text: string | null;
};

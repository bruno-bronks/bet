// ── Request ────────────────────────────────────────────────────────────────

export interface PredictRequest {
  competition: 'brasileirao' | 'champions_league'
  home_team: string
  away_team: string
  match_date: string // YYYY-MM-DD
  stage?: string
  matchday?: number
  include_explanation?: boolean
}

// ── Response ───────────────────────────────────────────────────────────────

export interface MatchInfo {
  competition: string
  home_team: string
  away_team: string
  match_date: string
}

export interface OutcomeProbs {
  home_win: number
  draw: number
  away_win: number
}

export interface Scoreline {
  scoreline: string
  home_goals: number
  away_goals: number
  probability: number
}

export interface GoalsInfo {
  expected_goals_home: number
  expected_goals_away: number
  expected_goals_total: number
  over_0_5: number
  over_1_5: number
  over_2_5: number
  over_3_5: number
  over_4_5: number
  both_teams_score: number
  clean_sheet_home: number
  clean_sheet_away: number
  top_scorelines: Scoreline[]
}

export interface CornersInfo {
  expected_corners_total: number
  expected_corners_home: number
  expected_corners_away: number
}

export interface CardsInfo {
  expected_cards_total: number
  expected_cards_home: number
  expected_cards_away: number
}

export interface TimeWindowsInfo {
  goal_first_15min: number
  goal_last_15min: number
  goal_first_half: number
  goal_second_half: number
}

export interface FeatureImportance {
  feature: string
  importance?: number
  shap_importance?: number
  method: string
}

export interface ExplainabilityInfo {
  top_features: FeatureImportance[]
  confidence_score: number
  low_confidence_warning: boolean
}

export interface PredictResponse {
  match: MatchInfo
  outcome: OutcomeProbs
  goals: GoalsInfo
  corners: CornersInfo
  cards: CardsInfo
  time_windows: TimeWindowsInfo
  explainability: ExplainabilityInfo
  warnings: string[]
  natural_language_explanation?: string
  disclaimer: string
}

// ── Models ─────────────────────────────────────────────────────────────────

export interface ModelItem {
  key: string
  competition: string
  model_type: string
  path?: string
  metrics: Record<string, unknown>
}

export interface ModelsResponse {
  models: ModelItem[]
  total: number
}

export interface HealthResponse {
  status: string
  version: string
  supported_competitions: string[]
}

export interface TrainRequest {
  competition: string
  force_retrain?: boolean
}

export interface TrainResponse {
  status: string
  competition: string
  metrics: Record<string, unknown>
  message: string
}

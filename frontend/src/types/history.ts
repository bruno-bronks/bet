// Types for the History / Backtesting page

export interface MatchActual {
  home_goals: number
  away_goals: number
  outcome: 'H' | 'D' | 'A'
  total_goals: number
  btts: boolean
  home_cards: number | null
  away_cards: number | null
  total_cards: number | null
  home_corners: number | null
  away_corners: number | null
  total_corners: number | null
  first_half_goals: number | null
  goal_first_half: boolean | null
}

export interface MatchPredSummary {
  home_win: number
  draw: number
  away_win: number
  predicted_outcome: 'H' | 'D' | 'A'
  over_2_5: number
  btts: number
  expected_home_goals: number
  expected_away_goals: number
  expected_total_cards: number
  expected_total_corners: number
  goal_first_half: number
}

export interface MatchAccuracy {
  outcome_correct: boolean
  over_2_5_correct: boolean | null
  btts_correct: boolean | null
  cards_diff: number | null
  corners_diff: number | null
  first_half_correct: boolean | null
}

export interface HistoryMatch {
  date: string
  matchday: number | null
  stage: string | null
  home_team: string
  away_team: string
  actual: MatchActual
  prediction: MatchPredSummary | null
  accuracy: MatchAccuracy | null
}

export interface HistorySummary {
  total_matches: number
  outcome_accuracy: number | null
  over_2_5_accuracy: number | null
  btts_accuracy: number | null
  avg_cards_diff: number | null
  avg_corners_diff: number | null
}

export interface HistoryResponse {
  competition: string
  season: number | null
  count: number
  matches: HistoryMatch[]
  summary: HistorySummary
}

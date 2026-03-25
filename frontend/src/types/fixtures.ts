// Types for fixtures, standings and recent results

export interface OutcomeProbsSlim {
  home_win: number
  draw: number
  away_win: number
}

export interface RefereeStats {
  name: string
  matches_analyzed: number
  avg_yellow_per_game: number
  avg_red_per_game: number
  avg_cards_per_game: number
  avg_cards_home_team: number | null
  avg_cards_away_team: number | null
  home_team_matches: number
  away_team_matches: number
  home_team_general_avg_cards: number | null
  away_team_general_avg_cards: number | null
}

export interface FixtureItem {
  fixture_id: number
  home_team: string
  away_team: string
  home_team_logo: string
  away_team_logo: string
  date: string        // YYYY-MM-DD
  time: string        // HH:MM
  matchday: number | null
  stage: string
  venue: string
  status: string      // NS, FT, etc.
  home_score: number | null
  away_score: number | null
  referee: string | null
}

export interface FixtureWithPrediction extends FixtureItem {
  prediction: OutcomeProbsSlim | null
}

export interface StandingItem {
  position: number
  team: string
  team_logo: string
  played: number
  won: number
  drawn: number
  lost: number
  goals_for: number
  goals_against: number
  goal_diff: number
  points: number
  form: string
  description: string
}

export interface StandingsResponse {
  competition: string
  season: number
  standings: StandingItem[]
}

export interface FixturesResponse {
  competition: string
  season_label: string
  count: number
  fixtures: FixtureWithPrediction[]
}

export interface RecentResponse {
  competition: string
  count: number
  fixtures: FixtureItem[]
}

export interface TeamCardStats {
  home_as_home: number | null   // mandante jogando em casa
  away_as_away: number | null   // visitante jogando fora
  home_avg: number | null       // média geral do mandante
  away_avg: number | null       // média geral do visitante
}

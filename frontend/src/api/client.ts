import axios from 'axios'
import type {
  PredictRequest,
  PredictResponse,
  ModelsResponse,
  HealthResponse,
  TrainRequest,
  TrainResponse,
} from '../types/prediction'
import type { FixturesResponse, StandingsResponse, RecentResponse, RefereeStats, TeamCardStats } from '../types/fixtures'
import type { HistoryResponse } from '../types/history'

const BASE = '/api/v1'

const http = axios.create({ baseURL: '/', timeout: 90_000 })

// ── Response interceptor para erros ──────────────────────────────────────────
http.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg = err.response?.data?.detail ?? err.message ?? 'Unknown error'
    return Promise.reject(new Error(msg))
  }
)

// ── Endpoints ─────────────────────────────────────────────────────────────────

export const api = {
  health: (): Promise<HealthResponse> =>
    http.get('/health').then((r) => r.data),

  predict: (payload: PredictRequest): Promise<PredictResponse> =>
    http.post(`${BASE}/predict`, payload).then((r) => r.data),

  listModels: (): Promise<ModelsResponse> =>
    http.get(`${BASE}/models`).then((r) => r.data),

  train: (payload: TrainRequest): Promise<TrainResponse> =>
    http.post(`${BASE}/train`, payload).then((r) => r.data),

  getFixtures: (competition: string, daysAhead = 14): Promise<FixturesResponse> =>
    http.get(`${BASE}/fixtures`, { params: { competition, days_ahead: daysAhead } }).then((r) => r.data),

  getStandings: (competition: string): Promise<StandingsResponse> =>
    http.get(`${BASE}/standings`, { params: { competition } }).then((r) => r.data),

  getRecent: (competition: string, limit = 10): Promise<RecentResponse> =>
    http.get(`${BASE}/recent`, { params: { competition, limit } }).then((r) => r.data),

  getRefereeStats: (
    referee: string,
    competition: string,
    homeTeam: string,
    awayTeam: string,
  ): Promise<RefereeStats> =>
    http.get(`${BASE}/referee-stats`, {
      params: { referee, competition, home_team: homeTeam, away_team: awayTeam },
    }).then((r) => r.data),

  getTeamCardStats: (
    competition: string,
    homeTeam: string,
    awayTeam: string,
  ): Promise<TeamCardStats> =>
    http.get(`${BASE}/team-card-stats`, {
      params: { competition, home_team: homeTeam, away_team: awayTeam },
    }).then((r) => r.data),

  getHistory: (competition: string, limit = 20, season?: number): Promise<HistoryResponse> =>
    http.get(`${BASE}/history`, { params: { competition, limit, season } }).then((r) => r.data),
}

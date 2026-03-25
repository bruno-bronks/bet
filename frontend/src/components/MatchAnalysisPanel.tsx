import { useEffect, useState } from 'react'
import { X, AlertCircle, ChevronDown, ChevronUp, ExternalLink, Scale } from 'lucide-react'
import { api } from '../api/client'
import type { PredictResponse } from '../types/prediction'
import type { FixtureWithPrediction, RefereeStats, TeamCardStats } from '../types/fixtures'
import OutcomeChart from './OutcomeChart'
import GoalsPanel from './GoalsPanel'
import ScorelineGrid from './ScorelineGrid'
import TimeWindowCards from './TimeWindowCards'
import CornersCardsPanel from './CornersCardsPanel'
import ExplainabilityPanel from './ExplainabilityPanel'

interface Props {
  fixture: FixtureWithPrediction | null
  competition: string
  onClose: () => void
}

export default function MatchAnalysisPanel({ fixture, competition, onClose }: Props) {
  const [data, setData] = useState<PredictResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showExplain, setShowExplain] = useState(false)
  const [refereeStats, setRefereeStats] = useState<RefereeStats | null>(null)
  const [refereeLoading, setRefereeLoading] = useState(false)
  const [teamCardStats, setTeamCardStats] = useState<TeamCardStats | null>(null)

  useEffect(() => {
    if (!fixture) { setData(null); setError(null); setRefereeStats(null); return }

    setData(null)
    setError(null)
    setRefereeStats(null)
    setTeamCardStats(null)
    setLoading(true)

    api.predict({
      competition: competition as 'brasileirao' | 'champions_league',
      home_team: fixture.home_team,
      away_team: fixture.away_team,
      match_date: fixture.date,
      include_explanation: false,
    })
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))

    // Busca médias históricas de cartões dos times (sempre, independente do árbitro)
    api.getTeamCardStats(competition, fixture.home_team, fixture.away_team)
      .then(setTeamCardStats)
      .catch(() => {/* sem dados no CSV */})

    // Busca stats do árbitro de forma independente (não bloqueia o painel)
    if (fixture.referee) {
      setRefereeLoading(true)
      api.getRefereeStats(fixture.referee, competition, fixture.home_team, fixture.away_team)
        .then(setRefereeStats)
        .catch(() => {/* árbitro sem dados suficientes */})
        .finally(() => setRefereeLoading(false))
    }
  }, [fixture, competition])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  if (!fixture) return null

  const matchDateLabel = new Date(fixture.date + 'T12:00:00').toLocaleDateString('pt-BR', {
    weekday: 'long', day: '2-digit', month: 'long', year: 'numeric',
  })

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed inset-y-0 right-0 z-50 w-full md:w-[620px] lg:w-[680px] flex flex-col bg-white border-l border-gray-200 shadow-2xl overflow-hidden animate-slide-left">

        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-gray-200 bg-gray-50 shrink-0">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] uppercase tracking-widest text-gray-400 font-semibold">
                {competition === 'brasileirao' ? '🇧🇷 Brasileirão' : '🌍 Champions League'}
              </span>
              {fixture.matchday && (
                <span className="text-[10px] text-gray-400">· {fixture.matchday}</span>
              )}
            </div>
            <h2 className="text-lg font-bold text-gray-900 truncate">
              {fixture.home_team} vs {fixture.away_team}
            </h2>
            <p className="text-xs text-gray-500 mt-0.5 capitalize">
              {matchDateLabel}{fixture.time && fixture.time !== '00:00' ? ` · ${fixture.time}` : ''}
              {fixture.venue ? ` · ${fixture.venue}` : ''}
            </p>
            {fixture.referee && (
              <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                <Scale size={11} className="shrink-0" />
                {fixture.referee}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="ml-4 shrink-0 rounded-lg p-2 text-gray-400 hover:bg-gray-200 hover:text-gray-700 transition-all"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body — scrollable */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-gray-50">

          {/* Loading */}
          {loading && (
            <div className="space-y-4 animate-pulse">
              <div className="h-52 rounded-xl bg-gray-200" />
              <div className="h-48 rounded-xl bg-gray-200" />
              <div className="h-36 rounded-xl bg-gray-200" />
              <div className="h-32 rounded-xl bg-gray-200" />
            </div>
          )}

          {/* Error */}
          {error && !loading && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 flex flex-col items-center text-center gap-3">
              <AlertCircle size={32} className="text-rose-400" />
              <div>
                <p className="text-sm font-semibold text-rose-700">Análise não disponível</p>
                <p className="text-xs text-rose-500 mt-1 max-w-xs mx-auto">{error}</p>
              </div>
              <div className="text-xs text-gray-500 bg-gray-100 rounded-lg px-3 py-2 font-mono border border-gray-200">
                POST /api/v1/train {"{"}competition: "{competition}"{"}"}
              </div>
            </div>
          )}

          {/* Results */}
          {data && !loading && (
            <>
              {/* Disclaimer */}
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 flex items-center gap-2">
                <span className="text-amber-500 text-sm shrink-0">⚠</span>
                <p className="text-[11px] text-amber-700">{data.disclaimer}</p>
              </div>

              {/* Árbitro + Cartões — sempre visível */}
              {(() => {
                // Prioridade: 1) média no papel (casa/fora)  2) média geral  3) referee stats  4) modelo
                const homeGeneral = teamCardStats?.home_as_home
                  ?? teamCardStats?.home_avg
                  ?? refereeStats?.home_team_general_avg_cards
                  ?? data.cards.expected_cards_home
                const awayGeneral = teamCardStats?.away_as_away
                  ?? teamCardStats?.away_avg
                  ?? refereeStats?.away_team_general_avg_cards
                  ?? data.cards.expected_cards_away
                const hasHistoricalData = (teamCardStats?.home_as_home ?? teamCardStats?.home_avg) != null
                  || (teamCardStats?.away_as_away ?? teamCardStats?.away_avg) != null
                const homeWithRef = refereeStats?.avg_cards_home_team ?? null
                const awayWithRef = refereeStats?.avg_cards_away_team ?? null
                const homeDelta = homeWithRef != null ? homeWithRef - homeGeneral : null
                const awayDelta = awayWithRef != null ? awayWithRef - awayGeneral : null

                const teamCard = (
                  name: string,
                  withRef: number | null,
                  general: number,
                  delta: number | null,
                  matches: number
                ) => {
                  const isMore = delta != null && delta > 0.1
                  const isLess = delta != null && delta < -0.1
                  return (
                    <div className={`rounded-lg border px-3 py-2.5 ${isMore ? 'bg-red-50 border-red-100' : isLess ? 'bg-green-50 border-green-100' : 'bg-gray-50 border-gray-100'}`}>
                      <p className="text-[10px] text-gray-400 mb-1.5 truncate font-semibold uppercase tracking-wide">{name}</p>
                      {/* Média histórica (CSV) ou esperados (modelo) */}
                      <div className="flex items-baseline gap-1 mb-1">
                        <span className="text-sm font-bold text-gray-700 tabular-nums">{general.toFixed(2)}</span>
                        <span className="text-[10px] text-gray-400">{hasHistoricalData ? 'últ. temporada' : 'cart. esperados'}</span>
                      </div>
                      {/* Com árbitro específico */}
                      {withRef != null && (
                        <>
                          <div className="flex items-baseline gap-1">
                            <span className={`text-sm font-bold tabular-nums ${isMore ? 'text-red-600' : isLess ? 'text-green-600' : 'text-gray-600'}`}>
                              {withRef.toFixed(1)}
                            </span>
                            <span className="text-[10px] text-gray-400">c/ este árb.</span>
                          </div>
                          {delta != null && Math.abs(delta) > 0.1 && (
                            <p className={`text-[10px] font-semibold mt-1 ${isMore ? 'text-red-500' : 'text-green-500'}`}>
                              {isMore ? '▲' : '▼'} {Math.abs(delta).toFixed(1)} {isMore ? 'a mais' : 'a menos'}
                            </p>
                          )}
                          {delta != null && Math.abs(delta) <= 0.1 && (
                            <p className="text-[10px] text-gray-400 mt-1">= dentro da média</p>
                          )}
                          {matches > 0 && (
                            <p className="text-[10px] text-gray-300 mt-0.5">{matches} jg c/ árb.</p>
                          )}
                        </>
                      )}
                    </div>
                  )
                }

                return (
                  <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
                    {/* Cabeçalho */}
                    <div className="flex items-center gap-2 mb-3">
                      <Scale size={13} className="text-gray-400 shrink-0" />
                      <span className="text-xs font-semibold text-gray-700">Árbitro &amp; Cartões</span>
                      {refereeLoading && (
                        <span className="text-[10px] text-gray-400 animate-pulse">carregando árbitro...</span>
                      )}
                      {!refereeLoading && fixture.referee && !refereeStats && (
                        <span className="text-[10px] text-gray-400 truncate">{fixture.referee} — sem dados históricos</span>
                      )}
                      {!refereeLoading && !fixture.referee && (
                        <span className="text-[10px] text-gray-400">árbitro não anunciado</span>
                      )}
                      {refereeStats && (
                        <>
                          <span className="text-xs text-gray-600 font-medium truncate">{refereeStats.name}</span>
                          <span className="ml-auto text-[10px] text-gray-400 shrink-0 whitespace-nowrap">
                            {refereeStats.matches_analyzed} jg analisados
                          </span>
                        </>
                      )}
                    </div>

                    {/* Média do árbitro (só quando disponível) */}
                    {refereeStats && (
                      <div className="rounded-lg bg-blue-50 border border-blue-100 px-3 py-2 mb-2 flex items-center gap-3">
                        <span className="text-[10px] text-blue-500 font-medium shrink-0">Árbitro / jogo</span>
                        <span className="text-sm font-bold text-blue-700 tabular-nums">
                          {refereeStats.avg_cards_per_game.toFixed(1)} cartões
                        </span>
                        <span className="text-[10px] text-blue-400 tabular-nums ml-auto">
                          🟡 {refereeStats.avg_yellow_per_game.toFixed(1)}&nbsp; 🔴 {refereeStats.avg_red_per_game.toFixed(1)}
                        </span>
                      </div>
                    )}

                    {/* Cards por time */}
                    <div className="grid grid-cols-2 gap-2">
                      {teamCard(data.match.home_team, homeWithRef, homeGeneral, homeDelta, refereeStats?.home_team_matches ?? 0)}
                      {teamCard(data.match.away_team, awayWithRef, awayGeneral, awayDelta, refereeStats?.away_team_matches ?? 0)}
                    </div>
                  </div>
                )
              })()}

              {/* 1X2 */}
              <OutcomeChart
                outcome={data.outcome}
                homeTeam={data.match.home_team}
                awayTeam={data.match.away_team}
              />

              {/* Goals */}
              <GoalsPanel
                goals={data.goals}
                homeTeam={data.match.home_team}
                awayTeam={data.match.away_team}
              />

              {/* Scorelines */}
              <ScorelineGrid
                scorelines={data.goals.top_scorelines}
                homeTeam={data.match.home_team}
                awayTeam={data.match.away_team}
              />

              {/* Time windows */}
              <TimeWindowCards timeWindows={data.time_windows} />

              {/* Corners + Cards */}
              <CornersCardsPanel
                corners={data.corners}
                cards={data.cards}
                homeTeam={data.match.home_team}
                awayTeam={data.match.away_team}
              />

              {/* Explainability (collapsible) */}
              <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
                <button
                  onClick={() => setShowExplain((v) => !v)}
                  className="w-full flex items-center justify-between p-4 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  <span>Explicabilidade & Confiança</span>
                  {showExplain ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </button>
                {showExplain && (
                  <div className="px-4 pb-4 border-t border-gray-100 pt-3">
                    <ExplainabilityPanel
                      explain={data.explainability}
                      explanation={data.natural_language_explanation}
                      warnings={data.warnings}
                    />
                  </div>
                )}
              </div>

              {/* Link to full page */}
              <a
                href={`/predict?home=${encodeURIComponent(fixture.home_team)}&away=${encodeURIComponent(fixture.away_team)}&comp=${competition}&date=${fixture.date}`}
                className="flex items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 px-4 py-3 text-sm text-gray-500 hover:text-gray-700 transition-all"
              >
                <ExternalLink size={14} />
                Abrir análise completa
              </a>
            </>
          )}
        </div>
      </div>
    </>
  )
}

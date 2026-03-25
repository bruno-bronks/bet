import { AlertCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import CornersCardsPanel from '../components/CornersCardsPanel'
import ExplainabilityPanel from '../components/ExplainabilityPanel'
import GoalsPanel from '../components/GoalsPanel'
import MatchForm from '../components/MatchForm'
import OutcomeChart from '../components/OutcomeChart'
import ScorelineGrid from '../components/ScorelineGrid'
import TimeWindowCards from '../components/TimeWindowCards'
import { usePrediction } from '../hooks/usePrediction'
import type { PredictRequest } from '../types/prediction'

export default function Predict() {
  const { data, loading, error, predict, reset } = usePrediction()
  const [showExplain, setShowExplain] = useState(false)

  const handleSubmit = (req: PredictRequest) => {
    reset()
    predict(req)
  }

  return (
    <div className="min-h-screen bg-gray-50 pt-20 pb-16">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Análise Manual de Partida</h1>
          <p className="mt-1 text-sm text-gray-500">
            Estimativas probabilísticas baseadas em dados históricos.
            Não constituem previsão garantida.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Left: Form */}
          <div className="lg:col-span-1">
            <div className="sticky top-24">
              <MatchForm onSubmit={handleSubmit} loading={loading} />
            </div>
          </div>

          {/* Right: Results */}
          <div className="lg:col-span-2 space-y-4">

            {/* Error */}
            {error && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 flex items-start gap-3 animate-fade-in">
                <AlertCircle size={18} className="text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-rose-700">Erro na análise</p>
                  <p className="text-xs text-rose-500 mt-0.5">{error}</p>
                </div>
              </div>
            )}

            {/* Loading skeleton */}
            {loading && (
              <div className="space-y-4 animate-pulse">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-48 rounded-xl bg-gray-200" />
                ))}
              </div>
            )}

            {/* Results */}
            {data && !loading && (
              <div className="space-y-4 animate-slide-up">

                {/* Disclaimer banner */}
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 flex items-center gap-2">
                  <span className="text-amber-500 text-sm">⚠</span>
                  <p className="text-xs text-amber-700">{data.disclaimer}</p>
                </div>

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
                    className="w-full flex items-center justify-between p-5 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    <span>Explicabilidade & Confiança</span>
                    {showExplain ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>

                  {showExplain && (
                    <div className="px-5 pb-5 border-t border-gray-100 pt-4 animate-fade-in">
                      <ExplainabilityPanel
                        explain={data.explainability}
                        explanation={data.natural_language_explanation}
                        warnings={data.warnings}
                      />
                    </div>
                  )}
                </div>

              </div>
            )}

            {/* Empty state */}
            {!data && !loading && !error && (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 py-24 text-center bg-white">
                <div className="text-5xl mb-4">⚽</div>
                <p className="text-gray-500 font-medium">Configure a partida e clique em Analisar</p>
                <p className="text-gray-400 text-sm mt-1">Os resultados aparecerão aqui</p>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  )
}

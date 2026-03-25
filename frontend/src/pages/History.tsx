import { useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, XCircle, Minus } from 'lucide-react'
import { api } from '../api/client'
import type { HistoryMatch, HistoryResponse } from '../types/history'
import { clsx } from 'clsx'

type Competition = 'brasileirao' | 'champions_league'

const COMP_INFO: Record<Competition, { label: string; flag: string }> = {
  brasileirao: { label: 'Brasileirão', flag: '🇧🇷' },
  champions_league: { label: 'Champions League', flag: '🌍' },
}

const OUTCOME_LABEL: Record<'H' | 'D' | 'A', string> = {
  H: 'Casa (1)',
  D: 'Empate (X)',
  A: 'Fora (2)',
}

// ── AccuracyPill ──────────────────────────────────────────────────────────────

function AccuracyPill({
  correct,
  label,
}: {
  correct: boolean | null
  label?: string
}) {
  if (correct === null)
    return (
      <span className="inline-flex items-center gap-0.5 text-[10px] text-gray-300">
        <Minus size={10} />
        {label && <span>{label}</span>}
      </span>
    )
  if (correct)
    return (
      <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-600">
        <CheckCircle2 size={11} />
        {label && <span>{label}</span>}
      </span>
    )
  return (
    <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-rose-500">
      <XCircle size={11} />
      {label && <span>{label}</span>}
    </span>
  )
}

// ── DiffBadge ─────────────────────────────────────────────────────────────────

function DiffBadge({ diff, threshold = 1.5 }: { diff: number | null; threshold?: number }) {
  if (diff === null) return <span className="text-[10px] text-gray-300">—</span>
  const good = diff <= threshold
  return (
    <span
      className={clsx(
        'text-[10px] font-mono',
        good ? 'text-emerald-600' : diff <= threshold * 2 ? 'text-amber-500' : 'text-rose-500',
      )}
    >
      ±{diff.toFixed(1)}
    </span>
  )
}

// ── SummaryBar ────────────────────────────────────────────────────────────────

function SummaryBar({ summary }: { summary: HistoryResponse['summary'] }) {
  const { total_matches, outcome_accuracy, over_2_5_accuracy, btts_accuracy, avg_cards_diff, avg_corners_diff } =
    summary

  if (total_matches === 0) return null

  const pct = (v: number | null) => (v != null ? `${Math.round(v * 100)}%` : '—')
  const n = (v: number | null, tot: number) => (v != null ? `${Math.round(v * tot)}/${tot}` : '—')

  return (
    <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 mb-4">
      <p className="text-[10px] uppercase tracking-widest text-blue-400 font-semibold mb-2">
        Resumo — {total_matches} partida{total_matches !== 1 ? 's' : ''} com previsão
      </p>
      <div className="flex flex-wrap gap-3">
        <StatChip label="Resultado" value={pct(outcome_accuracy)} sub={n(outcome_accuracy, total_matches)} />
        <StatChip label="Over 2.5" value={pct(over_2_5_accuracy)} sub={n(over_2_5_accuracy, total_matches)} />
        <StatChip label="BTTS" value={pct(btts_accuracy)} sub={n(btts_accuracy, total_matches)} />
        {avg_cards_diff != null && (
          <StatChip label="Cartões" value={`±${avg_cards_diff.toFixed(1)}`} sub="desvio médio" />
        )}
        {avg_corners_diff != null && (
          <StatChip label="Cantos" value={`±${avg_corners_diff.toFixed(1)}`} sub="desvio médio" />
        )}
      </div>
    </div>
  )
}

function StatChip({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="flex flex-col items-center bg-white border border-blue-100 rounded-lg px-3 py-1.5 min-w-[70px]">
      <span className="text-[10px] text-gray-400 uppercase tracking-wide">{label}</span>
      <span className="text-sm font-bold text-blue-700">{value}</span>
      <span className="text-[10px] text-gray-400">{sub}</span>
    </div>
  )
}

// ── PredCell ──────────────────────────────────────────────────────────────────

function PredCell({
  label,
  predicted,
  actual,
  correct,
}: {
  label: string
  predicted: string
  actual: string
  correct: boolean | null
}) {
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-[9px] uppercase tracking-widest text-gray-400 font-semibold">{label}</span>
      <div className="flex items-center gap-1">
        <AccuracyPill correct={correct} />
        <span className="text-[11px] font-semibold text-gray-700 truncate">{predicted}</span>
      </div>
      <span className="text-[10px] text-gray-400 truncate">real: {actual}</span>
    </div>
  )
}

// ── HistoryCard ───────────────────────────────────────────────────────────────

function HistoryCard({ match }: { match: HistoryMatch }) {
  const { actual, prediction: pred, accuracy: acc } = match

  const dateLabel = new Date(match.date + 'T12:00:00').toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'short',
  })

  const outcomeLabel = (o: 'H' | 'D' | 'A') => OUTCOME_LABEL[o]

  const pct = (v: number) => `${Math.round(v * 100)}%`

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      {/* Header: placar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50">
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span>{dateLabel}</span>
          {match.matchday && <span>· Rodada {match.matchday}</span>}
          {match.stage && !match.matchday && <span>· {match.stage}</span>}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-gray-800 text-right max-w-[130px] truncate">
            {match.home_team}
          </span>
          <span className="text-base font-bold text-gray-900 px-3 py-0.5 bg-white border border-gray-200 rounded-md tabular-nums">
            {actual.home_goals} – {actual.away_goals}
          </span>
          <span className="text-sm font-semibold text-gray-800 max-w-[130px] truncate">{match.away_team}</span>
        </div>
        <div className="w-20" />
      </div>

      {/* Corpo: comparação */}
      {pred && acc ? (
        <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {/* Resultado */}
          <PredCell
            label="Resultado"
            predicted={`${outcomeLabel(pred.predicted_outcome)} (${pct(Math.max(pred.home_win, pred.draw, pred.away_win))})`}
            actual={outcomeLabel(actual.outcome)}
            correct={acc.outcome_correct}
          />

          {/* Over 2.5 */}
          <PredCell
            label="Over 2.5"
            predicted={`${pct(pred.over_2_5)} → ${pred.over_2_5 > 0.5 ? 'Sim' : 'Não'}`}
            actual={`${actual.total_goals} gols → ${actual.total_goals > 2 ? 'Sim' : 'Não'}`}
            correct={acc.over_2_5_correct}
          />

          {/* BTTS */}
          <PredCell
            label="Ambas marcam"
            predicted={`${pct(pred.btts)} → ${pred.btts > 0.5 ? 'Sim' : 'Não'}`}
            actual={actual.btts ? 'Sim' : 'Não'}
            correct={acc.btts_correct}
          />

          {/* Gols xG */}
          <div className="flex flex-col gap-0.5 min-w-0">
            <span className="text-[9px] uppercase tracking-widest text-gray-400 font-semibold">Gols (xG)</span>
            <span className="text-[11px] font-semibold text-gray-700">
              {pred.expected_home_goals.toFixed(1)} / {pred.expected_away_goals.toFixed(1)}
            </span>
            <span className="text-[10px] text-gray-400">
              real: {actual.home_goals} – {actual.away_goals}
            </span>
          </div>

          {/* Cartões */}
          <div className="flex flex-col gap-0.5 min-w-0">
            <span className="text-[9px] uppercase tracking-widest text-gray-400 font-semibold">Cartões</span>
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-semibold text-gray-700">
                {pred.expected_total_cards.toFixed(1)}
              </span>
              {actual.total_cards != null && <DiffBadge diff={acc.cards_diff} threshold={1.5} />}
            </div>
            <span className="text-[10px] text-gray-400">
              real: {actual.total_cards ?? '—'}
            </span>
          </div>

          {/* Cantos */}
          <div className="flex flex-col gap-0.5 min-w-0">
            <span className="text-[9px] uppercase tracking-widest text-gray-400 font-semibold">Cantos</span>
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-semibold text-gray-700">
                {pred.expected_total_corners.toFixed(1)}
              </span>
              {actual.total_corners != null && <DiffBadge diff={acc.corners_diff} threshold={2} />}
            </div>
            <span className="text-[10px] text-gray-400">
              real: {actual.total_corners ?? '—'}
            </span>
          </div>
        </div>
      ) : (
        <div className="px-4 py-2 text-[11px] text-gray-400 italic">
          Sem previsão disponível para esta partida
        </div>
      )}

      {/* Gol 1° tempo — linha extra quando disponível */}
      {pred && acc && actual.goal_first_half != null && (
        <div className="px-4 pb-2.5 flex items-center gap-2">
          <span className="text-[9px] uppercase tracking-widest text-gray-400 font-semibold">Gol 1° tempo</span>
          <AccuracyPill correct={acc.first_half_correct} />
          <span className="text-[10px] text-gray-500">
            prev: {pct(pred.goal_first_half)} · real: {actual.goal_first_half ? 'Sim' : 'Não'}
          </span>
        </div>
      )}
    </div>
  )
}

// ── Loading skeleton ──────────────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-gray-200 bg-white overflow-hidden">
          <div className="h-12 bg-gray-100" />
          <div className="px-4 py-3 grid grid-cols-6 gap-3">
            {Array.from({ length: 6 }).map((_, j) => (
              <div key={j} className="h-10 bg-gray-100 rounded" />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function History() {
  const [competition, setCompetition] = useState<Competition>('brasileirao')
  const [data, setData] = useState<HistoryResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setData(null)
    setError(null)
    setLoading(true)
    api
      .getHistory(competition, 30)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [competition])

  const compInfo = COMP_INFO[competition]

  return (
    <div className="min-h-screen bg-gray-50 pt-20 pb-10">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">

        {/* Page header */}
        <div className="mb-6">
          <h1 className="text-xl font-bold text-gray-900">Histórico de Partidas</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Partidas realizadas comparadas com as previsões do modelo
          </p>
        </div>

        {/* Competition tabs */}
        <div className="flex gap-2 mb-5">
          {(Object.keys(COMP_INFO) as Competition[]).map((c) => {
            const info = COMP_INFO[c]
            return (
              <button
                key={c}
                onClick={() => setCompetition(c)}
                className={clsx(
                  'flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-all',
                  competition === c
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50',
                )}
              >
                <span>{info.flag}</span>
                {info.label}
              </button>
            )
          })}
        </div>

        {/* Summary */}
        {data && !loading && <SummaryBar summary={data.summary} />}

        {/* Content */}
        {loading && <LoadingSkeleton />}

        {error && !loading && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 flex items-center gap-3">
            <AlertCircle size={20} className="text-rose-400 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-rose-700">Erro ao carregar histórico</p>
              <p className="text-xs text-rose-500 mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {data && !loading && data.count === 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-8 text-center">
            <p className="text-sm text-gray-500">Nenhuma partida finalizada encontrada para {compInfo.label}.</p>
          </div>
        )}

        {data && !loading && data.count > 0 && (
          <div className="space-y-3">
            {data.matches.map((m, i) => (
              <HistoryCard key={`${m.date}-${m.home_team}-${i}`} match={m} />
            ))}
          </div>
        )}

      </div>
    </div>
  )
}

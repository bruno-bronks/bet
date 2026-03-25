import { useEffect, useState } from 'react'
import { Calendar, Trophy, Clock, ChevronDown, ChevronUp, AlertCircle, WifiOff } from 'lucide-react'
import { api } from '../api/client'
import type { FixtureWithPrediction, StandingItem, FixtureItem } from '../types/fixtures'
import { clsx } from 'clsx'

type Competition = 'brasileirao' | 'champions_league'

const COMP_INFO: Record<Competition, { label: string; flag: string; activeClass: string }> = {
  brasileirao: { label: 'Brasileirão', flag: '🇧🇷', activeClass: 'bg-green-50 text-green-700 ring-1 ring-green-200' },
  champions_league: { label: 'Champions League', flag: '🌍', activeClass: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200' },
}

function ProbBar({ label, value, bg, text }: { label: string; value: number; bg: string; text: string }) {
  const pct = Math.round(value * 100)
  return (
    <div className="flex flex-col items-center gap-1 min-w-[48px]">
      <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
        <div className={`h-full rounded-full ${bg}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-[10px] font-mono font-medium ${text}`}>{label} {pct}%</span>
    </div>
  )
}

function FixtureCard({ f }: { f: FixtureWithPrediction }) {
  const matchDate = new Date(f.date + 'T12:00:00')
  const dayLabel = matchDate.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' })
  const isFinished = ['FT', 'AET', 'PEN'].includes(f.status)

  return (
    <div className="rounded-xl border border-gray-200 bg-white px-4 py-3 hover:border-gray-300 hover:shadow-sm transition-all">
      <div className="flex items-center gap-3">

        {/* Time info */}
        <div className="flex flex-col items-center w-14 shrink-0">
          <span className="text-[10px] text-gray-400 uppercase">{dayLabel}</span>
          <span className="text-xs font-mono text-gray-500 mt-0.5 flex items-center gap-1">
            <Clock size={10} />
            {f.time || '--:--'}
          </span>
        </div>

        {/* Teams */}
        <div className="flex-1 min-w-0">
          {isFinished ? (
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-gray-800 truncate">{f.home_team}</span>
              <span className="text-sm font-bold text-gray-900 px-3 py-0.5 bg-gray-100 rounded-md tabular-nums border border-gray-200">
                {f.home_score} – {f.away_score}
              </span>
              <span className="text-sm font-medium text-gray-800 truncate text-right">{f.away_team}</span>
            </div>
          ) : (
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-gray-800 truncate">{f.home_team}</span>
              <span className="text-[10px] text-gray-400 px-2 shrink-0">vs</span>
              <span className="text-sm font-medium text-gray-800 truncate text-right">{f.away_team}</span>
            </div>
          )}

          {f.matchday != null && (
            <p className="text-[10px] text-gray-400 mt-0.5">Rodada {f.matchday}</p>
          )}
        </div>

        {/* Prediction bars */}
        {f.prediction && !isFinished ? (
          <div className="flex gap-2 shrink-0">
            <ProbBar label="1" value={f.prediction.home_win} bg="bg-emerald-500" text="text-emerald-600" />
            <ProbBar label="X" value={f.prediction.draw} bg="bg-gray-400" text="text-gray-500" />
            <ProbBar label="2" value={f.prediction.away_win} bg="bg-rose-500" text="text-rose-600" />
          </div>
        ) : !isFinished ? (
          <div className="text-[10px] text-gray-300 italic shrink-0">sem previsão</div>
        ) : null}
      </div>
    </div>
  )
}

function RecentCard({ f }: { f: FixtureItem }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-2.5">
      <span className="text-xs text-gray-400 w-20 shrink-0">
        {new Date(f.date + 'T12:00:00').toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })}
      </span>
      <span className="text-sm text-gray-700 truncate flex-1">{f.home_team}</span>
      <span className="text-sm font-bold text-gray-900 tabular-nums px-2 py-0.5 bg-gray-100 rounded border border-gray-200">
        {f.home_score != null ? `${f.home_score} – ${f.away_score}` : 'FT'}
      </span>
      <span className="text-sm text-gray-700 truncate flex-1 text-right">{f.away_team}</span>
    </div>
  )
}

function StandingsTable({ standings }: { standings: StandingItem[] }) {
  if (!standings.length) return null
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50 text-gray-400 uppercase tracking-wide">
            <th className="px-3 py-2.5 text-left w-8">#</th>
            <th className="px-3 py-2.5 text-left">Time</th>
            <th className="px-3 py-2.5 text-center">P</th>
            <th className="px-3 py-2.5 text-center">V</th>
            <th className="px-3 py-2.5 text-center">E</th>
            <th className="px-3 py-2.5 text-center">D</th>
            <th className="px-3 py-2.5 text-center">GP</th>
            <th className="px-3 py-2.5 text-center">GC</th>
            <th className="px-3 py-2.5 text-center">SG</th>
            <th className="px-3 py-2.5 text-center font-bold text-gray-600">Pts</th>
            <th className="px-3 py-2.5 text-center hidden sm:table-cell">Forma</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {standings.map((s) => (
            <tr key={s.position} className="hover:bg-gray-50 transition-colors">
              <td className="px-3 py-2 text-gray-400 tabular-nums">{s.position}</td>
              <td className="px-3 py-2 text-gray-800 font-medium whitespace-nowrap">
                {s.team_logo && (
                  <img src={s.team_logo} alt="" className="w-4 h-4 inline mr-2" />
                )}
                {s.team}
              </td>
              <td className="px-3 py-2 text-center text-gray-500 tabular-nums">{s.played}</td>
              <td className="px-3 py-2 text-center text-emerald-600 tabular-nums font-medium">{s.won}</td>
              <td className="px-3 py-2 text-center text-gray-400 tabular-nums">{s.drawn}</td>
              <td className="px-3 py-2 text-center text-rose-500 tabular-nums">{s.lost}</td>
              <td className="px-3 py-2 text-center text-gray-500 tabular-nums">{s.goals_for}</td>
              <td className="px-3 py-2 text-center text-gray-500 tabular-nums">{s.goals_against}</td>
              <td className="px-3 py-2 text-center text-gray-500 tabular-nums">
                {s.goal_diff > 0 ? `+${s.goal_diff}` : s.goal_diff}
              </td>
              <td className="px-3 py-2 text-center font-bold text-gray-900 tabular-nums">{s.points}</td>
              <td className="px-3 py-2 text-center hidden sm:table-cell">
                {s.form.split('').map((r, i) => (
                  <span
                    key={i}
                    className={clsx(
                      'inline-block w-4 h-4 rounded-sm text-[9px] font-bold leading-4 text-center mr-0.5',
                      r === 'W' && 'bg-emerald-100 text-emerald-600',
                      r === 'D' && 'bg-gray-100 text-gray-500',
                      r === 'L' && 'bg-rose-100 text-rose-500',
                    )}
                  >
                    {r}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function groupByDate(fixtures: FixtureWithPrediction[]): [string, FixtureWithPrediction[]][] {
  const map = new Map<string, FixtureWithPrediction[]>()
  for (const f of fixtures) {
    const arr = map.get(f.date) ?? []
    arr.push(f)
    map.set(f.date, arr)
  }
  return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b))
}

function formatDateHeader(dateStr: string): string {
  return new Date(dateStr + 'T12:00:00').toLocaleDateString('pt-BR', {
    weekday: 'long', day: '2-digit', month: 'long',
  })
}

export default function Fixtures() {
  const [comp, setComp] = useState<Competition>('brasileirao')
  const [fixtures, setFixtures] = useState<FixtureWithPrediction[]>([])
  const [standings, setStandings] = useState<StandingItem[]>([])
  const [recent, setRecent] = useState<FixtureItem[]>([])
  const [loadingFix, setLoadingFix] = useState(false)
  const [loadingStd, setLoadingStd] = useState(false)
  const [loadingRec, setLoadingRec] = useState(false)
  const [noApiKey, setNoApiKey] = useState(false)
  const [showStandings, setShowStandings] = useState(true)
  const [showRecent, setShowRecent] = useState(false)

  useEffect(() => {
    setFixtures([])
    setStandings([])
    setRecent([])
    setNoApiKey(false)

    setLoadingFix(true)
    api.getFixtures(comp, 21)
      .then((r) => {
        setFixtures(r.fixtures)
      })
      .catch(() => setNoApiKey(true))
      .finally(() => setLoadingFix(false))

    setLoadingStd(true)
    api.getStandings(comp)
      .then((r) => setStandings(r.standings))
      .catch(() => {})
      .finally(() => setLoadingStd(false))

    setLoadingRec(true)
    api.getRecent(comp, 10)
      .then((r) => setRecent(r.fixtures))
      .catch(() => {})
      .finally(() => setLoadingRec(false))
  }, [comp])

  const grouped = groupByDate(fixtures)

  return (
    <div className="min-h-screen bg-gray-50 pt-20 pb-16">
      <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Calendar size={22} className="text-blue-600" />
            Partidas
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Fixtures, classificação e resultados em tempo real
          </p>
        </div>

        {/* Competition tabs */}
        <div className="flex gap-2 mb-8">
          {(['brasileirao', 'champions_league'] as Competition[]).map((c) => {
            const ci = COMP_INFO[c]
            return (
              <button
                key={c}
                onClick={() => setComp(c)}
                className={clsx(
                  'flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all',
                  comp === c
                    ? ci.activeClass
                    : 'text-gray-500 border border-gray-200 bg-white hover:bg-gray-50 hover:text-gray-700'
                )}
              >
                <span>{ci.flag}</span>
                {ci.label}
              </button>
            )
          })}
        </div>

        {/* API Key warning */}
        {noApiKey && !loadingFix && (
          <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 mb-6">
            <WifiOff size={16} className="text-amber-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-700">API não configurada ou sem dados</p>
              <p className="text-xs text-amber-600 mt-1">
                Adicione sua chave em <code className="bg-amber-100 px-1 rounded">.env</code>:{' '}
                <code className="bg-amber-100 px-1 rounded">FOOTBALL_DATA_KEY=sua_chave</code>
              </p>
              <p className="text-xs text-amber-500 mt-1">
                Obtenha gratuitamente em football-data.org (inclui temporada atual)
              </p>
            </div>
          </div>
        )}

        {/* ── Próximas Partidas ─────────────────────────────────────────── */}
        <section className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Clock size={14} className="text-gray-400" />
            <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">
              Próximas Partidas
            </h2>
          </div>

          {loadingFix ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-14 rounded-xl bg-gray-200 animate-pulse" />
              ))}
            </div>
          ) : fixtures.length === 0 ? (
            <div className="flex flex-col items-center py-12 rounded-xl border border-dashed border-gray-300 bg-white">
              <AlertCircle size={28} className="text-gray-300 mb-3" />
              <p className="text-gray-500 text-sm">Nenhuma partida encontrada</p>
              <p className="text-gray-400 text-xs mt-1">
                {noApiKey ? 'Configure a chave da API para ver partidas reais' : 'Sem jogos nos próximos 21 dias'}
              </p>
            </div>
          ) : (
            <div className="space-y-5">
              {grouped.map(([dateStr, group]) => (
                <div key={dateStr}>
                  <p className="text-[10px] uppercase tracking-widest text-gray-400 mb-2 capitalize">
                    {formatDateHeader(dateStr)}
                  </p>
                  <div className="space-y-2">
                    {group.map((f) => <FixtureCard key={f.fixture_id} f={f} />)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ── Classificação ─────────────────────────────────────────────── */}
        <section className="mb-8">
          <button
            onClick={() => setShowStandings((v) => !v)}
            className="flex items-center gap-2 mb-4 w-full text-left group"
          >
            <Trophy size={14} className="text-gray-400" />
            <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400 flex-1">
              Classificação
            </h2>
            {showStandings
              ? <ChevronUp size={14} className="text-gray-400 group-hover:text-gray-600" />
              : <ChevronDown size={14} className="text-gray-400 group-hover:text-gray-600" />
            }
          </button>

          {showStandings && (
            loadingStd ? (
              <div className="space-y-1.5">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-8 rounded-lg bg-gray-200 animate-pulse" />
                ))}
              </div>
            ) : standings.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">
                {noApiKey ? 'Configure a API para ver a classificação' : 'Classificação não disponível'}
              </p>
            ) : (
              <StandingsTable standings={standings} />
            )
          )}
        </section>

        {/* ── Resultados Recentes ────────────────────────────────────────── */}
        <section>
          <button
            onClick={() => setShowRecent((v) => !v)}
            className="flex items-center gap-2 mb-4 w-full text-left group"
          >
            <Calendar size={14} className="text-gray-400" />
            <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400 flex-1">
              Resultados Recentes
            </h2>
            {showRecent
              ? <ChevronUp size={14} className="text-gray-400 group-hover:text-gray-600" />
              : <ChevronDown size={14} className="text-gray-400 group-hover:text-gray-600" />
            }
          </button>

          {showRecent && (
            loadingRec ? (
              <div className="space-y-1.5">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-10 rounded-lg bg-gray-200 animate-pulse" />
                ))}
              </div>
            ) : recent.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">
                {noApiKey ? 'Configure a API para ver resultados' : 'Sem resultados recentes'}
              </p>
            ) : (
              <div className="space-y-1.5">
                {recent.map((f) => <RecentCard key={f.fixture_id} f={f} />)}
              </div>
            )
          )}
        </section>

      </div>
    </div>
  )
}

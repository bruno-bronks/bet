import { useEffect, useState, useCallback } from 'react'
import {
  Calendar, Trophy, Clock, ChevronDown, ChevronUp,
  RefreshCw, WifiOff, TrendingUp, Activity, ServerOff,
} from 'lucide-react'
import { api } from '../api/client'
import type { FixtureWithPrediction, StandingItem, FixtureItem } from '../types/fixtures'
import MatchAnalysisPanel from '../components/MatchAnalysisPanel'
import { clsx } from 'clsx'

type Comp = 'brasileirao' | 'champions_league'

const COMP: Record<Comp, { label: string; flag: string; activeTab: string; inactiveTab: string }> = {
  brasileirao: {
    label: 'Brasileirão Série A',
    flag: '🇧🇷',
    activeTab: 'bg-green-50 text-green-700 ring-1 ring-green-200 border-green-200',
    inactiveTab: 'text-gray-500 border border-gray-200 hover:text-gray-700 hover:border-gray-300 hover:bg-gray-50',
  },
  champions_league: {
    label: 'UEFA Champions League',
    flag: '🌍',
    activeTab: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200 border-blue-200',
    inactiveTab: 'text-gray-500 border border-gray-200 hover:text-gray-700 hover:border-gray-300 hover:bg-gray-50',
  },
}

// ── Probability inline bars ────────────────────────────────────────────────────

function ProbMini({ hw, d, aw }: { hw: number; d: number; aw: number }) {
  const fmt = (v: number) => `${Math.round(v * 100)}%`
  return (
    <div className="flex items-center gap-3 text-xs">
      <div className="flex flex-col items-center min-w-[36px]">
        <div className="w-full h-1.5 rounded-full bg-gray-200 overflow-hidden mb-0.5">
          <div className="h-full bg-emerald-500 rounded-full" style={{ width: fmt(hw) }} />
        </div>
        <span className="text-emerald-600 font-mono font-semibold">{fmt(hw)}</span>
        <span className="text-gray-400 text-[9px]">1</span>
      </div>
      <div className="flex flex-col items-center min-w-[36px]">
        <div className="w-full h-1.5 rounded-full bg-gray-200 overflow-hidden mb-0.5">
          <div className="h-full bg-gray-400 rounded-full" style={{ width: fmt(d) }} />
        </div>
        <span className="text-gray-500 font-mono font-semibold">{fmt(d)}</span>
        <span className="text-gray-400 text-[9px]">X</span>
      </div>
      <div className="flex flex-col items-center min-w-[36px]">
        <div className="w-full h-1.5 rounded-full bg-gray-200 overflow-hidden mb-0.5">
          <div className="h-full bg-rose-500 rounded-full" style={{ width: fmt(aw) }} />
        </div>
        <span className="text-rose-600 font-mono font-semibold">{fmt(aw)}</span>
        <span className="text-gray-400 text-[9px]">2</span>
      </div>
    </div>
  )
}

// ── Fixture card ───────────────────────────────────────────────────────────────

function FixtureCard({
  f,
  onAnalyze,
}: {
  f: FixtureWithPrediction
  onAnalyze: (f: FixtureWithPrediction) => void
}) {
  const isFinished = ['FT', 'AET', 'PEN'].includes(f.status)

  return (
    <div className="group rounded-xl border border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm transition-all px-5 py-4">
      <div className="flex items-center gap-4">

        {/* Time */}
        <div className="text-center shrink-0 w-12">
          {isFinished ? (
            <span className="text-[10px] font-semibold text-gray-400 uppercase">FT</span>
          ) : (
            <span className="text-sm font-mono font-bold text-gray-700">
              {f.time && f.time !== '00:00' ? f.time : '--:--'}
            </span>
          )}
        </div>

        {/* Teams + score */}
        <div className="flex-1 min-w-0">
          {isFinished ? (
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-gray-800 truncate flex-1">{f.home_team}</span>
              <span className="px-3 py-1 rounded-lg bg-gray-100 text-gray-800 font-bold text-sm tabular-nums shrink-0 border border-gray-200">
                {f.home_score} – {f.away_score}
              </span>
              <span className="font-semibold text-sm text-gray-800 truncate flex-1 text-right">{f.away_team}</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              {f.home_team_logo && (
                <img src={f.home_team_logo} alt="" className="w-5 h-5 object-contain shrink-0" />
              )}
              <span className="font-semibold text-sm text-gray-800 truncate flex-1">{f.home_team}</span>
              <span className="text-gray-300 text-xs font-bold shrink-0">vs</span>
              <span className="font-semibold text-sm text-gray-800 truncate flex-1 text-right">{f.away_team}</span>
              {f.away_team_logo && (
                <img src={f.away_team_logo} alt="" className="w-5 h-5 object-contain shrink-0" />
              )}
            </div>
          )}
          {(f.venue || f.referee) && (
            <p className="text-[10px] text-gray-400 mt-0.5 truncate">
              {f.venue}
              {f.venue && f.referee ? ' · ' : ''}
              {f.referee ? `Árb: ${f.referee}` : ''}
            </p>
          )}
        </div>

        {/* Prediction or button */}
        <div className="shrink-0 flex items-center gap-3">
          {f.prediction && (
            <ProbMini hw={f.prediction.home_win} d={f.prediction.draw} aw={f.prediction.away_win} />
          )}
          <button
            onClick={() => onAnalyze(f)}
            className="rounded-lg border border-blue-200 bg-blue-50 hover:bg-blue-600 hover:border-blue-600 hover:text-white px-3 py-1.5 text-xs font-semibold text-blue-600 transition-all whitespace-nowrap"
          >
            Analisar →
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Recent result row ──────────────────────────────────────────────────────────

function RecentRow({ f }: { f: FixtureItem }) {
  const hw = f.home_score ?? 0
  const aw = f.away_score ?? 0
  const result = hw > aw ? 'H' : aw > hw ? 'A' : 'D'
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg border border-gray-200 bg-white">
      <span className="text-[10px] text-gray-400 w-16 shrink-0">
        {new Date(f.date + 'T12:00:00').toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })}
      </span>
      <span className={clsx('text-sm truncate flex-1', result === 'H' ? 'text-gray-900 font-semibold' : 'text-gray-500')}>
        {f.home_team}
      </span>
      <span className="font-bold text-gray-800 tabular-nums text-sm px-2 py-0.5 rounded bg-gray-100 border border-gray-200 shrink-0">
        {hw} – {aw}
      </span>
      <span className={clsx('text-sm truncate flex-1 text-right', result === 'A' ? 'text-gray-900 font-semibold' : 'text-gray-500')}>
        {f.away_team}
      </span>
    </div>
  )
}

// ── Standings table ────────────────────────────────────────────────────────────

function Standings({ standings, comp }: { standings: StandingItem[]; comp: Comp }) {
  if (!standings.length) return null
  const pointsColor = comp === 'brasileirao' ? 'text-green-600' : 'text-blue-600'

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-400 uppercase tracking-wide border-b border-gray-100 bg-gray-50">
            <th className="px-3 py-2.5 text-left w-7">#</th>
            <th className="px-3 py-2.5 text-left">Time</th>
            <th className="px-3 py-2.5 text-center w-8">P</th>
            <th className="px-3 py-2.5 text-center w-8 text-emerald-600">V</th>
            <th className="px-3 py-2.5 text-center w-8">E</th>
            <th className="px-3 py-2.5 text-center w-8 text-rose-500">D</th>
            <th className="px-3 py-2.5 text-center w-8">GP</th>
            <th className="px-3 py-2.5 text-center w-8">GC</th>
            <th className="px-3 py-2.5 text-center w-10">SG</th>
            <th className={`px-3 py-2.5 text-center w-10 font-bold ${pointsColor}`}>Pts</th>
            <th className="px-3 py-2.5 text-center hidden sm:table-cell">Forma</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {standings.map((s, idx) => {
            const isTop = idx < 4
            const isRelegation = idx >= standings.length - 4
            return (
              <tr
                key={s.position}
                className={clsx(
                  'transition-colors hover:bg-gray-50',
                  isTop && 'bg-emerald-50/60',
                  isRelegation && !isTop && 'bg-rose-50/60',
                )}
              >
                <td className="px-3 py-2.5">
                  <span className={clsx(
                    'text-xs font-bold tabular-nums',
                    isTop ? 'text-emerald-600' : isRelegation ? 'text-rose-500' : 'text-gray-400'
                  )}>
                    {s.position}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    {s.team_logo && (
                      <img src={s.team_logo} alt="" className="w-5 h-5 object-contain shrink-0" />
                    )}
                    <span className="text-gray-800 font-medium whitespace-nowrap">{s.team}</span>
                    {s.description && (
                      <span className="hidden lg:inline text-[9px] text-gray-400 truncate max-w-[80px]">{s.description}</span>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2.5 text-center text-gray-500 tabular-nums">{s.played}</td>
                <td className="px-3 py-2.5 text-center text-emerald-600 font-semibold tabular-nums">{s.won}</td>
                <td className="px-3 py-2.5 text-center text-gray-500 tabular-nums">{s.drawn}</td>
                <td className="px-3 py-2.5 text-center text-rose-500 tabular-nums">{s.lost}</td>
                <td className="px-3 py-2.5 text-center text-gray-500 tabular-nums">{s.goals_for}</td>
                <td className="px-3 py-2.5 text-center text-gray-500 tabular-nums">{s.goals_against}</td>
                <td className="px-3 py-2.5 text-center tabular-nums font-mono text-gray-500">
                  {s.goal_diff > 0 ? `+${s.goal_diff}` : s.goal_diff}
                </td>
                <td className={`px-3 py-2.5 text-center font-black tabular-nums ${pointsColor}`}>{s.points}</td>
                <td className="px-3 py-2.5 text-center hidden sm:table-cell">
                  <div className="flex justify-center gap-0.5">
                    {s.form.split('').slice(-5).map((r, i) => (
                      <span
                        key={i}
                        className={clsx(
                          'inline-flex w-4 h-4 rounded-sm text-[8px] font-bold items-center justify-center',
                          r === 'W' && 'bg-emerald-100 text-emerald-700',
                          r === 'D' && 'bg-gray-100 text-gray-500',
                          r === 'L' && 'bg-rose-100 text-rose-600',
                        )}
                      >
                        {r === 'W' ? 'V' : r === 'L' ? 'D' : 'E'}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Section header ─────────────────────────────────────────────────────────────

function SectionHeader({
  icon: Icon,
  title,
  count,
  collapsed,
  onToggle,
  onRefresh,
}: {
  icon: React.ElementType
  title: string
  count?: number
  collapsed?: boolean
  onToggle?: () => void
  onRefresh?: () => void
}) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <Icon size={14} className="text-gray-400 shrink-0" />
      <button
        onClick={onToggle}
        className="flex items-center gap-2 flex-1 text-left"
        disabled={!onToggle}
      >
        <span className="text-xs font-semibold uppercase tracking-widest text-gray-500">{title}</span>
        {count !== undefined && (
          <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded-full">{count}</span>
        )}
        {onToggle && (
          collapsed
            ? <ChevronDown size={13} className="text-gray-400" />
            : <ChevronUp size={13} className="text-gray-400" />
        )}
      </button>
      {onRefresh && (
        <button onClick={onRefresh} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-all">
          <RefreshCw size={13} />
        </button>
      )}
    </div>
  )
}

// ── Group fixtures by date ─────────────────────────────────────────────────────

function groupByDate(fixtures: FixtureWithPrediction[]): [string, FixtureWithPrediction[]][] {
  const map = new Map<string, FixtureWithPrediction[]>()
  for (const f of fixtures) {
    const arr = map.get(f.date) ?? []
    arr.push(f)
    map.set(f.date, arr)
  }
  return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
}

function fmtDateHeader(d: string) {
  return new Date(d + 'T12:00:00').toLocaleDateString('pt-BR', {
    weekday: 'long', day: '2-digit', month: 'long',
  })
}

// ── Dashboard ──────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [comp, setComp] = useState<Comp>('brasileirao')
  const [fixtures, setFixtures] = useState<FixtureWithPrediction[]>([])
  const [standings, setStandings] = useState<StandingItem[]>([])
  const [recent, setRecent] = useState<FixtureItem[]>([])

  const [loadFix, setLoadFix] = useState(false)
  const [loadStd, setLoadStd] = useState(false)
  const [loadRec, setLoadRec] = useState(false)

  const [noKey, setNoKey] = useState(false)
  const [backendDown, setBackendDown] = useState(false)
  const [colStd, setColStd] = useState(false)
  const [colRec, setColRec] = useState(true)

  const [selected, setSelected] = useState<FixtureWithPrediction | null>(null)

  const fetchAll = useCallback((c: Comp) => {
    setFixtures([]); setStandings([]); setRecent([])
    setNoKey(false); setBackendDown(false)

    setLoadFix(true)
    api.getFixtures(c, 21)
      .then((r) => {
        setFixtures(r.fixtures)
        // 0 fixtures pode ser ausência de API key OU simplesmente sem jogos no período
        if (r.count === 0) setNoKey(true)
      })
      .catch((err) => {
        // Network error = backend fora do ar; outros erros = problema de configuração
        if (err?.code === 'ERR_NETWORK' || err?.message?.includes('Network Error') || err?.message?.includes('ECONNREFUSED')) {
          setBackendDown(true)
        } else {
          setNoKey(true)
        }
      })
      .finally(() => setLoadFix(false))

    setLoadStd(true)
    api.getStandings(c)
      .then((r) => setStandings(r.standings))
      .catch(() => {})
      .finally(() => setLoadStd(false))

    setLoadRec(true)
    api.getRecent(c, 15)
      .then((r) => setRecent(r.fixtures))
      .catch(() => {})
      .finally(() => setLoadRec(false))
  }, [])

  useEffect(() => { fetchAll(comp) }, [comp, fetchAll])

  const grouped = groupByDate(fixtures)
  const ci = COMP[comp]

  return (
    <div className="min-h-screen bg-gray-50 pt-20 pb-16">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">

        {/* ── Page header ──────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2.5">
              <Activity size={22} className="text-blue-600" />
              Análise de Futebol
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              Fixtures, classificação e previsões probabilísticas em tempo real
            </p>
          </div>
          <button
            onClick={() => fetchAll(comp)}
            className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 px-3 py-2 text-sm text-gray-600 transition-all shadow-sm"
          >
            <RefreshCw size={13} />
            Atualizar
          </button>
        </div>

        {/* ── Competition tabs ─────────────────────────────────────────────── */}
        <div className="flex gap-2 mb-8">
          {(['brasileirao', 'champions_league'] as Comp[]).map((c) => {
            const info = COMP[c]
            return (
              <button
                key={c}
                onClick={() => setComp(c)}
                className={clsx(
                  'flex items-center gap-2.5 rounded-xl px-5 py-3 text-sm font-semibold transition-all',
                  comp === c ? info.activeTab : info.inactiveTab
                )}
              >
                <span className="text-base">{info.flag}</span>
                <span>{info.label}</span>
              </button>
            )
          })}
        </div>

        {/* ── Backend offline ───────────────────────────────────────────────── */}
        {backendDown && !loadFix && (
          <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 mb-6">
            <ServerOff size={15} className="text-red-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-red-700">Backend offline</p>
              <p className="text-xs text-red-600 mt-1">
                Inicie o servidor com{' '}
                <code className="bg-red-100 px-1 rounded text-red-800">uvicorn app.api.main:app --reload --port 8000</code>
              </p>
            </div>
          </div>
        )}

        {/* ── API Key warning (só quando backend está online mas sem dados) ─── */}
        {noKey && !backendDown && !loadFix && (
          <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 mb-6">
            <WifiOff size={15} className="text-amber-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-700">Sem fixtures no período ou API não configurada</p>
              <p className="text-xs text-amber-600 mt-1">
                Verifique <code className="bg-amber-100 px-1 rounded text-amber-800">API_FOOTBALL_KEY</code> no <code className="bg-amber-100 px-1 rounded text-amber-800">.env</code> ou não há jogos nos próximos 21 dias.
              </p>
            </div>
          </div>
        )}

        {/* ── Main grid: fixtures (2/3) + standings (1/3) ──────────────────── */}
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">

          {/* Left: Fixtures */}
          <div className="xl:col-span-3 space-y-6">

            {/* Próximas Partidas */}
            <div>
              <SectionHeader
                icon={Clock}
                title={fixtures.length > 0 && fixtures[0]?.date?.startsWith('2024') ? 'Partidas 2024' : 'Próximas Partidas'}
                count={fixtures.length || undefined}
                onRefresh={() => fetchAll(comp)}
              />

              {loadFix ? (
                <div className="space-y-2 animate-pulse">
                  {[1,2,3,4,5].map(i => (
                    <div key={i} className="h-16 rounded-xl bg-gray-200" />
                  ))}
                </div>
              ) : fixtures.length === 0 ? (
                <div className="flex flex-col items-center py-14 rounded-xl border border-dashed border-gray-300 text-center bg-white">
                  <Calendar size={28} className="text-gray-300 mb-3" />
                  <p className="text-sm text-gray-500 font-medium">Nenhuma partida encontrada</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {backendDown ? 'Backend offline — inicie o servidor' : noKey ? 'Configure a chave da API' : 'Sem jogos nos próximos 21 dias'}
                  </p>
                </div>
              ) : (
                <div className="space-y-5">
                  {grouped.map(([dateStr, group]) => (
                    <div key={dateStr}>
                      <p className="text-[10px] uppercase tracking-widest text-gray-400 mb-2.5 capitalize pl-1 font-semibold">
                        {fmtDateHeader(dateStr)}
                      </p>
                      <div className="space-y-2">
                        {group.map(f => (
                          <FixtureCard key={f.fixture_id} f={f} onAnalyze={setSelected} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Resultados Recentes */}
            <div>
              <SectionHeader
                icon={TrendingUp}
                title="Resultados Recentes"
                collapsed={colRec}
                onToggle={() => setColRec(v => !v)}
              />
              {!colRec && (
                loadRec ? (
                  <div className="space-y-1.5 animate-pulse">
                    {[1,2,3].map(i => <div key={i} className="h-10 rounded-lg bg-gray-200" />)}
                  </div>
                ) : recent.length === 0 ? (
                  <p className="text-sm text-gray-400 py-6 text-center">
                    {backendDown ? 'Backend offline' : noKey ? 'Configure a API para ver resultados' : 'Sem resultados recentes'}
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {recent.map(f => <RecentRow key={f.fixture_id} f={f} />)}
                  </div>
                )
              )}
            </div>
          </div>

          {/* Right: Standings */}
          <div className="xl:col-span-2">
            <div className="sticky top-24">
              <SectionHeader
                icon={Trophy}
                title="Classificação"
                collapsed={colStd}
                onToggle={() => setColStd(v => !v)}
              />

              {!colStd && (
                loadStd ? (
                  <div className="space-y-1.5 animate-pulse">
                    {Array.from({ length: 8 }).map((_, i) => (
                      <div key={i} className="h-9 rounded-lg bg-gray-200" />
                    ))}
                  </div>
                ) : standings.length === 0 ? (
                  <div className="flex flex-col items-center py-10 rounded-xl border border-dashed border-gray-300 text-center bg-white">
                    <Trophy size={24} className="text-gray-300 mb-2" />
                    <p className="text-sm text-gray-400">
                      {backendDown ? 'Backend offline' : noKey ? 'Configure a API' : 'Classificação não disponível'}
                    </p>
                  </div>
                ) : (
                  <>
                    <Standings standings={standings} comp={comp} />
                    {/* Legend */}
                    <div className="flex flex-wrap gap-3 mt-3 px-1">
                      <span className="flex items-center gap-1 text-[9px] text-emerald-600">
                        <span className="w-2 h-2 rounded-sm bg-emerald-100 border border-emerald-200 inline-block" />
                        Classificação / G8
                      </span>
                      <span className="flex items-center gap-1 text-[9px] text-rose-500">
                        <span className="w-2 h-2 rounded-sm bg-rose-100 border border-rose-200 inline-block" />
                        Zona de rebaixamento
                      </span>
                    </div>
                  </>
                )
              )}
            </div>
          </div>
        </div>

      </div>

      {/* ── Analysis slide panel ─────────────────────────────────────────────── */}
      <MatchAnalysisPanel
        fixture={selected}
        competition={comp}
        onClose={() => setSelected(null)}
      />
    </div>
  )
}

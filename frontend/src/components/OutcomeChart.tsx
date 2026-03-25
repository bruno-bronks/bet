import type { OutcomeProbs } from '../types/prediction'

interface Props {
  outcome: OutcomeProbs
  homeTeam: string
  awayTeam: string
}

function Bar({ label, value, bg, text }: { label: string; value: number; bg: string; text: string }) {
  const pct = (value * 100).toFixed(1)
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-600 font-medium">{label}</span>
        <span className={`font-bold text-base font-mono ${text}`}>{pct}%</span>
      </div>
      <div className="h-3 w-full rounded-full bg-gray-100 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${bg}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function OutcomeChart({ outcome, homeTeam, awayTeam }: Props) {
  const max = Math.max(outcome.home_win, outcome.draw, outcome.away_win)
  const mostLikely =
    max === outcome.home_win ? homeTeam : max === outcome.away_win ? awayTeam : 'Empate'

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-500">
          Resultado Final (1X2)
        </h3>
        <span className="rounded-md bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-600 ring-1 ring-blue-200">
          {mostLikely}
        </span>
      </div>

      {/* Visual match header */}
      <div className="grid grid-cols-3 items-center gap-2 py-3 border-y border-gray-100">
        <div className="text-center">
          <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Mandante</p>
          <p className="font-bold text-base text-gray-900 truncate">{homeTeam}</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-black text-gray-200">VS</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Visitante</p>
          <p className="font-bold text-base text-gray-900 truncate">{awayTeam}</p>
        </div>
      </div>

      {/* Probability bars */}
      <div className="space-y-3">
        <Bar label={`Vitória ${homeTeam}`} value={outcome.home_win} bg="bg-emerald-500" text="text-emerald-600" />
        <Bar label="Empate" value={outcome.draw} bg="bg-amber-400" text="text-amber-600" />
        <Bar label={`Vitória ${awayTeam}`} value={outcome.away_win} bg="bg-rose-500" text="text-rose-500" />
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-2 pt-2">
        {[
          { label: homeTeam, value: outcome.home_win, bg: 'bg-emerald-50', ring: 'ring-emerald-200', text: 'text-emerald-600' },
          { label: 'Empate', value: outcome.draw, bg: 'bg-amber-50', ring: 'ring-amber-200', text: 'text-amber-600' },
          { label: awayTeam, value: outcome.away_win, bg: 'bg-rose-50', ring: 'ring-rose-200', text: 'text-rose-500' },
        ].map((item) => (
          <div key={item.label} className={`rounded-lg ${item.bg} ring-1 ${item.ring} p-3 text-center`}>
            <p className={`text-xl font-black font-mono ${item.text}`}>
              {(item.value * 100).toFixed(0)}%
            </p>
            <p className="text-xs text-gray-500 mt-0.5 truncate">{item.label}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

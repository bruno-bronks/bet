import type { GoalsInfo } from '../types/prediction'

interface Props {
  goals: GoalsInfo
  homeTeam: string
  awayTeam: string
}

interface OverCardProps {
  line: string
  probability: number
}

function OverCard({ line, probability }: OverCardProps) {
  const pct = (probability * 100).toFixed(0)
  const hot = probability >= 0.6
  return (
    <div className={`rounded-lg p-3 text-center ring-1 transition-all ${
      hot ? 'bg-blue-50 ring-blue-200' : 'bg-gray-50 ring-gray-200'
    }`}>
      <p className={`text-xs font-medium mb-1 ${hot ? 'text-blue-600' : 'text-gray-500'}`}>
        Over {line}
      </p>
      <p className={`text-lg font-black font-mono ${hot ? 'text-blue-700' : 'text-gray-700'}`}>
        {pct}%
      </p>
    </div>
  )
}

export default function GoalsPanel({ goals, homeTeam, awayTeam }: Props) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-5">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-500">
        Mercado de Gols
      </h3>

      {/* Expected goals */}
      <div className="grid grid-cols-3 items-center gap-3">
        <div className="rounded-lg bg-emerald-50 ring-1 ring-emerald-200 p-3 text-center">
          <p className="text-xs text-gray-500 mb-1 truncate">{homeTeam}</p>
          <p className="text-2xl font-black text-emerald-600 font-mono">
            {goals.expected_goals_home.toFixed(2)}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">xG</p>
        </div>

        <div className="rounded-lg bg-gray-50 ring-1 ring-gray-200 p-3 text-center">
          <p className="text-xs text-gray-500 mb-1">Total</p>
          <p className="text-2xl font-black text-gray-800 font-mono">
            {goals.expected_goals_total.toFixed(2)}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">xG</p>
        </div>

        <div className="rounded-lg bg-rose-50 ring-1 ring-rose-200 p-3 text-center">
          <p className="text-xs text-gray-500 mb-1 truncate">{awayTeam}</p>
          <p className="text-2xl font-black text-rose-500 font-mono">
            {goals.expected_goals_away.toFixed(2)}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">xG</p>
        </div>
      </div>

      {/* Over/Under lines */}
      <div>
        <p className="text-xs text-gray-400 mb-2 uppercase tracking-wide">Over / Under</p>
        <div className="grid grid-cols-5 gap-1.5">
          <OverCard line="0.5" probability={goals.over_0_5} />
          <OverCard line="1.5" probability={goals.over_1_5} />
          <OverCard line="2.5" probability={goals.over_2_5} />
          <OverCard line="3.5" probability={goals.over_3_5} />
          <OverCard line="4.5" probability={goals.over_4_5} />
        </div>
      </div>

      {/* BTS + Clean sheets */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-lg bg-purple-50 ring-1 ring-purple-200 p-3 text-center">
          <p className="text-xs text-gray-500 mb-1">Ambas marcam</p>
          <p className="text-lg font-bold font-mono text-purple-600">
            {(goals.both_teams_score * 100).toFixed(0)}%
          </p>
        </div>
        <div className="rounded-lg bg-gray-50 ring-1 ring-gray-200 p-3 text-center">
          <p className="text-xs text-gray-500 mb-1">CS {homeTeam.split(' ')[0]}</p>
          <p className="text-lg font-bold font-mono text-gray-700">
            {(goals.clean_sheet_home * 100).toFixed(0)}%
          </p>
        </div>
        <div className="rounded-lg bg-gray-50 ring-1 ring-gray-200 p-3 text-center">
          <p className="text-xs text-gray-500 mb-1">CS {awayTeam.split(' ')[0]}</p>
          <p className="text-lg font-bold font-mono text-gray-700">
            {(goals.clean_sheet_away * 100).toFixed(0)}%
          </p>
        </div>
      </div>
    </div>
  )
}
